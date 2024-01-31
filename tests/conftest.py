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


@pytest.fixture
def force_color(monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", False)


@pytest.fixture
def no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("FORCE_COLOR", False)
