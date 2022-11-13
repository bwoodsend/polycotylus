import io
import subprocess
import platform
import tarfile
import re

from PIL import Image
import pyzstd

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._arch import Arch
from tests import dumb_text_viewer, cross_distribution, ubrotli, silly_name

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


def test_dumb_text_viewer():
    self = Arch(Project.from_root(dumb_text_viewer))
    self.generate()

    pkgbuild = self.pkgbuild()
    assert pkgbuild.startswith(pkgbuild_prefix)

    subprocess.run(["bash", str(self.distro_root / "PKGBUILD")], check=True)
    sysroot = self.distro_root / "pkg/dumb-text-viewer"
    package = self.build()

    site_packages = next(
        (sysroot / "usr/lib/").glob("python3.*")) / "site-packages"
    pycache = site_packages / "dumb_text_viewer/__pycache__"
    pyc_contents = {i: i.read_bytes() for i in pycache.iterdir()}
    assert len(pyc_contents) == 2

    for size in [16, 24, 128]:
        path = sysroot / f"usr/share/icons/hicolor/{size}x{size}/apps/underwhelming_software-dumb_text_viewer.png"
        assert path.exists()
        png = Image.open(path)
        assert png.size == (size, size)
        assert png.getpixel((0, 0))[3] == 0

    container = self.test(package)
    installed = container.commit()

    with mirror:
        script = "bash -c 'pacman -S --noconfirm python-pip && pip show dumb_text_viewer'"
        assert "Name: dumb-text-viewer" in _docker.run(installed, script).output
    info = _docker.run(installed, "pacman -Q --info dumb-text-viewer").output
    assert "Brénainn" in re.search("Packager *: *(.*)", info)[1]

    with container[pycache.relative_to(sysroot)] as tar:
        for pyc in pyc_contents:
            with tar.extractfile("__pycache__/" + pyc.name) as f:
                assert pyc_contents[pyc] == f.read()
        assert len(tar.getmembers()) == 3


def test_ubrotli():
    self = Arch(Project.from_root(ubrotli))
    self.generate()
    assert "arch=(x86_64)" in self.pkgbuild()

    package = self.build()
    raw = pyzstd.decompress(package.read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert f"arch = {platform.machine()}" in pkginfo

    self.test(package)


def test_silly_named_package():
    self = Arch(Project.from_root(silly_name))
    self.generate()
    package = self.build()
    installed = self.test(package).commit()
    script = "pacman -Q --info python-99---s1lly-name--packag3"
    container = _docker.run(installed, script)
    assert re.search(r"""Description *: 🚀 🦄 "quoted" 'quoted again' \$\$\$""",
                     container.output)
