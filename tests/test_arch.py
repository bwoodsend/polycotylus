import os
import subprocess
import shutil
import sys
import io
from tarfile import TarFile

from docker import from_env
from PIL import Image

from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._arch import Arch
from tests import dumb_text_viewer

mirror = mirrors["arch"]

pkgbuild_prefix = """\
# Maintainer: Brénainn Woodsend <bwoodsend@gmail.com>
pkgname=dumb_text_viewer
pkgver=0.1.0
pkgrel=1
pkgdesc='A small example GUI package'
arch=(any)
url=https://github.com/me/blah
license=(MIT)
"""


@mirror.decorate
def test_build():
    self = Arch(Project.from_root(dumb_text_viewer))
    self.generate(clean=True)

    pkgbuild = self.pkgbuild()
    assert pkgbuild.startswith(pkgbuild_prefix)

    subprocess.run(["sh", str(self.distro_root / "PKGBUILD")], check=True)
    sysroot = self.distro_root / "pkg/dumb_text_viewer"
    docker = from_env()
    build, _ = docker.images.build(path=str(self.project.root), target="build",
                                   dockerfile=".polycotylus/arch/Dockerfile",
                                   network_mode="host")
    docker.containers.run(build, "makepkg -fs --noconfirm",
                          volumes=[f"{self.distro_root}:/io"],
                          network_mode="host", remove=True)

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

    test, _ = docker.images.build(path=str(self.project.root), target="test",
                                  network_mode="host",
                                  dockerfile=".polycotylus/arch/Dockerfile")
    command = "bash -c 'pacman -Sy && pacman -U --noconfirm dumb_text_viewer-0.1.0-1-any.pkg.tar.zst'"
    container = docker.containers.run(test, command,
                                      volumes=[f"{self.distro_root}:/io"],
                                      detach=True, network_mode="host")
    assert container.wait()["StatusCode"] == 0, container.logs().decode()
    installed = container.commit()
    container.remove()

    command = "bash -c 'pacman -S --noconfirm python-pip && pip show dumb_text_viewer'"
    output = docker.containers.run(installed, command, network_mode="host",
                                   remove=True).decode()
    assert "Name: dumb-text-viewer" in output

    container = docker.containers.run(installed,
                                      "python -c 'import dumb_text_viewer'",
                                      detach=True, network_mode="host")
    assert container.wait()["StatusCode"] == 0, container.logs().decode()
    raw = b"".join(container.get_archive(pycache.relative_to(sysroot))[0])
    with TarFile("", "r", io.BytesIO(raw)) as tar:
        for pyc in pyc_contents:
            with tar.extractfile("__pycache__/" + pyc.name) as f:
                assert pyc_contents[pyc] == f.read()
        assert len(tar.getmembers()) == 3
    container.remove()

    docker.containers.run(installed, "xvfb-run pytest /io/tests",
                          volumes=[f"{self.project.root}/tests:/io/tests"],
                          remove=True)
