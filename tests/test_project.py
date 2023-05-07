import gzip
from pathlib import Path
import shutil
import sys
import subprocess

import toml
import pytest

from polycotylus._project import Project, expand_pip_requirements, \
    check_maintainer
from polycotylus._exceptions import PolycotylusYAMLParseError, \
    AmbiguousLicenseError, NoLicenseSpecifierError, PolycotylusUsageError
from shared import dumb_text_viewer, bare_minimum, poetry_based, silly_name


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


def test_yaml_error(polycotylus_yaml):
    polycotylus_yaml("""
source_url: https://xyz
desktop_entry_points:
  socks:
    Exec:
gui: true
""")
    with pytest.raises(PolycotylusYAMLParseError) as capture:
        Project.from_root(bare_minimum)
    assert str(capture.value) == f"""\
Invalid polycotylus.yaml:
  In "{bare_minimum / "polycotylus.yaml"}", line 3
        Exec: ''
    ^ (line: 4)
Required key(s) 'Name' not found while parsing a mapping.
"""


def test_empty_polycotylus_yaml(tmp_path):
    shutil.copy(bare_minimum / "pyproject.toml", tmp_path)
    shutil.copy(bare_minimum / "LICENSE", tmp_path / "COPYING.txt")
    for contents in ["", "\n", "  \n   \n # hello \n\n", "\n\n---\n\n"]:
        (tmp_path / "polycotylus.yaml").write_text(contents)
        Project.from_root(tmp_path)


def test_dockerignore(tmp_path):
    shutil.copy(bare_minimum / "pyproject.toml", tmp_path)
    shutil.copy(bare_minimum / "LICENSE", tmp_path)
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


def test_license_handling(polycotylus_yaml, pyproject_toml):
    options = toml.load(bare_minimum / "pyproject.toml")

    def _write_trove(trove):
        options["project"]["classifiers"] = [trove]
        pyproject_toml(options)

    self = Project.from_root(bare_minimum)
    assert self.license_names == ["MIT"]

    # No meaningful license identifier.
    _write_trove("License :: DFSG approved")
    with pytest.raises(NoLicenseSpecifierError, match=".* add it"):
        Project.from_root(bare_minimum)

    # Ambiguous license identifier.
    _write_trove("License :: OSI Approved :: Apache Software License")
    with pytest.raises(
            AmbiguousLicenseError, match=r".*classifier 'License :: OSI Approved :: Apache Software License' could .* codes \['Apache-1.0', 'Apache-1.1', 'Apache-2.0'\]\. "
            "Either .* as:\n    spdx:\n      - Apache-2.0:\n"):
        Project.from_root(bare_minimum)

    polycotylus_yaml("spdx:\n  kittens:\n")
    self = Project.from_root(bare_minimum)
    assert self.license_names == ["kittens"]


def test_check_maintainer():
    for name in ["Bob", "Theodore", "Brett Alex"]:
        check_maintainer(name)
    for name in ["Bob and contributors", "The NumPy development team",
                 "Poncy Titles Inc."]:
        with pytest.raises(PolycotylusUsageError):
            check_maintainer(name)


def test_missing_pyproject_metadata(tmp_path):
    shutil.copy(bare_minimum / "polycotylus.yaml", tmp_path)
    (tmp_path / "pyproject.toml").write_text("""
        [project]

        authors = [
            { name="Brénainn Woodsend", email="bwoodsend@gmail.com" },
        ]

        classifiers = [
            "License :: OSI Approved :: MIT License",
        ]
    """)
    with pytest.raises(PolycotylusUsageError) as error:
        Project.from_root(tmp_path)
    assert str(error.value) == """\
Missing pyproject.toml fields ['description', 'license', 'name', 'urls', 'version']. Add or migrate them to the pyproject.toml.

    [project]
    name = "your_package_name"
    version = "1.2.3"
    description = "Give a one-line description of your package here"

    [project.urls]
    homepage = "https://your.project.site"

    [project.license]
    file = "LICENSE.txt"

They cannot be dynamic."""


def test_missing_config_files(tmp_path):
    with pytest.raises(PolycotylusUsageError, match="No pyproject.toml found"):
        Project.from_root(tmp_path)
    (tmp_path / "pyproject.toml").write_text("")
    with pytest.raises(PolycotylusUsageError, match="Missing polycotylus.yaml"):
        Project.from_root(tmp_path)


def test_missing_poetry_metadata(pyproject_toml):
    pyproject = toml.load(poetry_based / "pyproject.toml")
    pyproject["tool"]["poetry"].pop("license")
    pyproject_toml(pyproject)
    with pytest.raises(PolycotylusUsageError) as error:
        Project.from_root(poetry_based)
    error.match('Field "license" is missing from poetry\'s .* '
                'See https://python-poetry.org/docs/pyproject/#license for what to set it to.')


def test_maintainer(pyproject_toml, polycotylus_yaml):

    options = toml.load(bare_minimum / "pyproject.toml")
    self = Project.from_root(bare_minimum)
    assert self.maintainer_slug == "Brénainn Woodsend <bwoodsend@gmail.com>"

    options["project"]["maintainers"] = [dict(name="Sausage Roll",
                                              email="s.roll@pastries.com")]
    pyproject_toml(options)
    self = Project.from_root(bare_minimum)
    assert self.maintainer_slug == "Sausage Roll <s.roll@pastries.com>"

    del options["project"]["maintainers"]
    del options["project"]["authors"]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError, match="No maintainer declared"):
        self = Project.from_root(bare_minimum)

    options["project"]["authors"] = [dict(name="bob", email="bob@mail.com"),
                                     dict(name="foo", email="foo@mail.com")]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError, match="exactly one"):
        self = Project.from_root(bare_minimum)

    options["project"]["maintainer"] = [dict(name="Bob and his friends",
                                             email="some@mailing-list.com")]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError, match=""):
        self = Project.from_root(bare_minimum)

    polycotylus_yaml("maintainer: The maintainers <foo@mail.com>")
    with pytest.raises(PolycotylusUsageError, match="generic"):
        self = Project.from_root(bare_minimum)

    polycotylus_yaml("maintainer: Mr Hippo < hippo@mail.com  > \n")
    self = Project.from_root(bare_minimum)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"

    polycotylus_yaml("maintainer: Mr Hippo<hippo@mail.com>")
    self = Project.from_root(bare_minimum)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"


def test_missing_setuptools_scm(monkeypatch):
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)
    with pytest.raises(PolycotylusUsageError, match="install setuptools-scm"):
        Project.from_root(silly_name)


def test_setuptools_scm(tmp_path, polycotylus_yaml, pyproject_toml):
    (tmp_path / "LICENSE").write_bytes(b"hello")
    subprocess.run(["sh", "-ec", """
        git init
        git add .
        git config --local user.email "you@example.com"
        git config --local user.name "Your Name"
        git commit -m "Blah blah blah"
        git tag v9.3
    """], check=True, cwd=str(tmp_path))
    (tmp_path / "LICENSE").write_bytes(b"feet")
    (tmp_path / "bar").write_bytes(b"")
    polycotylus_yaml("")
    pyproject_toml("""
        [project]
        name = "..."
        description = "..."
        dynamic = ["version"]
        maintainers = [{name="...", email="x@email.com"}]
        classifiers = ["License :: OSI Approved :: MIT License"]

        [project.urls]
        homepage = "..."

        [tool.setuptools_scm]
    """)
    self = Project.from_root(tmp_path)
    assert self.version == "9.3"
