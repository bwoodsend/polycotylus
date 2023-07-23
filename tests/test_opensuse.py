import pytest

import polycotylus
import shared
import test_fedora

pytestmark = pytest.mark.skipif(polycotylus._docker.docker.variant == "podman",
                                reason="OpenSUSE with podman is not supported")


class TestCommon(shared.Base):
    cls = polycotylus.OpenSUSE
    base_image = cls.image
    package_install = "zypper install -y"

    def test_python_package(self):
        for package in shared.awkward_pypi_packages:
            self.cls.python_package(package)
        with pytest.raises(polycotylus._exceptions.PackageUnavailableError):
            self.cls.python_package("i-am-a-unicorn")


def test_test_command():
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.bare_minimum))

    self.project.test_command = "pytest"
    assert self.test_command == "%pytest"
    self.project.test_command = "pytest -v"
    assert self.test_command == "%pytest -v"
    self.project.test_command = "\n\npytest -v\n  \n"
    assert self.test_command == "%pytest -v"
    self.project.test_command = "pytest foo\npytest bar"
    assert self.test_command == "%pytest foo\n%pytest bar"

    self.project.test_command = "xvfb-run pytest -xyz"
    assert self.test_command == "%python_expand xvfb-run $python -m pytest -xyz"
    self.project.test_command = "FOO=bar pytest"
    assert self.test_command == "%python_expand FOO=bar $python -m pytest"

    self.project.test_command = "xvfb-run pytest\npython -c '1 + 1'"
    assert self.test_command == \
        "%{python_expand export PYTHONPATH=%{buildroot}%{$python_sitelib}\n" \
        "xvfb-run $python -m pytest\n$python -c '1 + 1'\n}"

    self.project.test_command = "python -m unittest discover tests"
    assert self.test_command == "%pyunittest discover tests"

    self.project.architecture = "any"
    self.project.test_command = "xvfb-run python -m unittest foo\npython -c ''"
    assert self.test_command == \
        "%{python_expand export PYTHONPATH=%{buildroot}%{$python_sitearch}\n" \
        "xvfb-run $python -m unittest foo\n$python -c ''\n}"


def test_unittest():
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.bare_minimum))
    self.generate()
    rpms = self.build()
    assert len(rpms) == 4
    container = self.test(rpms["main"])
    assert "Ran 1 test" in container.output


def test_ubrotli():
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.ubrotli))
    self.generate()
    rpms = self.build()
    assert len(rpms) == 4
    self.test(rpms["main"])


def test_silly_named_package(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.silly_name))
    test_fedora._check_values_align(self.spec())
    self.generate()
    rpms = self.build()
    assert len(rpms) == 4
    self.test(rpms["main"])


def test_dumb_text_viewer():
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.dumb_text_viewer))
    self.generate()
    rpms = self.build()
    assert len(rpms) == 1
    container = self.test(rpms["main"])
    container.file("/usr/share/applications/underwhelming_software-dumb_text_viewer.desktop")
    assert container.file(
        "/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg"
    ).startswith(b"<svg")


def test_poetry():
    self = polycotylus.OpenSUSE(polycotylus.Project.from_root(shared.poetry_based))
    self.generate()
    rpms = self.build()
    assert len(rpms) == 4
    container = self.test(rpms["main"])
    assert container["/usr/bin/print_hello"].getmembers()[0].issym()
    python_version = polycotylus.OpenSUSE.python_version().rsplit(".", maxsplit=1)[0]
    script = container.file("/usr/bin/print_hello-" + python_version).decode()
    assert "python" + python_version in script.splitlines()[0]
