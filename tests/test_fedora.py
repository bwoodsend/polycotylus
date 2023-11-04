import re
import shlex
import shutil
import subprocess
import platform
import tarfile
import io
import contextlib

import toml
import pytest

from polycotylus import _docker, _exceptions
from polycotylus._project import Project
from polycotylus._fedora import Fedora, Fedora37, Fedora40
from polycotylus.__main__ import cli
import shared

if platform.system() == "Windows":
    pytest.skip("Fedora doesn't work on Windows")


def _check_values_align(spec):
    first, *others = re.finditer(r"^(\w+:( *))(.*)$", spec, flags=re.M)
    assert len(first[2]) >= 2
    for line in others:
        assert len(line[1]) == len(first[1])
        assert len(line[2]) >= 2


def test_pretty_spec():
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    spec = self.spec()
    _check_values_align(spec)
    assert "\n\n\n\n" not in spec


def test_python_extras():
    for (packages, imports) in shared._group_python_extras(Fedora.python_extras):
        _docker.run("fedora:37", f"""
            {Fedora.dnf_config_install}
            dnf install -y {shlex.join(packages)} python3
            python3 -c 'import {", ".join(imports)}'
        """, volumes=Fedora._mounted_caches.fget(None))


def test_python_package():
    packages = [
        Fedora.python_package(i) for i in shared.awkward_pypi_packages
        if i != "zope.deferredimport"]
    script = Fedora.dnf_config_install + "\ndnf install --assumeno " + shlex.join(packages)
    container = _docker.run("fedora:37", script, check=False,
                            volumes=Fedora._mounted_caches.fget(None))
    assert "Operation aborted." in container.output


def test_ubrotli():
    self = Fedora(Project.from_root(shared.ubrotli))
    self.generate()
    (self.distro_root / self.architecture).mkdir(exist_ok=True)
    (self.distro_root / self.architecture / f"python3-ubrotli-0.2.0-1.fc38.{self.architecture}.rpm").write_bytes(b"")
    packages = self.build()
    assert "main" in packages
    assert "debuginfo" in packages
    assert "debugsource" in packages
    self.test(packages["main"])


@pytest.mark.parametrize("Fedora", [Fedora37, Fedora40])
def test_dumb_text_viewer(Fedora):
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    container = self.test(self.build()["main"])
    shared.check_dumb_text_viewer_installation(container, b"#! /usr/bin/python3")
    container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_png_source_icon(tmp_path, polycotylus_yaml):
    _raw = Project.from_root(shared.dumb_text_viewer).tar()
    with tarfile.open("", "r", io.BytesIO(_raw)) as tar:
        tar.extractall(tmp_path, filter=tarfile.data_filter)
    config = (shared.dumb_text_viewer / "polycotylus.yaml").read_text("utf-8")
    config = config.replace("icon-source.svg", "dumb_text_viewer/icon.png")
    config = re.sub(".*pink-mode.svg", "", config)
    subprocess.run(["git", "init", str(tmp_path / "dumb_text_viewer-0.1.0")])
    polycotylus_yaml(config)
    self = Fedora(Project.from_root(tmp_path / "dumb_text_viewer-0.1.0"))
    self.generate()
    assert "svg" not in self.spec()
    container = self.test(self.build()["main"])
    container.file("/usr/share/icons/hicolor/24x24/apps/underwhelming_software-dumb_text_viewer.png")
    with pytest.raises(Exception):
        container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_kitchen_sink(monkeypatch):
    with contextlib.suppress(FileNotFoundError):
        (shared.kitchen_sink / ".polycotylus/artifacts.json").unlink()
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = Fedora(Project.from_root(shared.kitchen_sink))
    self.generate()
    assert "certifi" not in self.spec()
    assert "setuptools" not in self.spec()
    assert "colorama" not in self.spec()
    rpms = self.build()
    rpm = rpms["main"]
    self.test(rpm)
    self.update_artifacts_json(rpms)

    (self.distro_root / "noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.2-1.fc37.noarch.rpm").touch()

    self = Fedora37(Project.from_root(shared.kitchen_sink))
    rpms37 = self.build()
    rpm37 = rpms37["main"]
    self.test(rpm37)
    self.update_artifacts_json(rpms37)

    assert rpm.exists()
    assert rpm != rpm37

    assert (shared.kitchen_sink / ".polycotylus/artifacts.json").read_bytes() == b"""\
[
  {
    "distribution": "fedora",
    "tag": "37",
    "architecture": "noarch",
    "variant": "main",
    "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3-1.fc37.noarch.rpm"
  },
  {
    "distribution": "fedora",
    "tag": "39",
    "architecture": "noarch",
    "variant": "main",
    "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3-1.fc39.noarch.rpm"
  }
]"""


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

    with pytest.raises(SystemExit, match='^Error: Architecture "ppc64le" '):
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
