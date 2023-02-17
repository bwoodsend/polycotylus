import shlex
import collections
from fnmatch import fnmatch

import pytest

from polycotylus import _docker
from polycotylus._mirror import mirrors
from polycotylus._project import Project
from tests import ubrotli

awkward_pypi_packages = [
    "zope.deferredimport",  # Contains a '.'
    "flit_core",  # Contains a '_'
    "GitPython",  # Contains uppercase letters
    "cython",  # Ignores the standard Python package prefix on all distributions
    "urllib3",  # Contains a number
]


def _group_python_extras(dependencies):
    extras = ["tkinter", "sqlite3", "decimal", "lzma", "zlib", "readline",
              "bz2", "curses", "ctypes"]
    grouped = collections.defaultdict(list)
    for extra in extras:
        # ~ yield dependencies.get(extra, ()), (extra,)
        grouped[tuple(dependencies.get(extra, ()))].append(extra)
    return grouped.items()


class Base:
    cls: type

    def test_available_packages(self):
        packages = self.cls.available_packages()
        assert len(packages) > 1000
        for package in packages:
            assert " " not in package

    def test_python_package(self):
        for pypi_name in awkward_pypi_packages:
            assert self.cls.python_package(pypi_name) in self.cls.available_packages()

        with pytest.raises(ValueError):
            self.cls.python_package("hello world")

    base_image: str
    package_install: str

    def test_python_extras(self):
        for (packages, imports) in _group_python_extras(self.cls.python_extras):
            mirror = mirrors[self.cls.name]
            script = self.cls._formatter(f"""
                {mirror.install}
                {self.package_install} python3 {shlex.join(packages)}
                python3 -c 'import {", ".join(imports)}'
            """)
            with mirror:
                _docker.run(self.base_image, script)


def qemu(cls):
    packages = {}

    @pytest.mark.parametrize("architecture", cls.supported_architectures, ids=str)
    def test_multiarch(architecture):
        self = cls(Project.from_root(ubrotli), architecture)
        self.generate()
        package = self.build()["main"]
        packages[architecture] = package
        for (_architecture, _package) in packages.items():
            assert _package.is_file()
        container = self.test(package)
        with container[self.python_prefix] as tar:
            files = tar.getnames()
        binaries = [i for i in files if fnmatch(i, "**/ubrotli*.so*")]
        assert len(binaries) == 1
        binary, = binaries

        if architecture == "armv7":
            assert "arm" in binary
        elif architecture.startswith("ppc"):
            assert architecture.replace("ppc", "powerpc") in binary
        elif architecture == "x86":
            "i386" in binary
        else:
            architecture in binary

    return test_multiarch
