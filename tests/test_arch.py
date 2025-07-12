import io
import subprocess
import tarfile
import re
import sys
import textwrap
import shutil

import pyzstd
import pytest

from polycotylus import _docker, _exceptions
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
        assert "Name: dumb_text_viewer" in _docker.run(
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
    raw = pyzstd.decompress(package.path.read_bytes())
    with tarfile.open("", "r", io.BytesIO(raw)) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = x86_64" in pkginfo

    self.test(package)


def test_license_info():
    self = Arch(Project.from_root(shared.bare_minimum))

    self.project.license_spdx = "MIT"
    assert self._license_info() == (["MIT"], False)
    assert "license=(MIT)" in self.pkgbuild()
    assert "$pkgdir/usr/share/licenses" in self.pkgbuild()

    self.project.license_spdx = "(BSL-1.0 OR GPL-3.0+) AND GPL-2.0-only WITH GPL-3.0-linking-source-exception"
    assert self._license_info() == (["BSL-1.0", "GPL-3.0+", "GPL-2.0-only", "GPL-3.0-linking-source-exception"], True)
    assert "license=(BSL-1.0 GPL-3.0+ GPL-2.0-only GPL-3.0-linking-source-exception)" in self.pkgbuild()
    assert "share/licenses" not in self.pkgbuild()

    self.project.license_spdx = "bagpuss AND Jam"
    assert self._license_info() == (["custom:bagpuss", "custom:Jam"], False)
    assert "license=(custom:bagpuss custom:Jam)" in self.pkgbuild()
    assert "$pkgdir/usr/share/licenses" in self.pkgbuild()

    self.project.license_spdx = "LicenseRef-bagpuss"
    assert self._license_info() == (["LicenseRef-bagpuss"], False)
    assert "license=(LicenseRef-bagpuss)" in self.pkgbuild()

    self.project.license_spdx = "GFDL-1.2-only WITH bagpuss-exception"
    assert self._license_info() == (["GFDL-1.2-only", "custom:bagpuss-exception"], False)


def test_kitchen_sink_signing(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
    monkeypatch.setenv("GNUPGHOME", str(shared.gpg_home))
    self = Arch(Project.from_root(shared.kitchen_sink), signature="póĺýĉöţỹùṣ 🎩")
    # Test for encoding surprises such as https://bugs.archlinux.org/task/40805#comment124197
    monkeypatch.setattr(self, "dockerfile", lambda: Arch.dockerfile(self) + "ENV LANG=C\n")
    self.generate()
    packages = self.build()
    package = packages["main"]
    assert package.signature_path.exists()
    installed = self.test(package).commit()
    script = "pacman -Q --info python-99---s1lly---name---packag3--x--y--z"
    container = _docker.run(installed, script, architecture=self.docker_architecture)
    assert re.search(r"""Description *: 🚀 🦄 "quoted" 'quoted again' \$\$\$""",
                     container.output)
    self.update_artifacts_json(packages)
    with self.project.artifacts_database() as artifacts:
        artifact, = (i for i in artifacts if i._identifier == package._identifier)
        assert artifact.path.exists()
        assert artifact.path.is_absolute()
        assert artifact.signature_path.exists()
        assert artifact.signature_path.is_absolute()


def test_signing_id_normalisation(monkeypatch, no_color):
    monkeypatch.setenv("GNUPGHOME", str(shared.gpg_home))
    self = Arch(Project.from_root(shared.bare_minimum))

    self.signing_id = "ED7C694736BC74B3"
    assert self.signing_id == "582A6792B83A333D3B316677ED7C694736BC74B3"
    self.signing_id = "2DD6A735C5B889E7"
    assert self.signing_id == "AD4A871B79599B9DD0F62EBE2DD6A735C5B889E7"
    self.signing_id = "🎩"
    assert self.signing_id == "582A6792B83A333D3B316677ED7C694736BC74B3"
    self.signing_id = "encrypted@example.com"
    assert self.signing_id == "AD4A871B79599B9DD0F62EBE2DD6A735C5B889E7"

    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match="identifier 'example.com' is ambiguous.* any of \\['2DD6A735C5B889E7', 'ED7C694736BC74B3'\\]"):
        self.signing_id = "example.com"
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match="No private GPG key .* fingerprint 'KoЯn'"):
        self.signing_id = "KoЯn"


def test_post_mortem(polycotylus_yaml):
    script = textwrap.dedent("""
        import polycotylus.__main__
        polycotylus._yaml_schema._read_text = lambda x: \"""
            test_command: +python+ -c 'import os; os.stat("polycotylus.yaml")'
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
            assert 'stat("polycotylus.yaml")' in p.stdout.readline()
            assert p.stdout.readline().isspace()
            break
    p.stdin.write(post_mortem_script)
    p.stdin.close()
    assert p.wait() == 1
    post_mortem_output = p.stdout.readlines()
    assert post_mortem_output[-2].strip() == "Made it!!"
    assert "/bash" in post_mortem_output[-3]


def test_poetry():
    self = Arch(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])


def test_cli_with_tags(monkeypatch, force_color):
    from polycotylus.__main__ import cli
    monkeypatch.chdir(shared.dumb_text_viewer)
    with pytest.raises(SystemExit) as capture:
        cli(["arch:frogs"])
    shared.snapshot_test(str(capture.value), "invalid-no-tags")
