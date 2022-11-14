import re

from strictyaml import Any, Seq, Map, MapCombined, MapPattern, Str, EmptyDict, \
    Optional, OrValidator, Regex, Bool, load, ScalarValidator, StrictYAMLError

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

    def to_yaml(self, data):
        return " ".join([self._item_validator.to_yaml(item) for item in data])


python_extra = Regex("(tkinter|sqlite3|decimal|lzma|readline|ctypes|curses|bz2)")
desktop_file_id = Regex(r"(?:[a-zA-Z][\w\-.]+\.?)+")
icon = OrValidator(Map({"id": desktop_file_id, "source": Str()}), Str())
locale_string = OrValidator(Str(), MapPattern(Str(), Str()))

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

architectures = [
    "i386", "aarch64", "aarch64_be", "alpha", "arm", "armeb", "hexagon",
    "hppa", "m68k", "microblaze", "microblazeel", "mips", "mips64", "mips64el",
    "mipsel", "mipsn32", "mipsn32el", "or1k", "ppc", "ppc64", "ppc64le",
    "riscv32", "riscv64", "s390x", "sh4", "sh4eb", "sparc", "sparc32plus",
    "sparc64", "x86_64", "xtensa", "xtensaeb"
]

default_test_files = ["tests", "pytest.ini", "conftest.py", "test_*.py"]

polycotylus_yaml = Map({
    Optional("source_url"): Str(),
    Optional("source_top_level"): Str(),
    Optional("dependencies"): Map({
        Optional(type): dependencies_group for type in ["run", "build", "test"]
    }),
    Optional("gui"): Bool(),
    Optional("spdx"): MapPattern(Str(), EmptyDict()),
    Optional("prefix_package_name", default=True): Bool(),
    Optional("desktop_entry_points"): MapPattern(desktop_file_id, desktop_file),
    Optional("test_files", default=default_test_files): Seq(Str()),
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


def read(path):
    with open(path, "r") as f:
        raw = f.read()
    if not re.sub(r"#.*|\s|^---$|^\.\.\.$", "", raw, flags=re.M):
        # Strictyaml raises a parse error if the YAML is empty - even when all
        # fields are optional. Replace empty YAMLs.
        raw = "gui: false\n"
    try:
        yaml = load(raw, polycotylus_yaml, str(path))
        return yaml.data
    except StrictYAMLError as ex:
        yaml_error(ex)


if __name__ == "__main__":
    import sys
    import json
    import strictyaml

    path = sys.argv[1]
    with open(path) as f:
        contents = f.read()
    try:
        config = read(path)
    except PolycotylusYAMLParseError as ex:
        raise SystemExit(ex)

    print(json.dumps(config, indent="    ", ensure_ascii=False))
    print(strictyaml.as_document(config, schema=polycotylus_yaml).as_yaml())
