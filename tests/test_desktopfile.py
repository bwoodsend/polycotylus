import pytest

import polycotylus
from polycotylus._yaml_schema import localizations, Locale
from polycotylus.__main__ import cli
from tests import bare_minimum


list_localizations_sample_output = """\
Language Tag  Description
------------  -----------
aa            Afar
aab           Alumu-Tesu
aae           Arbëreshë Albanian
aaf           Aranadan
"""


def test_list_localizations(monkeypatch, capsys):
    monkeypatch.setitem(localizations, "language", {
        "aa": "Afar", "aab": "Alumu-Tesu", "aae": "Arbëreshë Albanian",
        "aaf": "Aranadan"})
    with pytest.raises(SystemExit):
        cli(["--list-localizations=language"])
    capture = capsys.readouterr()
    assert capture.out == list_localizations_sample_output


def test_multiple_descriptions():
    # Some languages have multiple names which correspond to multiple
    # Description fields in the language registry. A naive parser implementation
    # could result in second descriptions overwriting rather than extending the
    # first.
    languages = localizations["language"]
    assert "Spanish" in languages["es"]
    assert "Castilian" in languages["es"]
    assert "Swiss German" in languages["gsw"]
    assert "Alemannic" in languages["gsw"]
    assert "Alsatian" in languages["gsw"]


def test_all_available_localizers_are_valid():
    for key in localizations["language"]:
        assert Locale.pattern.fullmatch(key)
    for key in localizations["region"]:
        assert Locale.pattern.fullmatch("es_" + key)
    for key in localizations["modifier"]:
        assert Locale.pattern.fullmatch("es@" + key)


def test_localized_parse(polycotylus_yaml):
    polycotylus_yaml("""
        desktop_entry_points:
            foo:
                Exec: do something
                Name:
                    '': hello
                    es: holá
                    en_GB: hello
                    en_US: Yo
                    be@tarask: Выйсьці
                Keywords:
                    '': |
                        blah blah blah
                        x y z
                    es: bla bla bla;foo bar
                    zh: 我不听;我不听;;;
    """)
    self = polycotylus.Project.from_root(bare_minimum)
    content = self._desktop_file("foo", self.desktop_entry_points["foo"])
    assert "Name=hello\n" in content
    assert "Name[es]=holá\n" in content
    assert "Name[be@tarask]=Выйсьці\n" in content
    assert "Keywords=blah blah blah;x y z;\n" in content
    assert "Keywords[es]=bla bla bla;foo bar;\n" in content
    assert "Keywords[zh]=我不听;我不听;\n" in content

    polycotylus_yaml("""
        desktop_entry_points:
            foo:
                Exec: ...
                Name:
                    XYZ: ...
    """)
    with pytest.raises(polycotylus._exceptions.PolycotylusYAMLParseError,
                       match='Invalid localization "XYZ" should .*'
                       'See polycotylus --list-localizations'):
        polycotylus.Project.from_root(bare_minimum)

    polycotylus_yaml("""
        desktop_entry_points:
            foo:
                Exec: ...
                Name:
                    fr_XX: ...
    """)
    with pytest.raises(polycotylus._exceptions.PolycotylusYAMLParseError,
                       match='Unknown region identifier "XX". '
                             'See polycotylus --list-localizations=region for a list of valid region codes.'):
        polycotylus.Project.from_root(bare_minimum)
