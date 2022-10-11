from strictyaml import Any, Bool, Enum, Map, MapCombined, MapPattern, \
    Optional, OrValidator, Regex, Seq, Str, load

# yapf: disable

python_extra = Enum([
    "tkinter", "sqlite3", "decimal", "lzma", "zlib", "readline", "bz2"])

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

polycotylus_yaml = Map({
    "source_url": Str(),
    Optional("python_extras"): Seq(python_extra),
    Optional("test_requirements"): Seq(Str()),
    Optional("gui"): Bool(),
    Optional("prefix_package_name", default=True): Bool(),
    Optional("desktop_entry_points"): MapPattern(desktop_file_id, desktop_file),
})

if __name__ == "__main__":
    import sys
    import json
    path = sys.argv[1]
    with open(path) as f:
        contents = f.read()
    try:
        config = load(contents, polycotylus_yaml, path)
    except Exception as ex:
        raise SystemExit(str(ex))
    print(json.dumps(config.data, indent="    ", ensure_ascii=False))
