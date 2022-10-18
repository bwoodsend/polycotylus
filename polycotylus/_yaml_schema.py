import re

from strictyaml import Any, Bool, Enum, Map, MapCombined, MapPattern, \
    Optional, OrValidator, Regex, Seq, Str, load, ScalarValidator

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


# yapf: disable

python_extra = Regex("(tkinter|sqlite3|decimal|lzma|zlib|readline|bz2)")
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

polycotylus_yaml = Map({
    "source_url": Str(),
    Optional("dependencies"): Map({
        Optional(type): dependencies_group for type in ["run", "build", "test"]
    }),
    Optional("gui"): Bool(),
    Optional("prefix_package_name", default=True): Bool(),
    Optional("desktop_entry_points"): MapPattern(desktop_file_id, desktop_file),
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


if __name__ == "__main__":
    import sys
    import json
    import strictyaml

    path = sys.argv[1]
    with open(path) as f:
        contents = f.read()
    try:
        config = strictyaml.load(contents, polycotylus_yaml, path)
    except Exception as ex:
        raise SystemExit(format_yaml_error(ex))

    print(json.dumps(config.data, indent="    ", ensure_ascii=False))
    print(strictyaml.as_document(config.data, schema=polycotylus_yaml).as_yaml())
