import pytest

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
