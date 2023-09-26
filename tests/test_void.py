import tarfile
import io
import os
import re

import pyzstd

from polycotylus._project import Project
from polycotylus._void import Void, VoidMusl
import shared


class TestCommon(shared.Base):
    cls = Void
    base_image = Void.image
    package_install = "xbps-install -ySu xbps"


def test_ubrotli():
    self = VoidMusl(Project.from_root(shared.ubrotli))
    self.generate()
    native_xbps = self.build()["main"]
    self.test(native_xbps)
    for path in self.distro_root.rglob("*:*"):
        assert 0, f"{path} will break Windows file systems"
    assert os.listdir(self.void_packages_repo()) == [".git"]
    native_builder = self

    self = Void(Project.from_root(shared.ubrotli))
    self.generate()
    glibc_xbps = self.build()["main"]
    self.test(glibc_xbps)
    glibc_builder = self

    assert native_xbps.exists()
    assert glibc_xbps.exists()
    native_builder.test(native_xbps)
    glibc_builder.test(glibc_xbps)


def test_dumb_text_viewer():
    self = VoidMusl(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    shared.check_dumb_text_viewer_installation(self.test(self.build()["main"]),
                                               icon_sizes=(16, 48, 256))


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text("utf-8")
    polycotylus_yaml(re.sub("(icon-source|pink-mode).svg",
                            "dumb_text_viewer/icon.png", original))
    self = VoidMusl(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert "svg" not in self.template()
    packages = self.build()
    raw = pyzstd.decompress(packages["main"].read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        files = tar.getnames()
    for file in files:
        assert ".svg" not in file


def test_kitchen_sink(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = VoidMusl(Project.from_root(shared.kitchen_sink))
    self.generate()
    self.test(self.build()["main"])


def test_poetry():
    self = VoidMusl(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])
