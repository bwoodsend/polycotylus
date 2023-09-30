import io
import subprocess
import tarfile
import re
import sys
import textwrap
import shutil

import pyzstd

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._arch import Arch
import shared

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


class TestCommon(shared.Base):
    cls = Arch
    # Strictly speaking, the following should be a full system upgrade (-Syu)
    # but that makes the test very slow so instead just upgrade the most
    # troublesome dependency glibc.
    package_install = "pacman -Sy --noconfirm --needed glibc"


def test_dumb_text_viewer():
    self = Arch(Project.from_root(shared.dumb_text_viewer))
    self.generate()

    pkgbuild = self.pkgbuild()
    assert pkgbuild.startswith(pkgbuild_prefix)

    subprocess.run([shutil.which("bash"), str(self.distro_root / "PKGBUILD")], check=True)
    sysroot = self.distro_root / "pkg/dumb-text-viewer"
    package = self.build()["main"]

    site_packages = next(
        (sysroot / "usr/lib/").glob("python3.*")) / "site-packages"
    pycache = site_packages / "dumb_text_viewer/__pycache__"
    pyc_contents = {i: i.read_bytes() for i in pycache.iterdir()}
    assert len(pyc_contents) == 2

    container = self.test(package)
    shared.check_dumb_text_viewer_installation(container)
    installed = container.commit()

    with mirror:
        script = "sudo pacman -S --noconfirm --needed python-pip && pip show dumb_text_viewer"
        assert "Name: dumb-text-viewer" in _docker.run(
            installed, script, architecture=self.docker_architecture).output
    info = _docker.run(installed, "pacman -Q --info dumb-text-viewer",
                       architecture=self.docker_architecture).output
    assert "Brénainn" in re.search("Packager *: *(.*)", info)[1]

    with container[pycache.relative_to(sysroot)] as tar:
        for pyc in pyc_contents:
            with tar.extractfile("__pycache__/" + pyc.name) as f:
                assert pyc_contents[pyc] == f.read()
        assert len(tar.getmembers()) == 3


def test_ubrotli():
    self = Arch(Project.from_root(shared.ubrotli))
    self.generate()
    assert "arch=(x86_64)" in self.pkgbuild()
    self.project.build_dependencies["arch"].append("gcc")
    assert "gcc" not in self.build_dependencies
    assert "gcc" not in self.pkgbuild()

    package = self.build()["main"]
    raw = pyzstd.decompress(package.read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = x86_64" in pkginfo

    self.test(package)


def test_kitchen_sink(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    self = Arch(Project.from_root(shared.kitchen_sink))
    self.generate()
    package = self.build()["main"]
    installed = self.test(package).commit()
    script = "pacman -Q --info python-99---s1lly---name---packag3--x--y--z"
    container = _docker.run(installed, script, architecture=self.docker_architecture)
    assert re.search(r"""Description *: 🚀 🦄 "quoted" 'quoted again' \$\$\$""",
                     container.output)


def test_post_mortem(polycotylus_yaml):
    script = textwrap.dedent("""
        import polycotylus.__main__
        polycotylus._yaml_schema._read_text = lambda x: \"""
            test_command: cat polycotylus.yaml
            dependencies:
                test:
                    pip: pytest
            \"""
        polycotylus.__main__.cli(["arch", "--post-mortem"])
    """)
    post_mortem_script = " && ".join([
        "python -c 'import bare_minimum'",
        "sudo pacman -Syu",
        "pytest",
        "ps -f --no-headers 1",
        "echo Made it!!",
    ])
    p = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, cwd=str(shared.bare_minimum))
    lines = []
    while True:
        assert p.poll() is None, "".join(lines)
        lines.append(p.stdout.readline())
        if "Entering post-mortem debug shell." in lines[-1]:
            assert "pacman" in p.stdout.readline()
            assert ".zst" in p.stdout.readline()
            assert "cat polycotylus.yaml" in p.stdout.readline()
            assert p.stdout.readline().isspace()
            break
    p.stdin.write(post_mortem_script)
    p.stdin.close()
    assert p.wait() == 1
    post_mortem_output = p.stdout.readlines()
    assert post_mortem_output[-1].strip() == "Made it!!"
    assert "/bash" in post_mortem_output[-2]


def test_poetry():
    self = Arch(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])
