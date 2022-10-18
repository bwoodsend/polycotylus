import gzip
from pathlib import Path
import shutil

import pytest

from polycotylus._project import Project, expand_pip_requirements
from polycotylus._exceptions import PolycotylusYAMLParseError
from tests import dumb_text_viewer


def test_tar_reproducibility():
    """Verify that the tar archive really is gzip-compressed and that gzip's
    and tars timestamps are zeroed."""
    self = Project.from_root(dumb_text_viewer)
    self.write_desktop_files()
    gzip.decompress(self.tar())
    assert self.tar() == self.tar()
    old = self.tar()
    self.write_desktop_files()
    assert self.tar() == old


def test_expand_pip_requirements():
    assert list(expand_pip_requirements("numpy", ".")) == ["numpy"]

    root = Path(__file__,
                "../mock-packages/complex-test-requirements").resolve()
    self = Project.from_root(root)
    assert self.test_dependencies["pip"] == [
        "pyperclip", "numpy", "humanize", "soup", "cake", "hippo", "feet",
        "socks", "haggis"
    ]


def test_yaml_error(tmp_path):
    toml = Path(__file__, "../mock-packages/bare-minimum/pyproject.toml")
    shutil.copy(toml.resolve(), tmp_path)
    polycotylus_yaml = tmp_path / "polycotylus.yaml"
    polycotylus_yaml.write_text("""
source_url: https://xyz
desktop_entry_points:
  socks:
    Exec:
gui: true
""")
    with pytest.raises(PolycotylusYAMLParseError) as capture:
        Project.from_root(tmp_path)
    assert str(capture.value) == f"""\
Invalid polycotylus.yaml:
  In "{polycotylus_yaml}", line 3
        Exec: ''
    ^ (line: 4)
Required key(s) 'Name' not found while parsing a mapping.
"""
