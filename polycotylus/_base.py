import abc
import shutil
import re
import contextlib

import pkg_resources

from polycotylus import _docker
from polycotylus._mirror import mirrors


class BaseDistribution(abc.ABC):
    name = abc.abstractproperty()
    python_prefix = abc.abstractproperty()
    python = "python"
    python_extras: dict = abc.abstractproperty()
    _formatter = abc.abstractproperty()
    pkgdir = "$pkgdir"

    imagemagick = "imagemagick"
    imagemagick_svg = "librsvg"
    xvfb_run = abc.abstractproperty()
    font = "ttf-dejavu"

    def __init__(self, project):
        self.project = project

    @property
    def distro_root(self):
        return self.project.root / ".polycotylus" / self.name

    @abc.abstractmethod
    def available_packages():
        raise NotImplementedError

    @abc.abstractmethod
    def build_base_packages():
        """Packages that the distribution considers *too standard* to be given
        as build dependencies."""
        raise NotImplementedError

    @classmethod
    def python_package(cls, requirement):
        requirement = pkg_resources.Requirement(requirement)
        name = cls.normalise_package(requirement.key)
        if cls.python_package_convention(name) in cls.available_packages():
            requirement.name = cls.python_package_convention(name)
        elif name in cls.available_packages():
            requirement.name = name
        else:
            assert 0
        return str(requirement)

    invalid_package_characters = abc.abstractproperty()

    @abc.abstractmethod
    def fix_package_name(name):
        """Apply the distribution's package naming rules for case folding/
        underscore vs hyphen normalisation."""
        raise NotImplementedError

    @classmethod
    def normalise_package(cls, name):
        """Fix up a package name to make it compatible with this Linux
        Distribution, raise an error if there any unfixable invalid characters.
        """
        normalised = cls.fix_package_name(name)
        if invalid := re.findall(cls.invalid_package_characters, normalised):
            raise ValueError(
                f"'{name} is an invalid {cls.name} package name because it "
                f"contains the characters {invalid}.")
        return normalised

    @abc.abstractmethod
    def python_package_convention(self, pypi_name):
        raise NotImplementedError

    @property
    def package_name(self):
        """The distro-normalized/slugified version of this project's name,"""
        name = self.fix_package_name(self.project.name)
        if self.project.prefix_package_name:
            name = self.python_package_convention(name)
        return name

    @abc.abstractmethod
    def dockerfile(self):
        raise NotImplementedError

    @property
    def mirror(self):
        return mirrors[self.name]

    def inject_source(self):
        from urllib.parse import urlparse
        from pathlib import PurePosixPath

        url = self.project.source_url.format(version=self.project.version)
        name = PurePosixPath(urlparse(url).path).name
        with open(self.distro_root / name, "wb") as f:
            f.write(self.project.tar())

    def pip_build_command(self, indentation, into="$pkgdir"):
        return self._formatter(f"""
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
        return out

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
        return out

    def define_py3ver(self):
        return self._formatter(f"""
            _py3ver() {{
                {self.python_prefix}/bin/python3 -c 'import sys; print("{{0}}.{{1}}".format(*sys.version_info))'
            }}
        """) + "\n"

    def install_desktop_files(self, indentation, source="", dest="$pkgdir"):
        if source:
            source += "/"
        out = ""
        for id in self.project.desktop_entry_points:
            out += self._formatter(
                f'install -Dm644 "{source}.polycotylus/{id}.desktop" '
                f'"{dest}/usr/share/applications/{id}.desktop"', indentation)
        return out

    @abc.abstractmethod
    def generate(self):
        """Generate all pragmatically created files."""
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root)
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
                                 self.project.root, target="build")

    @abc.abstractmethod
    def build(self):
        raise NotImplementedError

    def build_test_image(self):
        with self.mirror:
            return _docker.build(self.distro_root / "Dockerfile",
                                 self.project.root, target="test")

    @abc.abstractmethod
    def test(self, package):
        pass


def _deduplicate(array):
    """Remove duplicates, preserving order of first appearance."""
    return list(dict.fromkeys(array))
