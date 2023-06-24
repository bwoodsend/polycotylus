import tarfile
import io
import os

import pyzstd

from polycotylus._project import Project
from polycotylus._void import Void
import shared


class TestCommon(shared.Base):
    cls = Void
    base_image = "ghcr.io/void-linux/void-linux:latest-mini-x86_64-musl"
    package_install = "xbps-install -ySu xbps"


def test_ubrotli():
    self = Void(Project.from_root(shared.ubrotli))
    self.generate()
    self.test(self.build()["main"])
    for path in self.distro_root.rglob("*:*"):
        assert 0, f"{path} will break Windows file systems"
    assert os.listdir(self.void_packages_repo()) == [".git"]


def test_dumb_text_viewer():
    self = Void(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    shared.check_dumb_text_viewer_installation(self.test(self.build()["main"]),
                                               icon_sizes=(16, 48, 256))


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text("utf-8")
    polycotylus_yaml(
        original.replace("icon-source.svg", "dumb_text_viewer/icon.png"))
    self = Void(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert "svg" not in self.template()
    packages = self.build()
    raw = pyzstd.decompress(packages["main"].read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        files = tar.getnames()
    for file in files:
        assert ".svg" not in file


def test_silly_named_package(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = Void(Project.from_root(shared.silly_name))
    self.generate()
    self.test(self.build()["main"])


def test_poetry():
    self = Void(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])
