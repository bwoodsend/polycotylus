from polycotylus._project import Project
from polycotylus._manjaro import Manjaro
from tests import dumb_text_viewer, cross_distribution


class TestCommon(cross_distribution.Base):
    cls = Manjaro
    base_image = "manjarolinux/base"
    package_install = "pacman -Sy --needed --noconfirm"


def test_dumb_text_viewer():
    self = Manjaro(Project.from_root(dumb_text_viewer))
    self.generate()
    self.test(self.build()["main"])
