import subprocess
from pathlib import Path
import tarfile
import shutil
import re
import platform
import json
import contextlib

import toml
import pytest

from polycotylus import _docker, _exceptions, machine
from polycotylus._project import Project
from polycotylus._alpine import Alpine, Alpine317, Alpine318, Alpine319, AlpineEdge
import shared


class TestCommon(shared.Base):
    cls = Alpine
    package_install = "apk upgrade && apk add"


class TestCommon317(TestCommon):
    cls = Alpine317


class TestCommonEdge(TestCommon):
    cls = AlpineEdge


def test_key_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    self.project.maintainer = "Mr Cake"
    self.project.email = "foo@bar.com"
    public, private = self.abuild_keys()
    assert public.name.startswith("foo@bar")
    assert public.name.endswith(".rsa.pub")
    assert "BEGIN PUBLIC" in public.read_text("utf-8")
    assert "BEGIN PRIVATE" in private.read_text("utf-8")

    assert (public, private) == self.abuild_keys()

    config = Path.home() / ".abuild/abuild.conf"
    config.write_text("eggs=foo")
    assert self.abuild_keys() != (public, private)
    assert config.read_text().startswith("eggs=foo\nPACKAGER_PRIVKEY=")


def test_abuild_lint():
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    with self.mirror:
        _docker.run(Alpine.base_image, f"""
            {self.mirror.install_command}
            apk add -q atools
            apkbuild-lint /io/APKBUILD
        """, volumes=[(self.distro_root, "/io")], architecture=self.docker_architecture)


def test_test_command(polycotylus_yaml):
    dependencies = "dependencies:\n  test:\n    pip: pytest\n"

    polycotylus_yaml(dependencies)
    apkbuild = Alpine(Project.from_root(shared.bare_minimum)).apkbuild()
    assert re.search("\tPYTHONPATH=.*pytest", apkbuild)

    polycotylus_yaml(dependencies + "test_command: |\n  +foo+\n    bar\n")
    apkbuild = Alpine(Project.from_root(shared.bare_minimum)).apkbuild()
    assert "\texport PYTHONPATH" in apkbuild
    assert "\tfoo\n\t\tbar\n" in apkbuild

    polycotylus_yaml(dependencies + "test_command: +foo+ && bar")
    apkbuild = Alpine(Project.from_root(shared.bare_minimum)).apkbuild()
    assert "\texport PYTHONPATH" in apkbuild
    assert "\tfoo && bar\n" in apkbuild

    polycotylus_yaml(dependencies + "test_command:\n")
    apkbuild = Alpine(Project.from_root(shared.bare_minimum)).apkbuild()
    assert "\tpytest" not in apkbuild


