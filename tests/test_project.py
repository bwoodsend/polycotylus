import gzip

from polycotylus._project import Project
from tests import dumb_text_viewer


def test_tar_reproducibility():
    """Verify that the tar archive really is gzip-compressed and that gzip's
    timestamps are zeroed."""
    self = Project.from_root(dumb_text_viewer)
    gzip.decompress(self.tar())
    assert self.tar() == self.tar()
