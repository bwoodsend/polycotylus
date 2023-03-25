import shlex
import collections
from fnmatch import fnmatch
from pathlib import Path

import pytest

from polycotylus import _docker, _exceptions
from polycotylus._mirror import mirrors
from polycotylus._project import Project

dumb_text_viewer = Path(__file__, "../../examples/dumb_text_viewer").resolve()
ubrotli = dumb_text_viewer.with_name("ubrotli")
bare_minimum = dumb_text_viewer.with_name("bare-minimum")
silly_name = Path(__file__, "../mock-packages/silly-name").resolve()
fussy_arch = silly_name.with_name("fussy_arch")

awkward_pypi_packages = [
    "zope.deferredimport",  # Contains a '.'
    "ruamel.yaml",
    "jaraco.classes",
    "flit_core",  # Contains a '_'
    "prompt_toolkit",
    "nest_asyncio",
    "setuptools_scm",
    "GitPython",  # Contains uppercase letters
    "cython",  # Ignores the standard Python package prefix on all distributions
    "urllib3",  # Contains a number
    "python-dateutil",  # Already has py/python prefix.
    "PyQt5",
    "pyyaml",
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

        with pytest.raises(_exceptions.PackageUnavailableError):
            self.cls.python_package("i-am-a-unicorn")

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