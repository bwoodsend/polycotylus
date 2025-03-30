import gzip
from pathlib import Path
import shutil
import sys
import re
import subprocess

import toml
import pytest


from polycotylus._project import Project, expand_pip_requirements, \
    check_maintainer
from polycotylus._exceptions import PolycotylusUsageError, PresubmitCheckError, \
    AmbiguousLicenseError, NoLicenseSpecifierError, PolycotylusYAMLParseError
from polycotylus import _misc
import shared


def test_tar_reproducibility():
    """Verify that the tar archive really is gzip-compressed and that gzip's
    and tars timestamps are zeroed."""
    self = Project.from_root(shared.dumb_text_viewer)
    self.write_desktop_files()
    gzip.decompress(self.tar())
    assert self.tar() == self.tar()
    old = self.tar()
    self.write_desktop_files()
    assert self.tar() == old


def test_expand_pip_requirements():
    assert list(expand_pip_requirements("numpy", ".", "")) == ["numpy"]

    root = Path(__file__,
                "../mock-packages/complex-test-requirements").resolve()
    self = Project.from_root(root)
    assert self.test_dependencies["pip"] == [
        "pyperclip", "numpy", "coverage", "soup", "cake", "hippo", "mypy",
        "feet", "socks", "haggis", "pytest-flake8", "black", "pyflakes"
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
        Project.from_root(shared.bare_minimum)
    assert str(capture.value) == f"""\
Invalid polycotylus.yaml:
  In "{shared.bare_minimum / "polycotylus.yaml"}", line 3
        Exec: ''
    ^ (line: 4)
Required key(s) 'Name' not found while parsing a mapping.
"""


def test_empty_polycotylus_yaml(tmp_path):
    shutil.copy(shared.bare_minimum / "pyproject.toml", tmp_path)
    shutil.copy(shared.bare_minimum / "LICENSE", tmp_path / "COPYING.txt")
    for contents in ["", "\n", "  \n   \n # hello \n\n", "\n\n---\n\n"]:
        (tmp_path / "polycotylus.yaml").write_text(contents)
        Project.from_root(tmp_path)


def test_dockerignore(tmp_path):
    shutil.copy(shared.bare_minimum / "pyproject.toml", tmp_path)
    shutil.copy(shared.bare_minimum / "LICENSE", tmp_path)
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


def test_comments_in_polycotylus_yaml(polycotylus_yaml):
    polycotylus_yaml("""
        dependencies:
            run:
                pip: |
                    # blah de blah
                    numpy
                    pyperclip  # don't eat me!
                      #
                        octopus
                    foo bar # pop
                    # -r some-nonexistent-file.txt

                    shoes
        desktop_entry_points:
            bagpuss:
                Name: hello
                Exec: ...
                MimeType: |
                    # X things
                    x/a;x/b;x/c
                    # Y related things
                    y/a;y/b  # trailing comment
                Categories: |
                    Text editor; thing # not a thing
    """)
    self = Project.from_root(shared.bare_minimum)
    assert self.dependencies["pip"] == ["numpy", "pyperclip", "octopus", "foo", "bar", "shoes"]
    assert "MimeType=x/a;x/b;x/c;y/a;y/b;\n" in self._desktop_file("bagpuss", self.desktop_entry_points["bagpuss"])
    assert "Categories=Text editor;thing;\n" in self._desktop_file("bagpuss", self.desktop_entry_points["bagpuss"])


def test_license_handling(polycotylus_yaml, pyproject_toml, force_color):
    options = toml.load(shared.bare_minimum / "pyproject.toml")

    def _write_trove(trove):
        options["project"]["classifiers"] = [trove]
        pyproject_toml(options)

    self = Project.from_root(shared.bare_minimum)
    assert self.license_names == ["MIT"]

    # No meaningful license identifier.
    _write_trove("License :: DFSG approved")
    with pytest.raises(NoLicenseSpecifierError) as capture:
        Project.from_root(shared.bare_minimum)
    shared.snapshot_test(str(capture.value), "no-license-specifier")

    # Ambiguous license identifier.
    _write_trove("License :: OSI Approved :: Apache Software License")
    with pytest.raises(AmbiguousLicenseError) as capture:
        Project.from_root(shared.bare_minimum)
    shared.snapshot_test(str(capture.value), "ambiguous-trove")

    polycotylus_yaml("spdx:\n  kittens:\n")
    self = Project.from_root(shared.bare_minimum)
    assert self.license_names == ["kittens"]


def test_check_maintainer():
    for name in ["Bob", "Theodore", "Brett Alex"]:
        check_maintainer(name)
    for name in ["Bob and contributors", "The NumPy development team",
                 "Poncy Titles Inc."]:
        with pytest.raises(PresubmitCheckError):
            check_maintainer(name)


def test_missing_pyproject_metadata(tmp_path, force_color):
    shutil.copy(shared.bare_minimum / "polycotylus.yaml", tmp_path)
    _misc.unix_write(tmp_path / "pyproject.toml", """
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
    shared.snapshot_test(str(error.value), "missing-pyproject-metadata")


def test_missing_config_files(tmp_path):
    with pytest.raises(PolycotylusUsageError, match="No pyproject.toml found"):
        Project.from_root(tmp_path)
    (tmp_path / "pyproject.toml").write_text("")
    with pytest.raises(PolycotylusUsageError, match="Missing polycotylus.yaml"):
        Project.from_root(tmp_path)


def test_missing_poetry_metadata(pyproject_toml, force_color):
    pyproject = toml.load(shared.poetry_based / "pyproject.toml")
    pyproject["tool"]["poetry"].pop("license")
    pyproject_toml(pyproject)
    with pytest.raises(PolycotylusUsageError) as capture:
        Project.from_root(shared.poetry_based)
    shared.snapshot_test(str(capture.value), "poetry-missing-metadata")


def test_overcomplicated_versioning(pyproject_toml, no_color):
    pyproject = toml.load(shared.bare_minimum / "pyproject.toml")

    pyproject["project"]["version"] = "10"
    pyproject_toml(pyproject)
    assert Project.from_root(shared.bare_minimum).version == "10"

    pyproject["project"]["version"] = "10.11.12.13"
    pyproject_toml(pyproject)
    assert Project.from_root(shared.bare_minimum).version == "10.11.12.13"

    pyproject["project"]["version"] = "1.2a1"
    pyproject_toml(pyproject)
    with pytest.raises(PolycotylusUsageError,
                       match="version '1.2a1' contains .* characters 'a'."):
        Project.from_root(shared.bare_minimum)

    pyproject["project"]["version"] = "1.2.post1"
    pyproject_toml(pyproject)
    with pytest.raises(PolycotylusUsageError,
                       match="version '1.2.post1' contains .* characters 'post'."):
        Project.from_root(shared.bare_minimum)


def test_maintainer(pyproject_toml, polycotylus_yaml, force_color):
    options = toml.load(shared.bare_minimum / "pyproject.toml")
    self = Project.from_root(shared.bare_minimum)
    assert self.maintainer_slug == "Brénainn Woodsend <bwoodsend@gmail.com>"

    options["project"]["maintainers"] = [dict(name="Sausage Roll",
                                              email="s.roll@pastries.com")]
    pyproject_toml(options)
    self = Project.from_root(shared.bare_minimum)
    assert self.maintainer_slug == "Sausage Roll <s.roll@pastries.com>"

    del options["project"]["maintainers"]
    del options["project"]["authors"]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError) as capture:
        self = Project.from_root(shared.bare_minimum)
    shared.snapshot_test(str(capture.value), "missing-maintainer")

    options["project"]["authors"] = [dict(name="bob", email="bob@mail.com"),
                                     dict(name="foo", email="foo@mail.com")]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError) as capture:
        self = Project.from_root(shared.bare_minimum)
    shared.snapshot_test(str(capture.value), "multiple-maintainers")

    options["project"]["maintainer"] = [dict(name="Bob and his friends",
                                             email="some@mailing-list.com")]
    pyproject_toml(options)
    with pytest.raises(PolycotylusUsageError, match="Multiple maintainers"):
        self = Project.from_root(shared.bare_minimum)

    polycotylus_yaml("maintainer: Mr Hippo < hippo@mail.com  > \n")
    self = Project.from_root(shared.bare_minimum)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"

    polycotylus_yaml("maintainer: Mr Hippo<hippo@mail.com>")
    self = Project.from_root(shared.bare_minimum)
    assert self.maintainer_slug == "Mr Hippo <hippo@mail.com>"

    polycotylus_yaml("maintainer: Mr Hippo")
    with pytest.raises(PolycotylusYAMLParseError,
                       match='Invalid maintainer "Mr Hippo".'):
        Project.from_root(shared.bare_minimum)


def test_missing_setuptools_scm(monkeypatch):
    monkeypatch.setitem(sys.modules, "setuptools_scm", None)
    with pytest.raises(PolycotylusUsageError, match="install setuptools-scm"):
        Project.from_root(shared.kitchen_sink)


def test_setuptools_scm(tmp_path, polycotylus_yaml, pyproject_toml, force_color):
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
    subprocess.run(["git", "tag", "v10.2.3.post3"], cwd=str(tmp_path), check=True)
    with pytest.raises(PolycotylusUsageError) as capture:
        Project.from_root(tmp_path)
    shared.snapshot_test(str(capture.value), "poetry-invalid-version")


def test_presubmit_lint(capsys, monkeypatch, polycotylus_yaml, no_color):
    from polycotylus.__main__ import cli

    monkeypatch.chdir(shared.dumb_text_viewer)
    with pytest.raises(SystemExit) as ex:
        cli(["--presubmit-check"])
    assert ex.value.code == 0
    assert capsys.readouterr().out == """\
✅ Implicit build backend
✅ Nonfunctional dependencies
✅ Non human maintainer
"""

    monkeypatch.chdir(shared.bare_minimum)
    with pytest.raises(SystemExit) as ex:
        cli(["--presubmit-check"])
    assert ex.value.code == 2
    assert capsys.readouterr().out == """\
❌ Implicit build backend:

No build backend specified via the build-system.build-backend key in the pyproject.toml. Pip/build correctly defaults to setuptools but Fedora does not handle this case properly. Add the following to your pyproject.toml to keep fedpkg happy.

# pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

✅ Nonfunctional dependencies
✅ Non human maintainer
"""

    monkeypatch.chdir(Path(__file__, "../../tests/mock-packages/complex-test-requirements").resolve())
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR")
    with pytest.raises(SystemExit) as ex:
        cli(["--presubmit-check"])
    assert ex.value.code == 14
    shared.snapshot_test(capsys.readouterr().out, "presubmit")

    polycotylus_yaml("maintainer: The maintainers <foo@mail.com>")
    self = Project.from_root(".")
    assert self.presubmit() == 10
    polycotylus_yaml("maintainer: Real person <foo@mail.com>")
    self = Project.from_root(".")
    assert self.presubmit() == 2


def test_python_extras_schema_definition():
    import polycotylus
    required = set()
    for distribution in polycotylus.distributions.values():
        required.update(distribution.python_extras)
    required = sorted(required)
    assert not [i for i in required if not re.fullmatch(polycotylus._yaml_schema.python_extra._regex, i)]
