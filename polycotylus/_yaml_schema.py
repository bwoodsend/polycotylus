import re
import json
from importlib import resources

from strictyaml import Any, Seq, Map, MapCombined, MapPattern, Str, EmptyDict, \
    Optional, OrValidator, Regex, Bool, load, ScalarValidator, \
    StrictYAMLError, YAMLValidationError

from polycotylus._exceptions import PolycotylusYAMLParseError


class WhitespaceDelimited(ScalarValidator):
    def __init__(self, item_validator):
        self._item_validator = item_validator
        assert isinstance(self._item_validator,
                          ScalarValidator), "item validator must be scalar too"

    def validate_scalar(self, chunk):
        out = []
        for match in re.finditer(r"(?:-r *)?(?:\[[^]]*\]|\S)+", chunk.contents):
            slice = chunk.textslice(match.start(), match.end())
            out.append(self._item_validator.validate_scalar(slice))
        return out

    def to_yaml(self, data):  # pragma: no cover
        return " ".join([self._item_validator.to_yaml(item) for item in data])


class Locale(ScalarValidator):
    """"
    https://specifications.freedesktop.org/desktop-entry-spec/latest/ar01s05.html
    https://unicode.org/reports/tr35/#Unicode_Language_and_Locale_Identifiers
    https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry

    Equivalent terms:

    freedesktop  unicode.org
    ===========  ===================
    lang         language or extlang
    country      region
    modifier     script or variant

    """
    pattern = re.compile(r"([a-z]+)(?:_([A-Z]+|[0-9]+))?(?:@([A-Za-z0-9]+))?")

    def validate_scalar(self, chunk):
        if not chunk.contents:
            return chunk.contents
        match = self.pattern.fullmatch(chunk.contents)
        if not match:
            raise YAMLValidationError(
                "See polycotylus --list-localizations={language|region|modifier} for a list of valid codes for each part",
                f'Invalid localization "{chunk.contents}" should be in the format "language_COUNTRY@modifier" where the "_COUNTRY" and "@modifier" parts are optional.',
                chunk)
        parsed = dict(zip(["language", "region", "modifier"], match.groups()))
        for (key, value) in parsed.items():
            if not value:
                continue
            if value not in localizations[key]:
                raise YAMLValidationError(
                    f"See polycotylus --list-localizations={key} for a list of valid {key} codes",
                    f'Unknown {key} identifier "{value}".', chunk)
        return chunk.contents


with resources.open_binary("polycotylus", "localizations.json") as f:
    localizations = json.load(f)

python_extra = Regex("(tkinter|sqlite3|decimal|lzma|readline|ctypes|curses|bz2)")
desktop_file_id = Regex(r"(?:[a-zA-Z][\w\-.]+\.?)+")
icon = OrValidator(Map({"id": desktop_file_id, "source": Str()}), Str())
locale_string = OrValidator(Str(), MapPattern(Locale(), Str()))

desktop_file = MapCombined({
    "Name": locale_string,
    "Exec": Str(),
    Optional("GenericName"): locale_string,
    Optional("Comment"): locale_string,
    Optional("Keywords"): locale_string,
    Optional("icon"): icon,
    Optional("NoDisplay"): Bool(),
}, Regex("[A-Za-z0-9-]+"), Any())

dependencies_group = MapCombined(
    {Optional("python"): WhitespaceDelimited(python_extra)},
    Str(), WhitespaceDelimited(Str()),
)

architectures = ["aarch64", "armhf", "armv7", "ppc64le", "x86", "x86_64"]

default_test_files = ["tests", "pytest.ini", "conftest.py", "test_*.py"]
maintainer_slug_re = r"\s*([^<>@]+)\b\s*<\s*([^<>@ ]+@[^<>@ ]+)\s*>\s*"

polycotylus_yaml = Map({
    Optional("source_url"): Str(),
    Optional("source_top_level"): Str(),
    Optional("dependencies"): Map({
        Optional(type): dependencies_group for type in ["run", "build", "test"]
    }),
    Optional("maintainer"): Regex(maintainer_slug_re),
    Optional("gui"): Bool(),
    Optional("spdx"): MapPattern(Str(), EmptyDict()),
    Optional("prefix_package_name", default=True): Bool(),
    Optional("desktop_entry_points"): MapPattern(desktop_file_id, desktop_file),
    Optional("test_files", default=default_test_files): Seq(Str()),
    Optional("test_command"): Str(),
    Optional("architecture"): OrValidator(
        Regex("(any|none)"),
        WhitespaceDelimited(Regex("!?(" + "|".join(architectures) + ")")),
    ),
})


def yaml_error(ex):
    out = "Invalid polycotylus.yaml:\n"
    out += f'  In "{ex.context_mark.name}", line {ex.problem_mark.line}\n'
    out += ex.problem_mark.get_snippet() + "\n"
    children = []
    while ex:
        children.append(ex)
        ex = ex.__context__
    for ex in children[::-1]:
        out += ex.problem[0].upper() + ex.problem[1:] + " " + ex.context + ".\n"
    raise PolycotylusYAMLParseError(out) from None


def _read_text(path):
    with open(path, "r") as f:
        return f.read()


def read(path):
    raw = _read_text(path)
    if not re.sub(r"#.*|\s|^---$|^\.\.\.$", "", raw, flags=re.M):
        # Strictyaml raises a parse error if the YAML is empty - even when all
        # fields are optional. Replace empty YAMLs with something functionally
        # equivalent to an empty one.
        raw = "dependencies:\n  run:\n    pip:"
    try:
        yaml = load(raw, polycotylus_yaml, str(path))
        return yaml
    except StrictYAMLError as ex:
        yaml_error(ex)


def revalidation_error(yaml, message):
    yaml_error(YAMLValidationError(*message.split(" ", 1)[::-1], yaml._chunk))


if __name__ == "__main__":
    import sys
    import json
    import strictyaml

    path = sys.argv[1]
    with open(path) as f:
        contents = f.read()
    try:
        config = read(path).data
    except PolycotylusYAMLParseError as ex:
        raise SystemExit(ex)

    print(json.dumps(config, indent="    ", ensure_ascii=False))
    print(strictyaml.as_document(config, schema=polycotylus_yaml).as_yaml())
