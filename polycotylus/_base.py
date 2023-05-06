import abc
import shutil
import re
import os
import platform
from functools import lru_cache

from packaging.requirements import Requirement

from polycotylus import _docker, _exceptions, _misc
from polycotylus._mirror import mirrors


class BaseDistribution(abc.ABC):
    python_prefix = abc.abstractproperty()
    python = "python"
    python_extras: dict = abc.abstractproperty()
    _formatter = abc.abstractproperty()
    pkgdir = "$pkgdir"
    supported_architectures = abc.abstractproperty()

    imagemagick = "imagemagick"
    imagemagick_svg = "librsvg"
    xvfb_run = abc.abstractproperty()
    font = "ttf-dejavu"

    def __init__(self, project, architecture=None):
        self.project = project
        self.architecture = architecture or platform.machine()
        if self.architecture not in self.supported_architectures:
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                Architecture "{self.architecture}" is not available on
                {type(self).__name__} Linux. Valid architectures are
                {sorted(self.supported_architectures)}.
            """))
        self.docker_architecture = self.supported_architectures[self.architecture]
        if self.architecture != platform.machine():
            qemu = f"qemu-{self.docker_architecture}-static"
            if not shutil.which(qemu):
                raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                    Missing qemu emulator: Emulating "{self.architecture}"
                    requires the "{qemu}" command. Install it with your native
                    package manager.
                """))
            _docker.setup_binfmt()

    @property
    def distro_root(self):
        return self.project.root / ".polycotylus" / self.name

    @classmethod
    def available_packages(cls):
        cls._package_manager_queries()
        return cls._available_packages

    @classmethod
    def build_base_packages(cls):
        """Packages that the distribution considers *too standard* to be given
        as build dependencies."""
        cls._package_manager_queries()
        return cls._build_base_packages

    @classmethod
    def python_version(cls):
        cls._package_manager_queries()
        return cls._python_version

    @classmethod
    @lru_cache()
    def available_packages_normalized(cls):
        return {re.sub("[._-]+", "-", i.lower()): i for i in cls.available_packages()}

    def _install_user(self, *groups):
        groups = ",".join(("wheel", *groups))
        return f"""\
            RUN echo '%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
            RUN useradd --create-home --non-unique --uid {os.getuid()} --groups {groups} user"""

    @classmethod
    def evaluate_requirements_marker(cls, requirement: Requirement):
        # See table in https://peps.python.org/pep-0508/#environment-markers
        return not requirement.marker or requirement.marker.evaluate({
            "os_name": "posix",
            "sys_platform": "linux",
            "platform_python_implementation": "CPython",
            "platform_system": "Linux",
            "python_version": re.match(r"\d+\.\d+", cls.python_version())[0],
            "python_full_version": cls.python_version(),
            "implementation_name": "cpython",
            "implementation_version": cls.python_version(),
        })

    @classmethod
    def python_package(cls, requirement):
        requirement = Requirement(requirement)
        name = re.sub("[._-]+", "-", requirement.name.lower())
        available = cls.available_packages_normalized()

        if not cls.evaluate_requirements_marker(requirement):
            return
        else:
            requirement.marker = None
        if cls.python_package_convention(name) in available:
            name = available[cls.python_package_convention(name)]
        elif name in available:
            name = available[name]
        elif m := re.match("(python|py)3?-?(.*)", name.lower()):
            try:
                name = cls.python_package(m[2])
            except _exceptions.PackageUnavailableError:
                raise _exceptions.PackageUnavailableError(requirement.name, cls.name) from None
        else:
            raise _exceptions.PackageUnavailableError(requirement.name, cls.name)

        requirement.name = name
        requirement.extras = set()
        return str(requirement)

    @abc.abstractmethod
    def fix_package_name(name):
        """Apply the distribution's package naming rules for case folding/
        underscore vs hyphen normalisation."""
        raise NotImplementedError

    @abc.abstractmethod
    def python_package_convention(self, pypi_name):
        raise NotImplementedError

    @property
    def package_name(self):
        """The distro-normalized/sluggified version of this project's name,"""
        name = self.fix_package_name(self.project.name)
        if self.project.prefix_package_name:
            name = self.python_package_convention(name)
        return name

    @abc.abstractmethod
    def dockerfile(self):
        raise NotImplementedError

    @_misc.classproperty
    def name(_, cls):
        return cls.__name__.lower()

    @_misc.classproperty
    def mirror(_, cls):
        return mirrors[cls.name]

    def inject_source(self):
        from urllib.parse import urlparse
        from pathlib import PurePosixPath

        url = self.project.source_url.format(version=self.project.version)
        name = PurePosixPath(urlparse(url).path).name
        with open(self.distro_root / name, "wb") as f:
            f.write(self.project.tar())

    def pip_build_command(self, indentation, into="$pkgdir"):
        if self.project.setuptools_scm:
            name = re.sub("[_.-]+", "_", self.project.name.upper())
            declare_version = f'export SETUPTOOLS_SCM_PRETEND_VERSION="$pkgver"'
            print(declare_version)
        return self._formatter(f"""
            {declare_version if self.project.setuptools_scm else ""}
            {self.python_prefix}/bin/pip install --disable-pip-version-check --no-compile --prefix="{into}{self.python_prefix}" --no-warn-script-location --no-deps --no-build-isolation .
            {self.python_prefix}/bin/python -m compileall --invalidation-mode=unchecked-hash -s "{into}" "{into}{self.python_prefix}/lib/"
        """, indentation)

    @property
    def icons(self):
        return [(i["icon"]["source"], i["icon"]["id"])
                for i in self.project.desktop_entry_points.values()
                if "icon" in i]

    def _dependencies(self, dependencies):
        out = []
        for extra in dependencies.get("python", []):
            out += self.python_extras.get(extra, [])
        for package in dependencies.get("pip", []):
            out.append(self.python_package(package))
        out += dependencies.get(self.name, [])
        return list(filter(None, out))

    @property
    def dependencies(self):
        out = [self.python + self.project.supported_python]
        out += self._dependencies(self.project.dependencies)
        return _deduplicate(out)

    @property
    def build_dependencies(self):
        out = [self.python_package("wheel"), self.python_package("pip")]
        out += self._dependencies(self.project.build_dependencies)
        if not self.project.build_dependencies.get("pip"):
            # If no build backend is specified by a project, pip defaults to
            # setuptools.
            out.append(self.python_package("setuptools>=61.0"))
        if self.icons:
            out.append(self.imagemagick)
            if any(source.endswith(".svg") for (source, _) in self.icons):
                out.append(self.imagemagick_svg)
        disallowed = self.build_base_packages()
        out = [i for i in out if i not in disallowed]
        return _deduplicate(out)

    @property
    def test_dependencies(self):
        out = self._dependencies(self.project.test_dependencies)
        if self.project.gui:
            out += [self.xvfb_run, self.font]
        return _deduplicate(out)

    def install_icons(self, indentation):
        if not self.icons:
            return ""
        out = self._formatter(f"""
            for _size in 16 22 24 32 48 128; do
                _icon_dir="{self.pkgdir}/usr/share/icons/hicolor/${{_size}}x$_size/apps"
                mkdir -p "$_icon_dir"
        """, indentation)
        for (source, dest) in self.icons:
            out += self._formatter(
                f'convert -background "#00000000" -size $_size +set date:create '
                f'+set date:modify "{source}" "$_icon_dir/{dest}.png"',
                indentation + 1)
        out += self._formatter("done", indentation)
        if any(i.endswith(".svg") for (i, _) in self.icons):
            out += self._formatter(
                f"mkdir -p {self.pkgdir}/usr/share/icons/hicolor/scalable/apps",
                indentation)
        for (source, dest) in self.icons:
            if source.endswith(".svg"):
                out += self._formatter(
                    f'cp "{source}" {self.pkgdir}/usr/share/icons/hicolor/scalable/apps/{dest}.svg',
                    indentation)
        return out

    def define_py3ver(self):
        return self._formatter(f"""
            _py3ver() {{
                {self.python_prefix}/bin/python3 -c 'import sys; print("{{0}}.{{1}}".format(*sys.version_info))'
            }}
        """) + "\n"

    def install_desktop_files(self, indentation, dest="$pkgdir"):
        out = ""
        for id in self.project.desktop_entry_points:
            out += self._formatter(
                f'install -Dm644 ".polycotylus/{id}.desktop" '
                f'"{dest}/usr/share/applications/{id}.desktop"', indentation)
        return out

    @abc.abstractmethod
    def generate(self):
        """Generate all pragmatically created files."""
        self.distro_root.mkdir(parents=True, exist_ok=True)
        self.project.write_desktop_files()
        self.distro_root.chmod(0o777)
        self.project.write_gitignore()
        self.project.write_dockerignore()
        self.inject_source()
        (self.distro_root / "Dockerfile").write_text(self.dockerfile(), "utf-8")

    def build_builder_image(self):
        with self.mirror:
            return _docker.build(self.distro_root / "Dockerfile",
                                 self.project.root, target="build",
                                 architecture=self.docker_architecture)

    @abc.abstractmethod
    def build(self):
        raise NotImplementedError

    def build_test_image(self):
        with self.mirror:
            return _docker.build(self.distro_root / "Dockerfile",
                                 self.project.root, target="test",
                                 architecture=self.docker_architecture)

    @abc.abstractmethod
    def test(self, package):
        pass


def _deduplicate(array):
    """Remove duplicates, preserving order of first appearance."""
    return list(dict.fromkeys(array))
