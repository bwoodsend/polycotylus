import io
import subprocess
import platform
import tarfile
import re

from PIL import Image

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._fedora import Fedora
from tests import dumb_text_viewer, cross_distribution, ubrotli, silly_name

mirror = mirrors["arch"]

# ~ class TestCommon(cross_distribution.Base):
    # ~ cls = Fedora
    # ~ base_image = "fedora:37"
    # ~ package_install = "pacman -Sy --noconfirm"


def test_pretty_spec():
    self = Fedora(Project.from_root(dumb_text_viewer))
    spec = self.spec()

    first, *others = re.finditer(r"^(\w+:( *))(.*)$", spec, flags=re.M)
    assert len(first[2]) >= 2
    for line in others:
        assert len(line[1]) == len(first[1])
        assert len(line[2]) >= 2

    assert "\n\n\n\n" not in spec
