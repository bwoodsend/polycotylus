import subprocess
from pathlib import Path
import tarfile
import shutil
import re
import platform

import toml
import pytest

from polycotylus import _docker, _exceptions, machine
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._alpine import Alpine, Alpine317
import shared

mirror = mirrors["alpine"]


class TestCommon(shared.Base):
    cls = Alpine
    base_image = Alpine.image
    package_install = "apk add"


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
        _docker.run(Alpine.image, f"""
            {mirror.install}
            apk add -q atools
            apkbuild-lint /io/APKBUILD
        """, volumes=[(self.distro_root, "/io")])


def test_dumb_text_viewer():
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    subprocess.run(["sh", str(self.distro_root / "APKBUILD")], check=True)
    assert "arch=noarch" in self.apkbuild()
    assert "gcc" not in self.apkbuild()

    _docker.run(Alpine.image, ["ash", "-c", "set -e; source /io/APKBUILD"],
                volumes=[(self.distro_root, "/io")])
    apks = self.build()
    assert len(apks) == 2
    assert "pyc" in apks
    apk = apks["main"]

    with tarfile.open(apk) as tar:
        files = tar.getnames()
        with tar.extractfile(".PKGINFO") as f:
            pkginfo = f.read().decode()
        assert "arch = noarch" in pkginfo
        assert "license = MIT" in pkginfo
    for file in files:
        assert "LICENSE" not in file

    container = self.test(apk)
    shared.check_dumb_text_viewer_installation(container)
    installed = container.commit()

    with mirror:
        script = "sudo apk add py3-pip && pip show dumb_text_viewer"
        assert "Name: dumb-text-viewer" in _docker.run(installed, script).output

        assert _docker.run(installed, """
            sudo apk add -q xdg-utils shared-mime-info
            xdg-mime query default text/plain
        """).output.strip() == "underwhelming_software-dumb_text_viewer.desktop"


def test_png_source_icon(polycotylus_yaml):
    original = (shared.dumb_text_viewer / "polycotylus.yaml").read_text("utf-8")
    polycotylus_yaml(re.sub("(icon-source|pink-mode).svg",
                            "dumb_text_viewer/icon.png", original))
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    assert "svg" not in self.apkbuild()
    apks = self.build()
    with tarfile.open(apks["main"]) as tar:
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
    with tarfile.open(apks["main"]) as tar:
        for file in tar.getnames():
            assert ".desktop" not in file
            assert ".png" not in file
            assert "LICENSE" not in file
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


def test_unknown_package(polycotylus_yaml):
    polycotylus_yaml("""
        dependencies:
            test:
                pip: Hippos_can_fly
    """)
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match="Dependency \"Hippos_can_fly\" is not .* on Alpine Linux. "
                       ".* submit Hippos_can_fly to Alpine Linux\'s package"):
        self.apkbuild()
    polycotylus_yaml("""
        dependencies:
            test:
                pip: python_Hippos_can_fly
    """)
    self = Alpine(Project.from_root(shared.dumb_text_viewer))
    with pytest.raises(_exceptions.PolycotylusUsageError, match="python_Hippos_can_fly"):
        self.apkbuild()


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
    yaml.write_text(yaml.read_text("utf-8") + "spdx:\n  kittens:\n")
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


def test_silly_named_package(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3")
    all_apks = []
    for _Alpine in (Alpine, Alpine317):
        self = _Alpine(Project.from_root(shared.silly_name))
        self.generate()
        assert "pywin32-ctypes" not in self.apkbuild()
        assert "colorama" in self.apkbuild()
        apks = self.build()
        installed = self.test(apks["main"]).commit()
        script = "apk info -a py3-99---s1lly---name---packag3--x--y--z"
        container = _docker.run(installed, script)
        assert """🚀 🦄 "quoted" 'quoted again' $$$""" in container.output
        assert "license:\ncustom" in container.output
        assert ("pyc" in apks) is (_Alpine is Alpine)
        all_apks.extend(apks.values())

        with tarfile.open(apks["doc"]) as tar:
            path = "usr/share/licenses/py3-99---s1lly---name---packag3--x--y--z/The license file"
            assert path in tar.getnames()
            with tar.extractfile(path) as f:
                assert "🦄" in f.read().decode()

    for apk in all_apks:
        assert apk.exists()
    assert len(set(all_apks)) == 5


test_multiarch = shared.qemu(Alpine)


def test_architecture_errors(monkeypatch):
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match='Architecture "donkey" is not available on Alpine Linux.'):
        Alpine(Project.from_root(shared.ubrotli), "donkey")

    monkeypatch.setattr(shutil, "which", lambda x: None)
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    with pytest.raises(_exceptions.PolycotylusUsageError,
                       match='Emulating "aarch64" requires the "qemu-aarch64-static" command'):
        Alpine(Project.from_root(shared.ubrotli), "aarch64")


def test_fussy_arch():
    self = Alpine(Project.from_root(shared.fussy_arch))
    assert "\narch='aarch64 ppc64le'\n" in self.apkbuild()


def test_poetry():
    self = Alpine(Project.from_root(shared.poetry_based))
    self.generate()
    self.test(self.build()["main"])
