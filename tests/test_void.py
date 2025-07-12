import tarfile
import io
import os
import re
from pathlib import Path
import contextlib

import pytest
import pyzstd

from polycotylus._exceptions import PolycotylusUsageError
from polycotylus._project import Project
from polycotylus._void import Void, VoidMusl
import shared


class TestCommon(shared.Base):
    cls = Void
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

    assert native_xbps.path.exists()
    assert glibc_xbps.path.exists()
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
    raw = pyzstd.decompress(packages["main"].path.read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        files = tar.getnames()
    for file in files:
        assert ".svg" not in file


def test_kitchen_sink(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
    self = VoidMusl(Project.from_root(shared.kitchen_sink))
    self.generate()
    packages = self.build()
    self.test(packages["main"])
    self.update_artifacts_json(packages)


def test_signing_poetry(monkeypatch, tmp_path):
    with contextlib.suppress(FileNotFoundError):
        (shared.poetry_based / ".polycotylus/void/musl/python3-poetry-based-0.1.0_1.x86_64-musl.xbps.sig2").unlink()
    import polycotylus.__main__
    keys = Path(__file__).with_name("void-keys").resolve()
    monkeypatch.chdir(shared.poetry_based)
    polycotylus.__main__.cli(["void:musl", "--void-signing-certificate", str(keys / "unencrypted-ssl.pem")])
    repodata = shared.poetry_based / f".polycotylus/void/musl/{Void.preferred_architecture}-musl-repodata"
    with tarfile.open("", "r", io.BytesIO(pyzstd.decompress(repodata.read_bytes()))) as tar:
        with tar.extractfile("index-meta.plist") as f:
            signing_info = f.read()
    assert b"rsa" in signing_info
    assert (shared.poetry_based / ".polycotylus/void/musl/python3-poetry-based-0.1.0_1.x86_64-musl.xbps.sig2").exists()

    self = VoidMusl(Project.from_root(shared.poetry_based))
    for key in keys.glob("*.pem"):
        self.private_key = key

    with pytest.raises(PolycotylusUsageError,
                       match=r'.*an IsADirectoryError\(\) whilst .* file ".*void-keys"'):
        self.private_key = keys

    broken_permissions = tmp_path / "foo"
    broken_permissions.touch()
    broken_permissions.chmod(0)
    with pytest.raises(PolycotylusUsageError, match="PermissionError"):
        self.private_key = broken_permissions

    for name in ("pgp", "pgp-armor", "unencrypted-ssh.pem.pub"):
        with pytest.raises(PolycotylusUsageError, match="Invalid"):
            self.private_key = keys / name
