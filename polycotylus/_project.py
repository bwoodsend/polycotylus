from dataclasses import dataclass
from pathlib import Path
import re
import collections
import subprocess
import io
import tarfile
import json
import mimetypes
from fnmatch import fnmatch
from locale import locale_alias
import gzip

import tomli
import strictyaml

from polycotylus import _exceptions


@dataclass
class Project:
    root: Path
    name: str
    maintainer: str
    email: str
    version: str
    description: str
    supported_python: str
    dependencies: list
    build_dependencies: list
    test_dependencies: list
    license_names: list
    licenses: list
    python_extras: list
    desktop_entry_points: dict
    gui: bool
    source_url: str
    url: str

    @classmethod
    def from_root(cls, root):
        root = Path(root)
        with (root / "pyproject.toml").open("rb") as f:
            pyproject_options = tomli.load(f)
        with (root / "polycotylus.yaml").open("r") as f:
            polycotylus_options = strictyaml.load(f.read()).data

        project = pyproject_options["project"]
        maintainer, = project["authors"]

        license_names = []
        for classifier in project["classifiers"]:
            m = re.fullmatch("License :: (?:OSI Approved ::)? (.+)", classifier)
            if m and m[1] != "OSI Approved":
                license_names.append(m[1])

        test_dependencies = []
        todo = collections.deque(polycotylus_options["test_requirements"])
        while todo:
            entry = todo.pop()
            m = re.match("-r *([^ ].*)", entry)
            if m:
                text = (root / m[1]).read_text()
                todo += re.findall(r"^ *\b[^#\n\r]+", text)
                continue
            m = re.match(r" *\[([^]]+)\]", entry)
            if m:
                for extra in re.findall("[^ ,]+", m[1]):
                    assert 0
                continue
            test_dependencies.append(entry)

        if "gui" in polycotylus_options:
            gui = polycotylus_options["gui"]
        else:
            gui = bool(project.get('gui-scripts'))

        return cls(
            name=project["name"],
            maintainer=maintainer["name"],
            email=maintainer["email"],
            version=project["version"],
            description=project["description"],
            supported_python=project["requires-python"],
            dependencies=project.get("dependencies", []),
            build_dependencies=pyproject_options["build-system"]["requires"],
            test_dependencies=test_dependencies,
            url=project["urls"]["Homepage"],
            license_names=license_names,
            licenses=[project["license"]["file"]],
            python_extras=polycotylus_options.get("python_extras", []),
            desktop_entry_points=polycotylus_options.get(
                "desktop_entry_points", {}),
            source_url=polycotylus_options["source_url"],
            gui=gui,
            root=root,
        )

    def tar(self):
        p = subprocess.run(["git", "ls-files", "--exclude-standard", "-oc"],
                           text=True, cwd=str(self.root),
                           stdout=subprocess.PIPE)
        assert p.returncode == 0
        files = re.findall("[^\n]+", p.stdout)
        buffer = io.BytesIO()
        with tarfile.TarFile("", mode="w", fileobj=buffer) as tar:
            for file in files:
                tar.add(self.root / file, f"{self.name}-{self.version}/{file}")
        return gzip.compress(buffer.getvalue(), mtime=0)

    def _desktop_file(self, id, options):
        out = {"Version": 1.0, "Type": "Application", "Terminal": False}
        out["Comment"] = self.description

        for (key, value) in options.items():
            value = _list_join(value)
            if key == "MimeType":
                mimes = []
                for pattern in re.findall(r"[^;\s]+", value):
                    mimes += expand_mimetype(pattern, id)
                value = ";".join(mimes)
            if key in ("Comment", "GenericName", "Keywords",
                       "Name") and isinstance(value, dict):
                for (locale, translation) in value.items():
                    locale = locale.lower()
                    if locale == "":
                        out[key] = translation
                    elif locale not in locale_alias:
                        raise _exceptions.InvalidLocale(
                            locale,
                            f"desktop_entry_points->{id}->{key}->{locale} "
                            "in the polycotylus.yaml")
                    else:
                        out[f"{key}[{locale}]"] = translation
            elif key == "icon":
                out["Icon"] = value["id"]
            else:
                out[key] = value

        for (key, value) in out.items():
            if not isinstance(value, str):
                out[key] = json.dumps(value)
        out = "".join(f"{key}={out[key]}\n" for key in sorted(out))

        return "[Desktop Entry]\n" + out

    def write_desktop_files(self):
        for (id, options) in self.desktop_entry_points.items():
            path = (self.root / ".polycotylus" / f"{id}.desktop")
            path.write_text(self._desktop_file(id, options), "utf-8")

    def write_gitignore(self):
        path = (self.root / ".polycotylus/.gitignore")
        path.write_text("*\n!.gitignore\n!*.desktop\n", encoding="utf-8")


def _list_join(x):
    if isinstance(x, list):
        return ";".join(x)
    if isinstance(x, dict):
        return {i: _list_join(j) for (i, j) in x.items()}
    return x


known_mimes = set(mimetypes.types_map.values())


def expand_mimetype(x, id):
    out = []
    if "*" not in x:
        return [x]
    for type in known_mimes:
        if fnmatch(type, x):
            out.append(type)
    if not out:
        raise _exceptions.InvalidMimetypePattern(
            x, f"desktop_entry_points->{id}->MimeType in the polycotylus.yaml")
    out.sort()
    return out


if __name__ == "__main__":
    self = Project.from_root(".")
    self.write_desktop_files()
    self.write_gitignore()
