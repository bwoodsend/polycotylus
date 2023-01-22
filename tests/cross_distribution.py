import shlex
import collections

import pytest

from polycotylus import _docker
from polycotylus._mirror import mirrors

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
