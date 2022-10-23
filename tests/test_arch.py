import os
import subprocess
import sys

from PIL import Image

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._arch import Arch
from tests import dumb_text_viewer, cross_distribution

mirror = mirrors["arch"]

pkgbuild_prefix = """\
# Maintainer: Brénainn Woodsend <bwoodsend@gmail.com>
pkgname=dumb-text-viewer
pkgver=0.1.0
pkgrel=1
pkgdesc='A small example GUI package'
arch=(any)
url=https://github.com/me/blah
license=(MIT)
"""


class TestCommon(cross_distribution.Base):
    cls = Arch
    base_image = "archlinux"
    package_install = "pacman -Sy --noconfirm"


@mirror.decorate
def test_build():
    self = Arch(Project.from_root(dumb_text_viewer))
    self.generate(clean=True)

    pkgbuild = self.pkgbuild()
    assert pkgbuild.startswith(pkgbuild_prefix)

    subprocess.run(["sh", str(self.distro_root / "PKGBUILD")], check=True)
    sysroot = self.distro_root / "pkg/dumb-text-viewer"
    package = self.build()

    site_packages = next(
        (sysroot / "usr/lib/").glob("python3.*")) / "site-packages"
    pycache = site_packages / "dumb_text_viewer/__pycache__"
    pyc_contents = {i: i.read_bytes() for i in pycache.iterdir()}
    assert len(pyc_contents) == 2
    subprocess.run([sys.executable, "-c", "import dumb_text_viewer"], env={
        **os.environ, "PYTHONPATH": str(site_packages)
    })
    assert pyc_contents == {
        i: i.read_bytes()
        for i in (site_packages / "dumb_text_viewer/__pycache__").iterdir()
    }

    for size in [16, 24, 128]:
        path = sysroot / f"usr/share/icons/hicolor/{size}x{size}/apps/underwhelming_software-dumb_text_viewer.png"
        assert path.exists()
        png = Image.open(path)
        assert png.size == (size, size)
        assert png.getpixel((0, 0))[3] == 0

    container = self.test(package)
    installed = container.commit()

    command = "bash -c 'pacman -S --noconfirm python-pip && pip show dumb_text_viewer'"
    assert "Name: dumb-text-viewer" in _docker.run(installed, command).output

    with container[pycache.relative_to(sysroot)] as tar:
        for pyc in pyc_contents:
            with tar.extractfile("__pycache__/" + pyc.name) as f:
                assert pyc_contents[pyc] == f.read()
        assert len(tar.getmembers()) == 3
