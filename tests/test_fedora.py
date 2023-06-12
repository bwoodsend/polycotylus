import re
import shlex
import shutil
import subprocess

import toml
import pytest

from polycotylus import _docker, _exceptions
from polycotylus._project import Project
from polycotylus._fedora import Fedora
from polycotylus.__main__ import cli
import shared


def test_pretty_spec():
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    spec = self.spec()

    first, *others = re.finditer(r"^(\w+:( *))(.*)$", spec, flags=re.M)
    assert len(first[2]) >= 2
    for line in others:
        assert len(line[1]) == len(first[1])
        assert len(line[2]) >= 2

    assert "\n\n\n\n" not in spec


def test_python_extras():
    for (packages, imports) in shared._group_python_extras(Fedora.python_extras):
        _docker.run("fedora:37", f"""
            {Fedora.dnf_config_install}
            yum install -y {shlex.join(packages)} python3
            python3 -c 'import {", ".join(imports)}'
        """, volumes=Fedora._mounted_caches.fget(None))


def test_python_package():
    packages = [
        Fedora.python_package(i) for i in shared.awkward_pypi_packages
        if i != "zope.deferredimport"]
    script = Fedora.dnf_config_install + "\nyum install --assumeno " + shlex.join(packages)
    container = _docker.run("fedora:37", script, check=False,
                            volumes=Fedora._mounted_caches.fget(None))
    assert "Operation aborted." in container.output


def test_ubrotli():
    self = Fedora(Project.from_root(shared.ubrotli))
    self.generate()
    (self.distro_root / self.architecture).mkdir(exist_ok=True)
    (self.distro_root / self.architecture / f"python3-ubrotli-0.2.0-1.fc37.{self.architecture}.rpm").write_bytes(b"")
    packages = self.build()
    assert "main" in packages
    assert "debuginfo" in packages
    assert "debugsource" in packages
    self.test(packages["main"])


def test_dumb_text_viewer():
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    container = self.test(self.build()["main"])
    shared.check_dumb_text_viewer_installation(container, b"#! /usr/bin/python3")
    container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text()
    polycotylus_yaml(
        original.replace("icon-source.svg", "dumb_text_viewer/icon.png"))
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert "svg" not in self.spec()
    container = self.test(self.build()["main"])
    container.file("/usr/share/icons/hicolor/24x24/apps/underwhelming_software-dumb_text_viewer.png")
    with pytest.raises(Exception):
        container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_silly_named_package(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = Fedora(Project.from_root(shared.silly_name))
    self.generate()
    assert "certifi" not in self.spec()
    assert "setuptools" not in self.spec()
    assert "colorama" not in self.spec()
    self.test(self.build()["main"])


def test_test_command(polycotylus_yaml):
    dependencies = "dependencies:\n  test:\n    pip: pytest\n"

    polycotylus_yaml(dependencies)
    spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    assert "%global __pytest" not in spec
    spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()
    assert "%global __pytest /usr/bin/xvfb-run %{python3} -m pytest" in spec

    polycotylus_yaml(dependencies + "test_command: python3 -c 'print(10)'")
    spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    assert "%global __pytest %{python3} -c 'print(10)'" in spec
    with pytest.raises(_exceptions.PolycotylusUsageError, match="implicit"):
        spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()

    polycotylus_yaml(dependencies + "test_command: python3 -c 'print(10)'\ngui: true")
    with pytest.raises(_exceptions.PolycotylusUsageError, match="specified"):
        spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()

    polycotylus_yaml(dependencies + "test_command: xvfb-run python3 -c 'print(10)'")
    spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()
    assert "%global __pytest /usr/bin/xvfb-run %{python3} -c 'print(10)'" in spec


def test_cli(monkeypatch, capsys):
    monkeypatch.chdir(shared.dumb_text_viewer)
    cli(["fedora"])
    capture = capsys.readouterr()
    assert "Built 1 artifact:\n" in capture.out

    monkeypatch.chdir(shared.ubrotli)
    cli(["fedora"])
    capture = capsys.readouterr()
    assert "Built 3 artifacts:\n" in capture.out

    with pytest.raises(SystemExit, match='^Architecture "ppc64le" '):
        cli(["fedora", "--architecture=ppc64le"])


def test_poetry(tmp_path):
    # Fedora turns optional dependencies into mandatory ones. This is wrong but
    # can't be fixed by polycotylus so remove them from the test and pretend all
    # is wonderful.
    (tmp_path / "poetry_based").mkdir(exist_ok=True)
    files = [
        ".dockerignore", "LICENSE", "README.md", "poetry.lock",
        "poetry_based/__init__.py", "poetry_based/__main__.py",
        "polycotylus.yaml", "pytest.ini", "test_poetry_based.py",
    ]
    for path in files:
        shutil.copyfile(shared.poetry_based / path, tmp_path / path)
    subprocess.run(["git", "init"], cwd=tmp_path)
    pyproject = toml.load(str(shared.poetry_based / "pyproject.toml"))
    pyproject["tool"]["poetry"]["dependencies"].pop("toml")
    pyproject["tool"]["poetry"]["dependencies"].pop("filelock")

    (tmp_path / "pyproject.toml").write_text(toml.dumps(pyproject))
    self = Fedora(Project.from_root(tmp_path))
    self.generate()
    self.test(self.build()["main"])


def test_unittest():
    self = Fedora(Project.from_root(shared.bare_minimum))
    self.generate()
    self.test(self.build()["main"])
