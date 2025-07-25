import json
import contextlib
import shutil
import subprocess

import pytest

import polycotylus
from polycotylus._project import Project
import shared


class TestCommon(shared.Base):
    cls = polycotylus.Ubuntu
    package_install = "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends"


@pytest.mark.parametrize("Ubuntu", [polycotylus.Ubuntu2410, polycotylus.Ubuntu2510])
def test_dumb_text_viewer(tmp_path, Ubuntu):
    for file in [
        "LICENSE",
        "MANIFEST.in",
        "README.md",
        "dumb_text_viewer/__init__.py",
        "dumb_text_viewer/__main__.py",
        "dumb_text_viewer/icon.png",
        "icon-source.svg",
        "pink-mode.svg",
        "polycotylus.yaml",
        "pyproject.toml",
        "pytest.ini",
        "test-requirements.txt",
        "tests/some-text.txt",
        "tests/test_ui.py",
    ]:
        (tmp_path / file).parent.mkdir(exist_ok=True)
        shutil.copy(shared.dumb_text_viewer / file, tmp_path / file)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True)
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_bytes(pyproject_toml.read_bytes() + b'[tool.setuptools.packages.find]\ninclude = ["dumb_text_viewer"]\n')

    self = Ubuntu(Project.from_root(tmp_path))
    self.generate()
    packages = self.build()
    assert sorted(packages) == ["main"]
    container = self.test(packages["main"])
    self.update_artifacts_json(packages)
    shared.check_dumb_text_viewer_installation(container)


def test_ubrotli():
    with contextlib.suppress(FileNotFoundError):
        (shared.ubrotli / ".polycotylus/artifacts.json").unlink()

    # Ubuntu's repository layout is different for non amd64 architectures which
    # unfortunately makes it necessary to do an extremely slow qemu platform test.
    for self in [
        polycotylus.Ubuntu2404(Project.from_root(shared.ubrotli), architecture="arm64"),
        polycotylus.Ubuntu2510(Project.from_root(shared.ubrotli), architecture="amd64"),
    ]:
        self.generate()
        artifacts = self.build()
        self.test(artifacts["main"])
        self.update_artifacts_json(artifacts)

    assert json.loads((shared.ubrotli / ".polycotylus/artifacts.json").read_bytes()) == [
        {
            "distribution": "ubuntu",
            "tag": "24.04",
            "architecture": "arm64",
            "package_type": "main",
            "path": ".polycotylus/ubuntu/24.04/python3-ubrotli_0.1.0-1_arm64.deb",
            "signature_path": None,
        },
        {
            "distribution": "ubuntu",
            "tag": "25.10",
            "architecture": "amd64",
            "package_type": "main",
            "path": ".polycotylus/ubuntu/25.10/python3-ubrotli_0.1.0-1_amd64.deb",
            "signature_path": None,
        }
    ]


def test_poetry():
    self = polycotylus.Ubuntu(polycotylus.Project.from_root(shared.poetry_based))
    self.generate()
    packages = self.build()
    self.test(packages["main"])


def test_kitchen_sink(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
    self = polycotylus.Ubuntu(polycotylus.Project.from_root(shared.kitchen_sink))
    self.generate()
    package = self.build()["main"]
    self.test(package)
