import subprocess
import platform
from pathlib import Path
import re

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._alpine import Alpine
from tests import dumb_text_viewer, cross_distribution

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
def test_build():
    self = Alpine(Project.from_root(dumb_text_viewer))
    self.generate(clean=True)
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)

    _docker.run("alpine", ["ash", "-c", "set -e; source /io/APKBUILD"],
                volumes=[(self.distro_root, "/io")])

    build = _docker.build(".polycotylus/alpine/Dockerfile", self.project.root,
                          target="build")
    public_key, private_key = self.abuild_keys()
    _docker.run(
        build, "abuild", volumes=[
            (self.distro_root, "/io"),
            (private_key, f"/home/user/.abuild/{private_key.name}"),
            (self.distro_root / "dist", "/home/user/packages"),
        ])
    apk = self.distro_root / "dist" / platform.machine(
    ) / "dumb-text-viewer-0.1.0-r1.apk"
    assert apk.exists()

    logs = _docker.run("alpine", ["tar", "tf", f"/io/{apk.name}"],
                       volumes=[(apk.parent, "/io")]).output
    files = set(re.findall("[^\n]+", logs))
    assert "usr/share/icons/hicolor/128x128/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/icons/hicolor/32x32/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/applications/underwhelming_software-dumb_text_viewer.desktop" in files

    test = _docker.build(".polycotylus/alpine/Dockerfile", self.project.root,
                         target="test")
    command = f"apk add /pkg/{platform.machine()}/dumb-text-viewer-0.1.0-r1.apk"
    container = _docker.run(
        test, command, volumes=[
            (self.distro_root / "dist", "/pkg"),
            (self.project.root / "tests", "/io/tests"),
        ])
    installed = container.commit()

    command = "apk add py3-pip && pip show dumb_text_viewer"
    assert "Name: dumb-text-viewer" in _docker.run(installed, command).output

    _docker.run(installed, "xvfb-run pytest /io/tests",
                volumes=[(self.project.root / "tests", "/io/tests")])

    assert _docker.run(
        installed, """
        apk add -q xdg-utils shared-mime-info
        xdg-mime query default text/plain
    """).output.strip() == "underwhelming_software-dumb_text_viewer.desktop"
