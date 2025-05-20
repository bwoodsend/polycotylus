import contextlib

import termcolor
import pytest


@pytest.fixture
def polycotylus_yaml(monkeypatch):

    def with_polycotylus_yaml(content):
        import textwrap
        import polycotylus
        monkeypatch.setattr(polycotylus._yaml_schema, "_read_text",
                            lambda *_: textwrap.dedent(content))

    return with_polycotylus_yaml


@pytest.fixture
def pyproject_toml(monkeypatch):

    def with_pyproject_toml(content):
        import toml
        original = toml.loads

        def toml_loads(*_):
            if isinstance(content, dict):
                return content
            else:
                return original(content)

        monkeypatch.setattr(toml, "loads", toml_loads)
        monkeypatch.setattr(toml, "load", toml_loads)

    return with_pyproject_toml


def _reset_termcolor():
    with contextlib.suppress(AttributeError):
        termcolor.termcolor._can_do_colour.cache_clear()
    with contextlib.suppress(AttributeError):
        termcolor.can_colorize.cache_clear()


@pytest.fixture
def force_color(monkeypatch):
    _reset_termcolor()
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", False)


@pytest.fixture
def no_color(monkeypatch):
    _reset_termcolor()
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", False)
