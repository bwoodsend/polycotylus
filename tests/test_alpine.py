import os
import subprocess
import shutil
import sys
import io
import platform
from tarfile import TarFile
from pathlib import Path
import re

from docker import from_env
from PIL import Image

from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._alpine import Alpine
from tests import dumb_text_viewer, cross_distribution

mirror = mirrors["alpine"]


class TestCommon(cross_distribution.Base):
    cls = Alpine


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
    docker = from_env()
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)

    docker = from_env()
    docker.containers.run("alpine",
                          ["ash", "-c", "set -e; source /io/APKBUILD"],
                          volumes=[f"{self.distro_root}:/io"], remove=True)

    build, _ = docker.images.build(path=str(self.project.root), target="build",
                                   dockerfile=".polycotylus/alpine/Dockerfile",
                                   network_mode="host")
    public_key, private_key = self.abuild_keys()
    docker.containers.run(
        build, "abuild", network_mode="host", volumes=[
            f"{self.distro_root}:/io",
            f"{private_key}:/home/user/.abuild/{private_key.name}:shared",
            f"{self.distro_root}/dist:/home/user/packages:shared"
        ], remove=True)
    apk = self.distro_root / "dist" / platform.machine(
    ) / "dumb_text_viewer-0.1.0-r1.apk"
    assert apk.exists()

    logs = docker.containers.run("alpine", ["tar", "tf", f"/io/{apk.name}"],
                                 volumes=[f"{apk.parent}:/io"], remove=True)
    files = set(re.findall("[^\n]+", logs.decode()))
    assert "usr/share/icons/hicolor/128x128/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/icons/hicolor/32x32/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/applications/underwhelming_software-dumb_text_viewer.desktop" in files

    test, _ = docker.images.build(path=str(self.project.root), target="test",
                                  network_mode="host",
                                  dockerfile=".polycotylus/alpine/Dockerfile")
    command = f"apk add /pkg/{platform.machine()}/dumb_text_viewer-0.1.0-r1.apk"
    container = docker.containers.run(
        test, ["sh", "-c", command], volumes=[
            f"{self.distro_root}/dist:/pkg",
            f"{self.project.root / 'tests'}:/io/tests"
        ], detach=True, network_mode="host")
    assert container.wait()["StatusCode"] == 0, container.logs().decode()
    installed = container.commit()
    container.remove()

    command = "ash -c 'apk add py3-pip && pip show dumb_text_viewer'"
    output = docker.containers.run(installed, command, network_mode="host",
                                   remove=True).decode()
    assert "Name: dumb-text-viewer" in output

    docker.containers.run(installed, "xvfb-run pytest /io/tests",
                          volumes=[f"{self.project.root}/tests:/io/tests"],
                          remove=True)

    assert docker.containers.run(installed, [
        "ash", "-c", """
        apk add -q xdg-utils shared-mime-info
        xdg-mime query default text/plain
    """
    ], network_mode="host", remove=True).strip(
    ) == b"underwhelming_software-dumb_text_viewer.desktop"
