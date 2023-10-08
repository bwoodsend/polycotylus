import shutil
import os
import importlib.metadata

import pytest

import sIlLy_Nam3


def test_main():
    assert importlib.metadata.version("99...S1Lly---namE___PACKAG3-.x-_y_.z") == "1.2.3"
    assert sIlLy_Nam3.a == "\U0001d738"


def test_dependencies():
    import sqlite3
    import tkinter
    assert shutil.which("nano")
    with pytest.raises(ImportError):
        import win32ctypes


def test_import_other_test_files():
    from the_test_suite.constants import POINTLESS_CONSTANT


def test_unrunable():
    assert 0, "This test should by skipped via pytest's '-k unrunable' flag"


def test_environment_variable():
    assert os.environ["TEST_VARIABLE"] == "hello"


def test_dependency_name_map():
    if shutil.which("pacman"):
        assert shutil.which("netcat")
        with pytest.raises(ImportError):
            import tzlocal
    else:
        import tzlocal
