import re
import shlex
import shutil
import subprocess
import platform
import tarfile
import io
import contextlib
import time

import toml
import pytest

from polycotylus import _docker, _exceptions, _misc
from polycotylus._project import Project
from polycotylus._fedora import Fedora, Fedora37, Fedora40, Fedora41, Fedora43
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


# Cover oldest, latest and both sides of the transition made from 40->41
@pytest.mark.parametrize("Fedora", [Fedora37, Fedora40, Fedora41, Fedora43])
def test_dnf_cache(Fedora):
    mounts = Fedora._mounted_caches
    before = time.time()
    _docker.run(Fedora.base_image, f"""
        find /var/cache -name 'libretls*.rpm' -exec rm {{}} \\;
        {Fedora.dnf_config_install}
        dnf install --refresh -y libretls
    """, volumes=mounts)
    changed_files = []
    for (source, _) in mounts:
        changed_files += [i.name for i in source.rglob("*") if i.stat().st_mtime > before]
    assert changed_files
    assert [i for i in changed_files if i.endswith(".xml.zck")]
    assert [i for i in changed_files if i.endswith(".rpm")]
    time.sleep(3)


def test_pretty_spec():
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    spec = self.spec()
    _check_values_align(spec)
    assert "\n\n\n\n" not in spec


def test_python_extras():
    for (packages, imports) in shared._group_python_extras(Fedora.python_extras):
        _docker.run(Fedora.base_image, f"""
            {Fedora.dnf_config_install}
            dnf install -y {shlex.join(packages)} python3
            python3 -c 'import {", ".join(imports)}'
        """, volumes=Fedora._mounted_caches)


def test_python_package():
    packages = [
        Fedora.python_package(i) for i in shared.awkward_pypi_packages
        if i != "zope.deferredimport"]
    script = Fedora.dnf_config_install + "\ndnf install --assumeno " + shlex.join(packages)
    container = _docker.run(Fedora.base_image, script, check=False,
                            volumes=Fedora._mounted_caches)
    assert "Operation aborted" in container.output


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


@pytest.mark.parametrize("Fedora", [Fedora37, Fedora43])
def test_dumb_text_viewer(Fedora):
    self = Fedora(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    container = self.test(self.build()["main"])
    shared.check_dumb_text_viewer_installation(container, b"#! /usr/bin/python3")
    container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_png_source_icon(tmp_path, polycotylus_yaml):
    _raw = Project.from_root(shared.dumb_text_viewer).tar()
    with tarfile.open("", "r", io.BytesIO(_raw)) as tar:
        _misc.tar_extract_all(tar, tmp_path)
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
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
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

    assert rpm.path.exists()
    assert rpm.path != rpm37.path

    assert (shared.kitchen_sink / ".polycotylus/artifacts.json").read_bytes() == b"""\
[
  {
    "distribution": "fedora",
    "tag": "37",
    "architecture": "noarch",
    "package_type": "main",
    "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc37.noarch.rpm",
    "signature_path": null
  },
  {
    "distribution": "fedora",
    "tag": "42",
    "architecture": "noarch",
    "package_type": "main",
    "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc42.noarch.rpm",
    "signature_path": null
  }
]"""


def test_test_command(polycotylus_yaml):
    dependencies = "dependencies:\n  test:\n    pip: pytest\n"

    polycotylus_yaml(dependencies)
    spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    assert "%check\n%pytest\n\n" in spec
    spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()
    assert "%check\nxvfb-run %{python3} -m pytest\n\n" in spec

    polycotylus_yaml(dependencies + "test_command: +python+ -c 'print(10)'")
    spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    assert "%check\n%{python3} -c 'print(10)'\n\n" in spec
    with pytest.raises(_exceptions.PolycotylusUsageError, match="implicit"):
        spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()

    polycotylus_yaml(dependencies + "test_command: +python+ -c 'print(10)'\ngui: true")
    with pytest.raises(_exceptions.PolycotylusUsageError, match="specified"):
        spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()

    polycotylus_yaml(dependencies + "test_command: pytest")
    with pytest.raises(_exceptions.PolycotylusUsageError) as capture:
        spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    message = str(capture.value)[str(capture.value).rfind("The"):]
    shared.snapshot_test(message, "no-test-command-placeholder")

    polycotylus_yaml(dependencies + "test_command: xvfb-run +python+ -c 'print(10)'")
    spec = Fedora(Project.from_root(shared.dumb_text_viewer)).spec()
    assert "%check\nxvfb-run %{python3} -c 'print(10)'\n\n" in spec

    polycotylus_yaml(dependencies + "test_command: |\n  +python+\n    \t\n\n  foo\n\n  bar")
    spec = Fedora(Project.from_root(shared.bare_minimum)).spec()
    assert "%check\n%{python3}\n\nfoo\n\nbar\n\n" in spec


def test_cli_signing(monkeypatch, capsys, force_color):
    monkeypatch.chdir(shared.dumb_text_viewer)
    cli(["fedora"])
    capture = capsys.readouterr()
    assert "Built 1 artifact" in capture.out

    monkeypatch.chdir(shared.ubrotli)
    monkeypatch.setenv("GNUPGHOME", str(shared.gpg_home))
    artifacts = cli(["fedora:", "--gpg-signing-id=ED7C694736BC74B3"])
    capture = capsys.readouterr()
    assert "Built 3 artifacts" in capture.out

    rpm_info = _docker.run(Fedora.base_image,
                           ["rpm", "-qpi"] + ["/io/" + i.path.name for i in artifacts.values()],
                           volumes=[(artifacts["main"].path.parent, "/io")]).output
    assert rpm_info.count("ED7C694736BC74B3".lower()) == 3


def test_cli_invalid(monkeypatch, force_color):
    monkeypatch.chdir(shared.ubrotli)

    with pytest.raises(SystemExit) as capture:
        cli(["fedora", "--architecture=ppc64le"])
    shared.snapshot_test(str(capture.value), "invalid-architecture")

    with pytest.raises(SystemExit) as capture:
        cli(["fedora:bog"])
    shared.snapshot_test(str(capture.value), "invalid-tag")

    with pytest.raises(SystemExit) as capture:
        cli(["fluff"])
    shared.snapshot_test(str(capture.value), "invalid-distribution")

    with pytest.raises(SystemExit) as capture:
        cli(["fluff:bog"])
    shared.snapshot_test(str(capture.value), "invalid-distribution")


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
    pyproject["tool"]["poetry"]["dependencies"].pop("snowballstemmer")

    (tmp_path / "pyproject.toml").write_text(toml.dumps(pyproject))
    self = Fedora(Project.from_root(tmp_path))
    self.generate()
    self.test(self.build()["main"])


def test_unittest():
    self = Fedora(Project.from_root(shared.bare_minimum))
    self.generate()
    self.test(self.build()["main"])


def test_hatchling():
    self = Fedora(Project.from_root(shared.hatchling_based))
    self.generate()
    packages = self.build()
    self.test(packages["main"])
