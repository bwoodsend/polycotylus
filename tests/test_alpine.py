import subprocess
from pathlib import Path
import platform
import tarfile
import shutil
import re

import pytest
import toml

from polycotylus import _docker, _exceptions
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._alpine import Alpine
from tests import dumb_text_viewer, ubrotli, cross_distribution, silly_name, \
    bare_minimum

mirror = mirrors["alpine"]


class TestCommon(cross_distribution.Base):
    cls = Alpine
    base_image = Alpine.base
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
    self.generate()
    _docker.run(Alpine.base, f"""
        {mirror.install}
        apk add -q atools
        apkbuild-lint /io/APKBUILD
    """, volumes=[(self.distro_root, "/io")])


def test_dumb_text_viewer():
    self = Alpine(Project.from_root(dumb_text_viewer))
    self.generate()
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)
    assert "arch=noarch" in self.apkbuild()
    assert "gcc" not in self.apkbuild()

    _docker.run(Alpine.base, ["ash", "-c", "set -e; source /io/APKBUILD"],
                volumes=[(self.distro_root, "/io")])
    apks = self.build()
    assert len(apks) == 1
    apk = apks["main"]

    with tarfile.open(apk) as tar:
        files = tar.getnames()
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = noarch" in pkginfo
        assert "license = MIT" in pkginfo
    assert "usr/share/icons/hicolor/128x128/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/icons/hicolor/32x32/apps/underwhelming_software-dumb_text_viewer.png" in files
    assert "usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg" in files
    assert "usr/share/applications/underwhelming_software-dumb_text_viewer.desktop" in files
    for file in files:
        assert "LICENSE" not in file

    container = self.test(apk)
    installed = container.commit()

    with mirror:
        script = "apk add py3-pip && pip show dumb_text_viewer"
        assert "Name: dumb-text-viewer" in _docker.run(installed, script).output

        assert _docker.run(installed, """
            apk add -q xdg-utils shared-mime-info
            xdg-mime query default text/plain
        """).output.strip() == "underwhelming_software-dumb_text_viewer.desktop"


def test_ubrotli():
    self = Alpine(Project.from_root(ubrotli))
    self.generate()
    assert "arch=all" in self.apkbuild()

    apks = self.build()
    with tarfile.open(apks["main"]) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
            assert "LICENSE" not in file
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert f"arch = {platform.machine()}" in pkginfo
        assert "license = Apache-2.0" in pkginfo
    assert len(apks) == 1
    self.test(apks["main"])


def test_license_handling(tmp_path):
    subprocess.run(["git", "-C", tmp_path, "init"])
    (tmp_path / "tests").mkdir()
    for path in [
            "pyproject.toml", "polycotylus.yaml", "LICENSE", "bare_minimum.py",
            "tests/test_bare_minimum.py"
    ]:
        shutil.copy(bare_minimum / path, tmp_path / path)

    pyproject_toml = tmp_path / "pyproject.toml"
    options = toml.load(pyproject_toml)

    def _write_trove(trove):
        options["project"]["classifiers"] = [trove]
        pyproject_toml.write_text(toml.dumps(options))

    # An SPDX recognised, OSI approved license.
    _write_trove("License :: OSI Approved :: MIT License")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    assert "doc" not in apks
    with tarfile.open(apks["main"]) as tar:
        for file in tar.getnames():
            assert "LICENSE" not in file
        with tar.extractfile(".PKGINFO") as f:
            assert "license = MIT" in f.read().decode()

    # An SPDX recognised, but not OSI approved license.
    _write_trove("License :: Aladdin Free Public License (AFPL)")
    (tmp_path / "LICENSE").write_text("Aladdin license here.")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    with tarfile.open(apks["main"]) as tar:
        for file in tar.getnames():
            assert "LICENSE" not in file
        with tar.extractfile(".PKGINFO") as f:
            assert re.search("license = (.+)", f.read().decode())[1] == "custom"
    with tarfile.open(apks["doc"]) as tar:
        path = "usr/share/licenses/py3-bare-minimum/LICENSE"
        assert path in tar.getnames()
        with tar.extractfile(path) as f:
            assert f.read() == b"Aladdin license here."

    # Something made up.
    (tmp_path / "LICENSE").write_text(
        "You may use this software as long as you are nice to kittens.")
    yaml = tmp_path / "polycotylus.yaml"
    yaml.write_text(yaml.read_text() + "spdx:\n  kittens:\n")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    with tarfile.open(apks["main"]) as tar:
        with tar.extractfile(".PKGINFO") as f:
            assert re.search("license = (.+)", f.read().decode())[1] == "custom"
    with tarfile.open(apks["doc"]) as tar:
        path = "usr/share/licenses/py3-bare-minimum/LICENSE"
        assert path in tar.getnames()
        with tar.extractfile(path) as f:
            assert f.read().endswith(b"kittens.")


def test_silly_named_package():
    self = Alpine(Project.from_root(silly_name))
    self.generate()
    apks = self.build()
    installed = self.test(apks["main"]).commit()
    script = "apk info -a py3-99---s1lly---name---packag3--x--y--z"
    container = _docker.run(installed, script)
    assert """🚀 🦄 "quoted" 'quoted again' $$$""" in container.output
    assert "license:\ncustom" in container.output

    with tarfile.open(apks["doc"]) as tar:
        path = "usr/share/licenses/py3-99---s1lly---name---packag3--x--y--z/The license file"
        assert path in tar.getnames()
        with tar.extractfile(path) as f:
            assert "🦄" in f.read().decode()
