import subprocess

from polycotylus._project import Project
from polycotylus._void import Void
from tests import dumb_text_viewer, ubrotli, cross_distribution, silly_name


class TestCommon(cross_distribution.Base):
    cls = Void
    base_image = "ghcr.io/void-linux/void-linux:latest-mini-x86_64-musl"
    package_install = "xbps-install -ySu xbps"


def test_ubrotli():
    self = Void(Project.from_root(ubrotli))
    self.generate()
    self.test(self.build()["main"])


def test_dumb_text_viewer():
    self = Void(Project.from_root(dumb_text_viewer))
    self.generate()
    self.test(self.build()["main"])


def test_silly_named_package():
    # Mimic the local cache of the void-packages repo being out of date so that
    # some dependencies will no longer be available.
    self = Void(Project.from_root(silly_name))
    cache = self.void_packages_repo()
    hash = "f9bf46d6376a467b5f7dc21018f7a6dc9e6a3f2b"
    for command in [["fetch", "--depth=1", "https://github.com/void-linux/void-packages", hash],
                    ["reset", "--hard"], ["checkout", hash]]:
        subprocess.run(["git", "-C", str(cache)] + command, check=True)

    self.generate()
    self.test(self.build()["main"])

    assert hash not in subprocess.run(["git", "-C", str(cache), "log", "-n1"], check=True, stdout=subprocess.PIPE, text=True).stdout
