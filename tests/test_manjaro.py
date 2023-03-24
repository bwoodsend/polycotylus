import contextlib

from polycotylus._project import Project
from polycotylus._manjaro import Manjaro
from polycotylus import _docker
from polycotylus._mirror import cache_root, _manjaro_preferred_mirror
import shared


class TestCommon(shared.Base):
    cls = Manjaro
    base_image = "manjarolinux/base"
    package_install = "pacman -Sy --needed --noconfirm"


def test_dumb_text_viewer():
    self = Manjaro(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    self.test(self.build()["main"])


def test_mirror_detection():
    with contextlib.suppress(FileNotFoundError):
        (cache_root / "manjaro-mirror").unlink()
    with Manjaro.mirror:
        for architecture in ["x86_64", "aarch64"]:
            _docker.run("manjarolinux/base", f"""
                {Manjaro.mirror.install}
                pacman -Sy
            """, architecture=architecture, tty=True)
    assert _manjaro_preferred_mirror() == _manjaro_preferred_mirror()


test_multiarch = shared.qemu(Manjaro)


def test_fussy_arch():
    self = Manjaro(Project.from_root(shared.fussy_arch))
    assert "\narch=(aarch64)\n" in self.pkgbuild()
