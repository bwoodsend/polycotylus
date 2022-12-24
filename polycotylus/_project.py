from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess
import io
import tarfile
import json
import mimetypes
from fnmatch import fnmatch
from locale import locale_alias
import gzip
from importlib import resources

import tomli

from polycotylus import _exceptions, _yaml_schema


@dataclass
class Project:
    root: Path
    name: str
    maintainer: str
    email: str
    version: str
    description: str
    supported_python: str
    dependencies: dict
    build_dependencies: dict
    test_dependencies: dict
    test_files: list
    license_names: list
    licenses: list
    desktop_entry_points: dict
    architecture: object
    gui: bool
    source_url: str
    source_top_level: str
    prefix_package_name: bool
    url: str

    @classmethod
    def from_root(cls, root):
        root = Path(root)
        with (root / "pyproject.toml").open("rb") as f:
            pyproject_options = tomli.load(f)
        polycotylus_options = _yaml_schema.read(root / "polycotylus.yaml")

        project = pyproject_options["project"]
        maintainer, = project["authors"]

        if polycotylus_options.get("spdx"):
            license_names = list(polycotylus_options["spdx"])
        else:
            license_names = []
            for classifier in project.get("classifiers", []):
                if spdx := trove_to_spdx.get(classifier):
                    if spdx == "ignore":
                        continue
                    if isinstance(spdx, list):
                        raise _exceptions.AmbiguousLicenseError(
                            classifier, spdx)
                    license_names.append(spdx)
            if not license_names:
                raise _exceptions.NoLicenseSpecifierError()

        dependencies = polycotylus_options.get("dependencies", {})
        test_dependencies = []
        extras = project.get("optional-dependencies", {})
        for requirement in dependencies.get("test", {}).get("pip", []):
            test_dependencies += expand_pip_requirements(
                requirement, root, extras)
        dependencies.setdefault("test", {})["pip"] = test_dependencies
        dependencies.setdefault("build", {})["pip"] = \
            pyproject_options.get("build-system", {}).get("requires", [])
        dependencies.setdefault("run", {})["pip"] = \
            project.get("dependencies", [])

        if "gui" in polycotylus_options:
            gui = polycotylus_options["gui"]
        else:
            gui = bool(project.get('gui-scripts'))

        if "architecture" in polycotylus_options:
            architecture = polycotylus_options["architecture"]
        else:
            architecture = "none"
            for compiler in ("gcc", "g++", "build-base", "clang"):
                for group in dependencies["build"].values():
                    if compiler in group:
                        architecture = "any"

        desktop_files = polycotylus_options.get("desktop_entry_points", {})
        for (id, desktop_file) in desktop_files.items():
            if isinstance(icon := desktop_file.get("icon"), str):
                desktop_file["icon"] = {"id": id, "source": icon}

        test_files = []
        for pattern in polycotylus_options["test_files"]:
            test_files += root.glob(pattern)
        test_files = [i.relative_to(root) for i in test_files]

        source = polycotylus_options.get("source_url")
        if not source:
            name = project["name"]
            _name = re.sub("[-_.]+", "-", name).lower()
            source = f"https://pypi.io/packages/source/{_name[0]}/{_name}/{name}-{{version}}.tar.gz"
        source_top_level = polycotylus_options.get("source_top_level")
        if not source_top_level:
            source_top_level = project["name"] + "-{version}"

        return cls(
            name=project["name"],
            maintainer=maintainer["name"],
            email=maintainer["email"],
            version=project["version"],
            description=project["description"],
            supported_python=project.get("requires-python", ""),
            dependencies=dependencies.get("run", {}),
            build_dependencies=dependencies["build"],
            test_dependencies=dependencies["test"],
            test_files=test_files,
            url=project["urls"]["Homepage"],
            license_names=license_names,
            licenses=[project["license"]["file"]],
            desktop_entry_points=desktop_files,
            source_url=source,
            source_top_level=source_top_level,
            prefix_package_name=polycotylus_options["prefix_package_name"],
            architecture=architecture,
            gui=gui,
            root=root,
        )

    @property
    def maintainer_slug(self):
        return f"{self.maintainer} <{self.email}>"

    def tar(self):
        p = subprocess.run(["git", "ls-files", "--exclude-standard", "-ocz"],
                           text=True, cwd=str(self.root),
                           stdout=subprocess.PIPE)
        assert p.returncode == 0
        files = re.findall("[^\x00]+", p.stdout)
        buffer = io.BytesIO()

        def _strip_mtime(tar_info):
            tar_info.mtime = 0
            return tar_info

        with tarfile.TarFile("", mode="w", fileobj=buffer) as tar:
            top_level = self.source_top_level.format(version=self.version)
            for file in files:
                tar.add(self.root / file, PurePosixPath(top_level, file),
                        filter=_strip_mtime)
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
        if self.desktop_entry_points:
            path.write_text("*\n!.gitignore\n!*.desktop\n", encoding="utf-8")
        else:
            path.write_text("*\n")

    def write_dockerignore(self):
        path = self.root / ".dockerignore"
        try:
            original = path.read_bytes().rstrip() + b"\n"
        except FileNotFoundError:
            original = b""
        if b".polycotylus" in original:
            return
        path.write_bytes(original + b".polycotylus\n")

    @property
    def test_command(self):
        return "xvfb-run pytest" if self.gui else "pytest"


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


def expand_pip_requirements(requirement, cwd, extras=None):
    if m := re.match("-r *([^ ].*)", requirement):
        requirements_txt = cwd / m[1]
        text = requirements_txt.read_text()
        for child in re.findall(r"^ *([^#\n\r]+)", text, re.MULTILINE):
            yield from expand_pip_requirements(child.strip(),
                                               requirements_txt.parent)

    elif m := re.match(r" *([^]]+) *\[([^]]+)\]", requirement):
        assert m[1] == "."
        for group in re.findall("[^ ,]+", m[2]):
            for extra in extras[group]:
                yield from expand_pip_requirements(extra, cwd)

    else:
        yield requirement


with resources.open_binary("polycotylus", "trove-spdx-licenses.json") as f:
    trove_to_spdx = json.load(f)
with resources.open_binary("polycotylus", "spdx-osi-approval.json") as f:
    spdx_osi_approval = json.load(f)

if __name__ == "__main__":
    self = Project.from_root(".")
    self.write_desktop_files()
    self.write_gitignore()
