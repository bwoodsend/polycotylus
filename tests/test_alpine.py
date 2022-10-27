import subprocess
from pathlib import Path
import platform
import tarfile

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._alpine import Alpine
from tests import dumb_text_viewer, ubrotli, cross_distribution

mirror = mirrors["alpine"]


class TestCommon(cross_distribution.Base):
    cls = Alpine
    base_image = "alpine"
    package_install = "apk add"


def test_key_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    self = Alpine(Project.from_root(dumb_text_viewer))
    self.project.maintainer = "Mr Cake"
    self.project.email = "foo@bar.com"
    public, private = self.abuild_keys()
    assert public.name.startswith("foo@bar")
    assert public.name.endswith(".rsa.pub")
    assert "BEGIN PUBLIC" in public.read_text()
    assert "BEGIN PRIVATE" in private.read_text()

    assert (public, private) == self.abuild_keys()

    config = Path.home() / ".abuild/abuild.conf"
    config.write_text("eggs=foo")
    assert self.abuild_keys() != (public, private)
    assert config.read_text().startswith("eggs=foo\nPACKAGER_PRIVKEY=")


@mirror.decorate
def test_abuild_lint():
    self = Alpine(Project.from_root(dumb_text_viewer))
    self.generate(clean=True)
    _docker.run(
        "alpine", f"""
        {mirror.install}
        apk add -q atools
        apkbuild-lint /io/APKBUILD
    """, volumes=[(self.distro_root, "/io")])


def test_dumb_text_viewer():
    self = Alpine(Project.from_root(dumb_text_viewer))
    self.generate(clean=True)
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)
    assert "arch=noarch" in self.pkgbuild()

    _docker.run("alpine", ["ash", "-c", "set -e; source /io/APKBUILD"],
                volumes=[(self.distro_root, "/io")])
    apk = self.build()

    with tarfile.open(apk) as tar:
        files = tar.getnames()
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = noarch" in pkginfo
    assert "usr/share/icons/hicolor/128x128/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/icons/hicolor/32x32/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/applications/underwhelming_software-dumb_text_viewer.desktop" in files

    container = self.test(apk)
    installed = container.commit()

    with mirror:
        script = "apk add py3-pip && pip show dumb_text_viewer"
        assert "Name: dumb-text-viewer" in _docker.run(installed, script).output

        assert _docker.run(
            installed, """
            apk add -q xdg-utils shared-mime-info
            xdg-mime query default text/plain
        """).output.strip() == "underwhelming_software-dumb_text_viewer.desktop"


def test_ubrotli():
    self = Alpine(Project.from_root(ubrotli))
    self.generate(clean=True)
    assert "arch=all" in self.pkgbuild()

    apk = self.build()
    with tarfile.open(apk) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert f"arch = {platform.machine()}" in pkginfo

    self.test(apk)
