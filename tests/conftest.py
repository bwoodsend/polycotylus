import pytest


@pytest.fixture(autouse=True)
def polycotylus_yaml(monkeypatch):

    def with_polycotylus_yaml(content):
        import textwrap
        import polycotylus
        monkeypatch.setattr(polycotylus._yaml_schema, "_read_text",
                            lambda *_: textwrap.dedent(content))

    return with_polycotylus_yaml
