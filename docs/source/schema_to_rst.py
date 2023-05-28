from pathlib import Path
import re
import textwrap

import strictyaml

from polycotylus._yaml_schema import polycotylus_yaml


raw = Path(__file__).with_name("schema.yaml").read_text()
intro, raw = re.match("(.*?)(# ---.*)", raw, flags=re.DOTALL).groups()
intro = re.sub("^# ?", "", intro, flags=re.M)
lines = raw.splitlines(keepends=True)

heading = ["""
===============================
Reference: ``polycotylus.yaml``
===============================

.. highlight:: YAML
"""]

key_value_re = re.compile(r"( *)'?([^#:']*)'?: *(.*)")
comment_re = re.compile("( *)# ?(.*\n)")
caption_re = re.compile("# -{20}")
list_re = re.compile("( *)- ([^ ].*)")
blank_re = re.compile(" *\n")

toc = []
body = []
paths = {}
i = 0
while i < len(lines):
    while True:
        if m := comment_re.match(lines[i]):
            body.append(m[2])
        elif blank_re.match(lines[i]):
            body.append(lines[i])
        else:
            break
        i += 1
    line = lines[i]
    i += 1
    indentation, key, value = key_value_re.match(line).groups()
    yaml = {key: value}
    if key in ("alpine", "arch"):
        while m := key_value_re.match(lines[i]):
            indentation, key, value = m.groups()
            yaml[key] = value
            i += 1
        key = "$distribution"
    if key in ("spdx", "Name"):
        yaml[key] = {}
        while m := key_value_re.match(lines[i]):
            _indentation, _key, _value = m.groups()
            yaml[key][_key] = _value
            i += 1
        value = yaml
    if key == "test_files":
        yaml[key] = []
        while m := list_re.match(lines[i]):
            yaml[key].append(m[2])
            i += 1
        value = yaml

    paths[indentation] = key
    path = [j for (i, j) in paths.items() if len(i) <= len(indentation)]
    title = ".".join(path)
    body.append(f"\n\n{'.' * len(title)}\n{title}\n{'.' * len(title)}\n\n")
    toc.append(indentation * 2 + f"- :ref:`{key} <{'.'.join(path)}>`\n")
    while i < len(lines):
        line = lines[i]
        i += 1
        if caption_re.match(line):
            i -= 1
            break
        elif m := comment_re.match(line):
            body.append(m[1] * 0 + m[2])
        elif m := re.match(" *\n", line):
            body.append(line)
            continue
        elif key_value_re.match(line):
            i -= 1
            break
        else:
            yaml[key] += line

    if value:
        if isinstance(yaml.get(path[-1]), str):
            if yaml[path[-1]].startswith("|"):
                yaml[path[-1]] = textwrap.dedent(yaml[path[-1]][1:])
        for key in path[::-1][1:]:
            yaml = {key: yaml}
        serialized = strictyaml.as_document(yaml).as_yaml()
        try:
            strictyaml.load(serialized.replace("$identifier", "identifier"),
                            schema=polycotylus_yaml)
        except Exception as ex:
            if not re.search("required key.*not found", str(ex)):
                raise
        body += [
            "\n.. code-block:: yaml\n\n",
            textwrap.indent(serialized, "    "),
            "\n",
        ]

content = "".join(heading + ["\n\n", intro] + toc + ["\n\n"] + body)
rst = Path(__file__).with_name("schema.rst")
if not rst.exists() or rst.read_text() != content:
    rst.write_text(content)
