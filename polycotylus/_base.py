import abc
import shutil
import re

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
    build_script_name = "PKGBUILD"

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
        pass

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
        pass

    @property
    def package_name(self):
        """The distro-normalized/slugified version of this project's name,"""
        name = self.fix_package_name(self.project.name)
        if self.project.prefix_package_name:
            name = self.python_package_convention(name)
        return name

    @abc.abstractmethod
    def dockerfile(self):
        pass

    @abc.abstractmethod
    def pkgbuild(self):
        pass

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
        return self._formatter(
            f"""
            {self.python_prefix}/bin/pip install --no-compile --prefix="{into}{self.python_prefix}" --no-warn-script-location --no-deps --no-build-isolation .
            {self.python_prefix}/bin/python -m compileall --invalidation-mode=unchecked-hash -s "{into}" "{into}{self.python_prefix}/lib/"
        """, indentation)

    @property
    def icons(self):
        return [(i["icon"]["source"], i["icon"]["id"])
                for i in self.project.desktop_entry_points.values()]

    def _dependencies(self, dependencies):
        out = []
        for extra in dependencies.get("python", []):
            out += self.python_extras[extra]
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
        if self.icons:
            out.append(self.imagemagick)
            if any(source.endswith(".svg") for (source, _) in self.icons):
                out.append(self.imagemagick_svg)
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
        out = self._formatter(
            f"""
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

    def install_desktop_files(self, indentation, source="", dest="$pkgdir"):
        if source:
            source += "/"
        out = ""
        for id in self.project.desktop_entry_points:
            out += self._formatter(
                f'install -Dm644 "{source}.polycotylus/{id}.desktop" '
                f'"{dest}/usr/share/applications/{id}.desktop"', indentation)
        return out

    def generate(self, clean=False):
        """Generate all pragmatically created files."""
        if clean:
            try:
                shutil.rmtree(self.distro_root)
            except FileNotFoundError:
                pass
        self.distro_root.mkdir(parents=True, exist_ok=True)
        self.project.write_desktop_files()
        self.project.write_gitignore()
        self.inject_source()
        (self.distro_root / self.build_script_name).write_text(
            self.pkgbuild(), encoding="utf-8")
        (self.distro_root / "Dockerfile").write_text(self.dockerfile(), "utf-8")

    def build_builder_image(self, verbosity=None):
        with self.mirror:
            return _docker.build(self.distro_root / "Dockerfile",
                                 self.project.root, target="build",
                                 verbosity=verbosity)

    @abc.abstractmethod
    def build(self, verbosity=None):
        pass

    def build_test_image(self, verbosity=None):
        with self.mirror:
            return _docker.build(self.distro_root / "Dockerfile",
                                 self.project.root, target="test",
                                 verbosity=verbosity)

    @abc.abstractmethod
    def test(self, package, verbosity=None):
        pass


def _deduplicate(array):
    """Remove duplicates, preserving order of first appearance."""
    return list(dict.fromkeys(array))
