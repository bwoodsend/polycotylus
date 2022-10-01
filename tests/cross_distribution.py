import shlex

from docker import from_env
import pytest

from polycotylus._mirror import mirrors

awkward_pypi_packages = [
    "zope.deferredimport",  # Contains a '.'
    "flit_core",  # Contains a '_'
    "GitPython",  # Contains uppercase letters
    "cython",  # Ignores the standard Python package prefix on all distributions
    "urllib3",  # Contains a number
]


class Base:
    cls: type

    def test_python_package(self):
        for pypi_name in awkward_pypi_packages:
            self.cls.python_package(pypi_name)

        with pytest.raises(ValueError):
            self.cls.python_package("hello world")

    base_image: str
    package_install: str

    @pytest.mark.parametrize(
        "name",
        ["tkinter", "sqlite3", "decimal", "lzma", "zlib", "readline", "bz2"])
    def test_python_extras(self, name, ids=str):
        docker = from_env()
        extras = self.cls.python_extras[name]
        mirror = mirrors[self.cls.name]
        script = self.cls._formatter(f"""
            {mirror.install}
            {self.package_install} python3 {shlex.join(extras)}
            python3 -c 'import {name}'
        """)
        with mirror:
            docker.containers.run(self.base_image, ["sh", "-c", script],
                                  network_mode="host", remove=True)