def test_dumb_text_viewer():
    extraneous_desktop_file = shared.dumb_text_viewer / ".polycotylus" / "delete-me.desktop"
    extraneous_desktop_file.write_bytes(b"")
    self = AlpineEdge(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert not extraneous_desktop_file.exists()
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)
    assert "arch=noarch" in self.apkbuild()
    assert "gcc" not in self.apkbuild()

    _docker.run(AlpineEdge.base_image, ["ash", "-c", "set -e; source /io/APKBUILD"],
                volumes=[(self.distro_root, "/io")], architecture=self.docker_architecture)
    apks = self.build()
    assert len(apks) == 3
    assert "pyc" in apks
    assert "doc" in apks
    apk = apks["main"]

    with tarfile.open(apk.path) as tar:
        files = tar.getnames()
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = noarch" in pkginfo
        assert "license = MIT" in pkginfo
    for file in files:
        assert not re.search("usr/share/.*/LICENSE", file)

    container = self.test(apk)
    shared.check_dumb_text_viewer_installation(container)
    installed = container.commit()

    with self.mirror:
        script = "sudo apk add py3-pip && pip show dumb_text_viewer"
        assert "Name: dumb_text_viewer" in _docker.run(
            installed, script, architecture=self.docker_architecture).output

        assert _docker.run(installed, """
            sudo apk add -q xdg-utils shared-mime-info
            xdg-mime query default text/plain
        """, architecture=self.docker_architecture).output.strip() == "underwhelming_software-dumb_text_viewer.desktop"


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text("utf-8")
    polycotylus_yaml(re.sub("(icon-source|pink-mode).svg",
                            "dumb_text_viewer/icon.png", original))
    self = Alpine317(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert "svg" not in self.apkbuild()
    apks = self.build()
    with tarfile.open(apks["main"].path) as tar:
        files = tar.getnames()
    for file in files:
        assert ".svg" not in file


def test_not_a_git_repo_error(tmp_path):
    for file in ["pyproject.toml", "polycotylus.yaml", "LICENSE"]:
        shutil.copy(shared.bare_minimum / file, tmp_path)
    with pytest.raises(_exceptions.PolycotylusUsageError, match="git"):
        Alpine(Project.from_root(tmp_path)).generate()


def test_ubrotli():
    self = Alpine(Project.from_root(shared.ubrotli))
    self.generate()
    assert "arch=all" in self.apkbuild()
    assert "-m compile" not in self.apkbuild()
    assert "$pkgname-pyc" not in self.apkbuild()

    apks = self.build()
    with tarfile.open(apks["main"].path) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
            assert not re.search("usr/share/.*/LICENSE", file)
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert f"arch = {machine()}" in pkginfo
        assert "license = Apache-2.0" in pkginfo
    assert len(apks) == 1
    self.test(apks["main"])


def test_user_privilege_escalation():
    self = Alpine(Project.from_root(shared.ubrotli))
    self.generate()
    base = self.build_builder_image()

    user = _docker.run(base, ["whoami"], root=False).output.strip()
    assert user == "user"

    # sudo should not require a password.
    user = _docker.run(base, ["sudo", "whoami"], root=False).output.strip()
    assert user == "root"


def test_unknown_package(polycotylus_yaml, force_color):
    polycotylus_yaml("""
        dependencies:
            test:
                pip: Hippos_can_fly
    """)
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    with pytest.raises(_exceptions.PolycotylusUsageError) as capture:
        self.apkbuild()
    shared.snapshot_test(str(capture.value), "unavailable-package")
    polycotylus_yaml("""
        dependencies:
            test:
                pip: python_Hippos_can_fly
    """)
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    with pytest.raises(_exceptions.PolycotylusUsageError, match="python_Hippos_can_fly"):
        self.apkbuild()


def test_license_info():
    self = Alpine(Project.from_root(shared.bare_minimum))

    self.project.license_spdx = "MIT"
    assert self._license_info() == (True, False)
    assert "license=MIT" in self.apkbuild()
    assert "pkgdir-doc/usr/share/licenses" in self.apkbuild()
    assert 'subpackages="$pkgname-pyc $pkgname-doc"' in self.apkbuild()

    self.project.license_spdx = "(0BSD OR GPL-3.0+) AND Jam WITH SHL-2.1"
    assert self._license_info() == (True, True)
    assert "license='(0BSD OR GPL-3.0+) AND Jam WITH SHL-2.1'" in self.apkbuild()
    assert "pkgdir-doc" not in self.apkbuild()
    assert "pkgname-doc" not in self.apkbuild()

    self.project.license_spdx = "0BSD OR bagpuss AND Jam"
    assert self._license_info() == (False, False)
    assert "license=custom" in self.apkbuild()
    assert "pkgdir-doc/usr/share/licenses" in self.apkbuild()
    assert 'subpackages="$pkgname-pyc $pkgname-doc"' in self.apkbuild()

    self.project.license_spdx = "Jam with bagpuss"
    assert self._license_info() == (False, False)


def test_license_handling(tmp_path):
    subprocess.run(["git", "-C", tmp_path, "init"])
    (tmp_path / "tests").mkdir()
    for path in [
            "pyproject.toml", "polycotylus.yaml", "LICENSE", "bare_minimum.py",
            "tests/test_bare_minimum.py"
    ]:
        shutil.copy(shared.bare_minimum / path, tmp_path / path)

    pyproject_toml = tmp_path / "pyproject.toml"
    options = toml.load(pyproject_toml)

    def _write_trove(trove):
        options["project"]["classifiers"] = [trove]
        pyproject_toml.write_text(toml.dumps(options), "utf-8")

    # An SPDX recognised, OSI approved license.
    _write_trove("License :: OSI Approved :: MirOS License (MirOS)")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    assert "doc" not in apks
    with tarfile.open(apks["main"].path) as tar:
        for file in tar.getnames():
            assert not re.search("usr/share/.*/LICENSE", file)
        with tar.extractfile(".PKGINFO") as f:
            assert "license = MirOS" in f.read().decode()

    # An SPDX recognised, but not OSI approved license.
    _write_trove("License :: Aladdin Free Public License (AFPL)")
    (tmp_path / "LICENSE").write_text("Aladdin license here.")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    with tarfile.open(apks["main"].path) as tar:
        for file in tar.getnames():
            assert not re.search("usr/share/.*/LICENSE", file)
        with tar.extractfile(".PKGINFO") as f:
            assert re.search("license = (.+)", f.read().decode())[1] == "custom"
    with tarfile.open(apks["doc"].path) as tar:
        path = "usr/share/licenses/py3-bare-minimum/LICENSE"
        assert path in tar.getnames()
        with tar.extractfile(path) as f:
            assert f.read() == b"Aladdin license here."

    # Something made up.
    (tmp_path / "LICENSE").write_text(
        "You may use this software as long as you are nice to kittens.")
    yaml = tmp_path / "polycotylus.yaml"
    yaml.write_text(yaml.read_text("utf-8") + "license: kittens\n")
    self = Alpine(Project.from_root(tmp_path))
    self.generate()
    apks = self.build()
    with tarfile.open(apks["main"].path) as tar:
        with tar.extractfile(".PKGINFO") as f:
            assert re.search("license = (.+)", f.read().decode())[1] == "custom"
    with tarfile.open(apks["doc"].path) as tar:
        path = "usr/share/licenses/py3-bare-minimum/LICENSE"
        assert path in tar.getnames()
        with tar.extractfile(path) as f:
            assert f.read().endswith(b"kittens.")


def test_kitchen_sink(monkeypatch):
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(shared.kitchen_sink / ".polycotylus/fedora/noarch")
    (shared.kitchen_sink / ".polycotylus/fedora/noarch").mkdir(exist_ok=True, parents=True)
    (shared.kitchen_sink / ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc38.noarch.rpm").touch()
    (shared.kitchen_sink / ".polycotylus/artifacts.json").write_text(json.dumps([
        {
            "distribution": "fedora",
            "tag": "38",
            "architecture": "noarch",
            "package_type": "main",
            "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc38.noarch.rpm"
        }, {
            "distribution": "alpine",
            "tag": "3.17",
            "architecture": Alpine.preferred_architecture,
            "package_type": "main",
            "path": ".polycotylus/alpine/3.17/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk"
        }, {
            "distribution": "fedora",
            "tag": "39",
            "architecture": "noarch",
            "package_type": "main",
            "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc39.noarch.rpm"
        },
    ]))

    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
    all_apks = []
    for _Alpine in (Alpine, Alpine317, Alpine318, Alpine319, AlpineEdge):
        self = _Alpine(Project.from_root(shared.kitchen_sink))
        self.generate()
        assert "pywin32-ctypes" not in self.apkbuild()
        assert "colorama" in self.apkbuild()
        apks = self.build()
        installed = self.test(apks["main"]).commit()
        script = "apk info -a py3-99---s1lly---name---packag3--x--y--z"
        container = _docker.run(installed, script)
        assert """🚀 🦄 "quoted" 'quoted again' $$$""" in container.output
        assert "license:\ncustom" in container.output
        assert ("pyc" in apks) is (_Alpine is not Alpine317)
        all_apks.extend(apks.values())
        self.update_artifacts_json(apks)

        with tarfile.open(apks["doc"].path) as tar:
            path = "usr/share/licenses/py3-99---s1lly---name---packag3--x--y--z/The license file"
            assert path in tar.getnames()
            with tar.extractfile(path) as f:
                assert "🦄" in f.read().decode()

    for apk in all_apks:
        assert apk.path.exists()
    assert len(set(i.path for i in all_apks)) == 14

    assert json.loads((shared.kitchen_sink / ".polycotylus/artifacts.json").read_bytes()) == [
        {
            "distribution": "alpine",
            "tag": "3.17",
            "architecture": "x86_64",
            "package_type": "doc",
            "path": ".polycotylus/alpine/3.17/x86_64/py3-99---s1lly---name---packag3--x--y--z-doc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.17",
            "architecture": "x86_64",
            "package_type": "main",
            "path": ".polycotylus/alpine/3.17/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.18",
            "architecture": "x86_64",
            "package_type": "doc",
            "path": ".polycotylus/alpine/3.18/x86_64/py3-99---s1lly---name---packag3--x--y--z-doc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.18",
            "architecture": "x86_64",
            "package_type": "main",
            "path": ".polycotylus/alpine/3.18/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.18",
            "architecture": "x86_64",
            "package_type": "pyc",
            "path": ".polycotylus/alpine/3.18/x86_64/py3-99---s1lly---name---packag3--x--y--z-pyc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.19",
            "architecture": "x86_64",
            "package_type": "doc",
            "path": ".polycotylus/alpine/3.19/x86_64/py3-99---s1lly---name---packag3--x--y--z-doc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.19",
            "architecture": "x86_64",
            "package_type": "main",
            "path": ".polycotylus/alpine/3.19/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.19",
            "architecture": "x86_64",
            "package_type": "pyc",
            "path": ".polycotylus/alpine/3.19/x86_64/py3-99---s1lly---name---packag3--x--y--z-pyc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.23",
            "architecture": "x86_64",
            "package_type": "doc",
            "path": ".polycotylus/alpine/3.23/x86_64/py3-99---s1lly---name---packag3--x--y--z-doc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.23",
            "architecture": "x86_64",
            "package_type": "main",
            "path": ".polycotylus/alpine/3.23/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "3.23",
            "architecture": "x86_64",
            "package_type": "pyc",
            "path": ".polycotylus/alpine/3.23/x86_64/py3-99---s1lly---name---packag3--x--y--z-pyc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "edge",
            "architecture": "x86_64",
            "package_type": "doc",
            "path": ".polycotylus/alpine/edge/x86_64/py3-99---s1lly---name---packag3--x--y--z-doc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "edge",
            "architecture": "x86_64",
            "package_type": "main",
            "path": ".polycotylus/alpine/edge/x86_64/py3-99---s1lly---name---packag3--x--y--z-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "alpine",
            "tag": "edge",
            "architecture": "x86_64",
            "package_type": "pyc",
            "path": ".polycotylus/alpine/edge/x86_64/py3-99---s1lly---name---packag3--x--y--z-pyc-1.2.3.4-r1.apk",
            "signature_path": None
        }, {
            "distribution": "fedora",
            "tag": "38",
            "architecture": "noarch",
            "package_type": "main",
            "path": ".polycotylus/fedora/noarch/python3-99-s1lly-name-packag3-x-y-z-1.2.3.4-1.fc38.noarch.rpm",
            "signature_path": None
        }
    ]


test_multiarch = shared.qemu(Alpine)


def test_architecture_errors(monkeypatch, no_color):
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match="Unknown architecture 'donkey' for Alpine Linux"):
        Alpine(Project.from_root(shared.ubrotli), "donkey")

    monkeypatch.setattr(shutil, "which", lambda x: None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match="Emulating 'ppc64le' requires the 'qemu-ppc64le-static' command"):
        Alpine(Project.from_root(shared.ubrotli), "ppc64le")


def test_fussy_arch():
    self = Alpine(Project.from_root(shared.fussy_arch))
    assert "\narch='aarch64 ppc64le'\n" in self.apkbuild()


def test_poetry():
    self = Alpine(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])


def test_hatchling(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "10.20")
    self = Alpine(Project.from_root(shared.hatchling_based))
    self.generate()
    apks = self.build()
    self.test(apks["main"])
    assert "doc" not in apks
    with tarfile.open(apks["main"].path) as tar:
        assert b"BlueOak-1.0.0" in tar.extractfile(".PKGINFO").read()
