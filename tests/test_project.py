import gzip
from pathlib import Path
import shutil

import toml
import pytest

from polycotylus._project import Project, expand_pip_requirements, \
    check_maintainer
from polycotylus._exceptions import PolycotylusYAMLParseError, \
    AmbiguousLicenseError, NoLicenseSpecifierError, PolycotylusUsageError
from tests import dumb_text_viewer, bare_minimum


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
    shutil.copy(bare_minimum / "pyproject.toml", tmp_path)
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


def test_minimal_configuration(tmp_path):
    shutil.copy(bare_minimum / "pyproject.toml", tmp_path)
    for contents in ["", "\n", "  \n   \n # hello \n\n", "\n\n---\n\n"]:
        (tmp_path / "polycotylus.yaml").write_text(contents)
        Project.from_root(tmp_path)


def test_dockerignore(tmp_path):
    shutil.copy(bare_minimum / "pyproject.toml", tmp_path)
    (tmp_path / "polycotylus.yaml").write_bytes(b"")
    self = Project.from_root(tmp_path)
    path = tmp_path / ".dockerignore"

    self.write_dockerignore()
    assert path.read_bytes() == b".polycotylus\n"

    path.write_bytes(b"foo\nbar")
    self.write_dockerignore()
    assert path.read_bytes() == b"foo\nbar\n.polycotylus\n"

    path.write_bytes(b"\n\nfoo\nbar\n\n\n")
    self.write_dockerignore()
    assert path.read_bytes() == b"\n\nfoo\nbar\n.polycotylus\n"

    path.write_bytes(b"foo\n.polycotylus\nbar\n")
    old = path.stat()
    self.write_dockerignore()
    assert path.stat() == old


def test_license_handling(tmp_path):
    for path in ["pyproject.toml", "polycotylus.yaml", "LICENSE"]:
        shutil.copy(bare_minimum / path, tmp_path / path)

    pyproject_toml = tmp_path / "pyproject.toml"
    options = toml.load(pyproject_toml)

    def _write_trove(trove):
        options["project"]["classifiers"] = [trove]
        pyproject_toml.write_text(toml.dumps(options))

    self = Project.from_root(tmp_path)
    assert self.license_names == ["MIT"]

    # No meaningful license identifier.
    _write_trove("License :: DFSG approved")
    with pytest.raises(NoLicenseSpecifierError, match=".* add it"):
        Project.from_root(tmp_path)

    # Ambiguous license identifier.
    _write_trove("License :: OSI Approved :: Apache Software License")
    with pytest.raises(
            AmbiguousLicenseError, match=r".*classifier 'License :: OSI Approved :: Apache Software License' could .* codes \['Apache-1.0', 'Apache-1.1', 'Apache-2.0'\]\. "
            "Either .* as:\n    spdx:\n      - Apache-2.0:\n"):
        Project.from_root(tmp_path)

    yaml = tmp_path / "polycotylus.yaml"
    yaml.write_text(yaml.read_text() + "spdx:\n  kittens:\n")
    self = Project.from_root(tmp_path)
    assert self.license_names == ["kittens"]


def test_check_maintainer():
    for name in ["Bob", "Theodore", "Brett Alex"]:
        check_maintainer(name)
    for name in ["Bob and contributors", "The NumPy development team",
                 "Poncy Titles Inc."]:
        with pytest.raises(PolycotylusUsageError):
            check_maintainer(name)


def test_maintainer(tmp_path):
    for path in ["pyproject.toml", "polycotylus.yaml", "LICENSE"]:
        shutil.copy(bare_minimum / path, tmp_path / path)

    pyproject_toml = tmp_path / "pyproject.toml"
    polycotylus_yaml = tmp_path / "polycotylus.yaml"
    options = toml.load(pyproject_toml)
    self = Project.from_root(tmp_path)
    assert self.maintainer_slug == "Brénainn Woodsend <bwoodsend@gmail.com>"

    options["project"]["maintainers"] = [dict(name="Sausage Roll",
                                              email="s.roll@pastries.com")]
    pyproject_toml.write_text(toml.dumps(options))
    self = Project.from_root(tmp_path)
    assert self.maintainer_slug == "Sausage Roll <s.roll@pastries.com>"

    del options["project"]["maintainers"]
    del options["project"]["authors"]
    pyproject_toml.write_text(toml.dumps(options))
    with pytest.raises(PolycotylusUsageError, match="exactly one"):
        self = Project.from_root(tmp_path)

    options["project"]["authors"] = [dict(name="bob", email="bob@mail.com"),
                                     dict(name="foo", email="foo@mail.com")]
    pyproject_toml.write_text(toml.dumps(options))
    with pytest.raises(PolycotylusUsageError, match="exactly one"):
        self = Project.from_root(tmp_path)

    options["project"]["maintainer"] = [dict(name="Bob and his friends",
                                             email="some@mailing-list.com")]
    pyproject_toml.write_text(toml.dumps(options))
    with pytest.raises(PolycotylusUsageError, match=""):
        self = Project.from_root(tmp_path)

    polycotylus_yaml.write_text("maintainer: The maintainers <foo@mail.com>")
    with pytest.raises(PolycotylusUsageError, match="generic"):
        self = Project.from_root(tmp_path)

    polycotylus_yaml.write_text("maintainer: Mr Hippo < hippo@mail.com  > \n")
    self = Project.from_root(tmp_path)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"

    polycotylus_yaml.write_text("maintainer: Mr Hippo<hippo@mail.com>")
    self = Project.from_root(tmp_path)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"
