import subprocess
import tarfile
import io

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


def test_dumb_text_viewer():
    self = Void(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    shared.check_dumb_text_viewer_installation(self.test(self.build()["main"]),
                                               icon_sizes=(16, 48, 256))


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text()
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
    # Mimic the local cache of the void-packages repo being out of date so that
    # some dependencies will no longer be available.
    self = Void(Project.from_root(shared.silly_name))
    cache = self.void_packages_repo()
    hash = "f9bf46d6376a467b5f7dc21018f7a6dc9e6a3f2b"
    for command in [["fetch", "--depth=1", "https://github.com/void-linux/void-packages", hash],
                    ["reset", "--hard"], ["checkout", hash]]:
        subprocess.run(["git", "-C", str(cache)] + command, check=True)

    self.generate()
    self.test(self.build()["main"])

    assert hash not in subprocess.run(["git", "-C", str(cache), "log", "-n1"], check=True, stdout=subprocess.PIPE, text=True).stdout


def test_poetry():
    self = Void(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])
