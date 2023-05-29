from pathlib import Path

import strictyaml

import polycotylus
import shared


def test_minimum_extension_module_build_dependencies():
    """Ensure that the example dependencies.build from docs/source/schema.yaml
    (which is otherwise untested) stays in sync with that of ubrotli's
    polycotylus.yaml (which is tested on all distributions) minus the brotli
    references."""
    schema = Path(__file__, "../../docs/source/schema.yaml").resolve().read_text()
    api_reference = strictyaml.load(schema.replace("$identifier", "identifier"),
                                    polycotylus._yaml_schema.polycotylus_yaml)
    ubrotli = polycotylus._yaml_schema.read(shared.ubrotli / "polycotylus.yaml")

    target = {}
    for (_type, dependencies) in ubrotli.data["dependencies"]["build"].items():
        target[_type] = [i for i in dependencies if "brotli" not in i]
    target["pip"] = []

    documented = api_reference["dependencies"]["build"].data
    assert documented == target
