import abc
import shutil
import re
import os
import platform
from functools import lru_cache
import subprocess
import base64

from packaging.requirements import Requirement

from polycotylus import _docker, _exceptions, _misc, machine
from polycotylus._project import Artifact
from polycotylus._mirror import mirrors


class BaseDistribution(abc.ABC):
    python_prefix = "/usr"
    python_extras: dict = abc.abstractproperty()
    _formatter = abc.abstractproperty()
    supported_architectures = abc.abstractproperty()
    _packages = abc.abstractproperty()
    tag = abc.abstractproperty()
    signature_property = None

    def __init__(self, project, architecture=None, signature=None):
        self.project = project
        self.architecture = architecture or self.preferred_architecture
        if self.architecture not in self.supported_architectures:
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                Architecture {_exceptions.string(repr(self.architecture))} is not
                available on {type(self).__name__} Linux. Valid architectures are
                {_exceptions.highlight_toml(str(sorted(self.supported_architectures)))}.
            """))
        self.docker_architecture = self.supported_architectures[self.architecture]
        # Check that the appropriate Qemu emulators are installed to virtualise
        # this architecture.
        if platform.system() == "Linux" and {"amd64": "x86_64", "arm64": "aarch64"}.get(self.architecture, self.architecture) != machine():
            qemu_architecture = {"amd64": "x86_64", "arm64": "aarch64", "mips64le": "mips64el"}.get(self.docker_architecture, self.docker_architecture)
            # Qemu is not required for running 32-bit variants of x86_64 or aarch64.
            if not ((machine() == "x86_64" and re.fullmatch("i[3-6]86", qemu_architecture))
                    or (machine() == "aarch64" and qemu_architecture.startswith("arm"))):
                qemu = f"qemu-{qemu_architecture.split('/')[0]}-static"
                if not shutil.which(qemu):
                    raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                        Missing qemu emulator: Emulating
                        {_exceptions.string(repr(self.architecture))} requires
                        the {_exceptions.string(repr(qemu))} command. Install
                        it with your native package manager.
                    """))
                _docker.setup_binfmt()
        if self.signature_property:
            setattr(self, self.signature_property, signature)

    @property
    def distro_root(self):
        return self.project.root / ".polycotylus" / self.name

    @_misc.classproperty
    def preferred_architecture(_, cls):
        return machine() if machine() in cls.supported_architectures else "x86_64"

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
        uid = 1000 if platform.system() == "Windows" else os.getuid()
        return f"""\
            RUN echo '%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
            RUN useradd --create-home --non-unique --uid {uid} --groups {groups} user"""

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
    def python_package(cls, requirement, dependency_name_map=None):
        requirement = Requirement(requirement)
        name = re.sub("[._-]+", "-", requirement.name.lower())
        available = cls.available_packages_normalized()

        if not cls.evaluate_requirements_marker(requirement):
            return
        else:
            requirement.marker = None
        if dependency_name_map and name in dependency_name_map:
            name = dependency_name_map[name]
        elif cls.python_package_convention(name) in available:
            name = available[cls.python_package_convention(name)]
        elif name in available:
            name = available[name]
        elif m := re.match("(python|py)3?-?(.*)", name.lower()):
            try:
                name = cls.python_package(m[2], dependency_name_map)
            except _exceptions.PackageUnavailableError:
                raise _exceptions.PackageUnavailableError(requirement.name, cls.name) from None
        else:
            raise _exceptions.PackageUnavailableError(requirement.name, cls.name)

        requirement.name = name
        requirement.extras = set()
        return str(requirement)

    @property
    def dependency_name_map(self):
        out = {}
        for (package, map) in self.project.dependency_name_map.items():
            for key in map:
                if self.name in key.split():
                    out[re.sub("[._-]+", "-", package.lower())] = map[key]
                    break
        return out

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
        if not self.project.frontend:
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

    def pip_build_command(self, indentation, into):
        if self.project.setuptools_scm:
            declare_version = 'export SETUPTOOLS_SCM_PRETEND_VERSION="$pkgver"'
        out = self._formatter(f"""
            {declare_version if self.project.setuptools_scm else ""}
            {self.python_prefix}/bin/pip install --disable-pip-version-check --no-compile --prefix="{into}{self.python_prefix}" --no-warn-script-location --no-deps --no-build-isolation .
        """, indentation)
        if self.project.contains_py_files:
            out += self._formatter(f"""
                {self.python_prefix}/bin/python -m compileall --invalidation-mode=unchecked-hash -s "{into}" "{into}{self.python_prefix}/lib/"
            """, indentation)
        return out

    @property
    def icons(self):
        icons = []
        for desktop_file in self.project.desktop_entry_points.values():
            if icon := desktop_file.get("icon"):  # pragma: no branch
                icons.append((icon["source"], icon["id"]))
            for action in desktop_file.get("actions", {}).values():
                if icon := action.get("icon"):
                    icons.append((icon["source"], icon["id"]))
        return _deduplicate(icons)

    def _dependencies(self, dependencies):
        out = []
        for extra in dependencies.get("python", []):
            out += self.python_extras.get(extra, [])
        for package in dependencies.get("pip", []):
            out.append(self.python_package(package, self.dependency_name_map))
        out += dependencies.get(self.name, [])
        return list(filter(None, out))

    @property
    def dependencies(self):
        out = [self._packages["python"] + self.project.supported_python]
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
            if any(not source.endswith(".svg") for (source, _) in self.icons):
                out += self._packages["image-conversion"]
            if any(source.endswith(".svg") for (source, _) in self.icons):
                out += self._packages["svg-conversion"]
        disallowed = self.build_base_packages()
        out = [i for i in out if i not in disallowed]
        return _deduplicate(out)

    @property
    def test_dependencies(self):
        out = self._dependencies(self.project.test_dependencies)
        if self.project.gui:
            out += [*self._packages["xvfb-run"].split(), self._packages["font"]]
        return _deduplicate(out)

    def install_icons(self, indentation, sysroot):
        if not self.icons:
            return ""
        out = self._formatter(f"""
            for _size in 16 22 24 32 48 128; do
                _icon_dir="{sysroot}/usr/share/icons/hicolor/${{_size}}x$_size/apps"
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
                f"mkdir -p {sysroot}/usr/share/icons/hicolor/scalable/apps",
                indentation)
        for (source, dest) in self.icons:
            if source.endswith(".svg"):
                out += self._formatter(
                    f'cp "{source}" {sysroot}/usr/share/icons/hicolor/scalable/apps/{dest}.svg',
                    indentation)
        return out

    def define_py3ver(self):
        return self._formatter(f"""
            _py3ver() {{
                {self.python_prefix}/bin/python3 -c 'import sys; print("{{0}}.{{1}}".format(*sys.version_info))'
            }}
        """) + "\n"

    def install_desktop_files(self, indentation, dest):
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
        _misc.unix_write(self.distro_root / "Dockerfile", self.dockerfile())

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

    def _make_artifact(self, path, package_type, signature_path=None):
        return Artifact(self.name, self.tag, self.architecture, package_type, path, signature_path)

    def update_artifacts_json(self, packages):
        with self.project.artifacts_database() as database:
            database.extend(packages.values())


class GPGBased(abc.ABC):
    signature_property = "signing_id"

    @property
    def signing_id(self):
        return self._signing_id

    @signing_id.setter
    def signing_id(self, id):
        if id is None:
            self._signing_id = None
            return
        # Normalise key identifier (name/email/abbreviated fingerprint) to full
        # length fingerprint (which doubles as a check that the key exists).
        p = subprocess.run(["gpg", "--with-colons", "--status-fd=2", "--list-secret-keys", id],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if p.returncode:
            assert "[GNUPG:] ERROR keylist.getkey 17" in p.stderr, p.stderr + "\nI am a bug in polycotylus, please report me!"
            raise _exceptions.PolycotylusUsageError(
                f'No private GPG key found with user ID or fingerprint {_exceptions.string(repr(id))}')
        # For GPG's machine readable (--with-colons) mode, see:
        # https://github.com/gpg/gnupg/blob/gnupg-2.5-base/doc/DETAILS#format-of-the-colon-listings
        lines = p.stdout.splitlines()
        keys = sorted(i.split(":")[4] for i in lines if i.startswith("sec:"))
        if len(keys) > 1:
            raise _exceptions.PolycotylusUsageError(
                f'The GPG signing key identifier {_exceptions.string(repr(id))} is ambiguous. '
                f'It could refer to any of {_exceptions.highlight_toml(str(keys))}')
        fingerprints = [i.split(":")[9] for i in lines if i.startswith("fpr:")]
        self._signing_id, = [i for i in fingerprints if i.endswith(keys[0])]

    @property
    def public_key(self):
        p = subprocess.run(["gpg", "--armor", "--export", self.signing_id],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert p.returncode == 0, p.stderr.decode()
        return base64.b64encode(p.stdout).decode("ascii")


def _deduplicate(array):
    """Remove duplicates, preserving order of first appearance."""
    return list(dict.fromkeys(array))
