from pathlib import Path
import re

import strictyaml

import polycotylus
import shared

schema = Path(__file__, "../../docs/source/schema.yaml").resolve().read_text("utf-8")


def test_minimum_extension_module_build_dependencies():
    """Ensure that the example dependencies.build from docs/source/schema.yaml
    (which is otherwise untested) stays in sync with that of ubrotli's
    polycotylus.yaml (which is tested on all distributions) minus the brotli
    references."""
    api_reference = strictyaml.load(schema.replace("$", ""),
                                    polycotylus._yaml_schema.polycotylus_yaml)
    ubrotli = polycotylus._yaml_schema.read(shared.ubrotli / "polycotylus.yaml")

    target = {}
    for (_type, dependencies) in ubrotli.data["dependencies"]["build"].items():
        target[_type] = [i for i in dependencies if "brotli" not in i]
    target["pip"] = []

    documented = api_reference["dependencies"]["build"].data
    assert documented == target


def test_dependency_categories():
    documented = re.search(r"``(alpine\|[|a-z]+)``", schema)[1].split("|")
    assert documented == sorted(i for i in polycotylus.distributions if ":" not in i)
