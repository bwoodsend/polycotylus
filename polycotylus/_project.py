from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess
import io
import tarfile
import json
import gzip
import warnings
from importlib import resources
import itertools
import textwrap
import os
from fnmatch import fnmatch

import toml

from polycotylus import _exceptions, _yaml_schema, _misc


# When dropping support for Python 3.8, replace
# importlib.resources.read_bytes("polycotylus", "xyz") with
# (importlib.resources.files("polycotylus") / "xyz").read_bytes().
warnings.filterwarnings(
    "ignore", r":(read|open)_(text|binary) is deprecated. Use files\(\) instead.",
    DeprecationWarning)


@dataclass
class Project:
    root: Path
    name: str
    maintainer: str
    email: str
    version: str
    setuptools_scm: bool
    description: str
    supported_python: str
    dependencies: dict
    build_dependencies: dict
    test_dependencies: dict
    test_command: str
    test_files: list
    license_names: list
    licenses: list
    scripts: dict
    desktop_entry_points: dict
    architecture: object
    gui: bool
    source_url: str
    source_top_level: str
    frontend: bool
    url: str

    @classmethod
    def from_root(cls, root):
        root = Path(root)
        try:
            pyproject_options = toml.load(str(root / "pyproject.toml"))
        except FileNotFoundError:
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                No pyproject.toml found. polycotylus should be ran from the
                root of a pip installable Python distribution with its core
                metadata declared in a PEP 621 pyproject.toml file. See
                https://packaging.python.org/en/latest/tutorials/packaging-projects/
            """)) from None
        try:
            polycotylus_yaml = _yaml_schema.read(root / "polycotylus.yaml")
        except FileNotFoundError:
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                Missing polycotylus.yaml: Create a polycotylus.yaml file in the
                same directory as your pyproject.toml file. See
                https://polycotylus.readthedocs.io/en/latest/schema.html
            """)) from None

        polycotylus_options = polycotylus_yaml.data

        if poetry_project := pyproject_options.get("tool", {}).get("poetry", {}):
            # Copy all poetry configuration to wherever it would be if poetry
            # followed PEP 621.
            try:
                maintainers = poetry_project.get("maintainers") or poetry_project["authors"]
                maintainers = [dict(zip(["name", "email"], re.match("([^<>]+?) *<(.+)>", i).groups())) for i in maintainers]
                project = {
                    "name": poetry_project["name"],
                    "version": poetry_project["version"],
                    "description": poetry_project["description"],
                    "urls": {"homepage": poetry_project["homepage"]},
                    "maintainers": maintainers,
                    "dependencies": [],
                    "scripts": poetry_project["scripts"],
                }
                for (name, version) in poetry_project["dependencies"].items():
                    # Poetry strongly encourages over-constraining versions
                    # (both lower and upper bounds). Since both bounds are most
                    # likely arbitrary and will cause disruption on
                    # distributions with longer release latencies, just discard
                    # them both. For Python, discard the upper bound.
                    if name == "python":
                        project["requires-python"] = version.replace("^", ">=")
                    elif isinstance(version, str) or not version.get("optional"):
                        project["dependencies"].append(name)

                poetry_spdx = poetry_project["license"]
            except KeyError as ex:
                raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                    Field "{ex.args[0]}" is missing from poetry's configuration
                    (the [tool.poetry] section of the pyproject.toml). See
                    https://python-poetry.org/docs/pyproject/#{ex.args[0]} for
                    what to set it to.
                """)) from None
        else:
            poetry_spdx = None
            project = pyproject_options.get("project", {})
        missing_fields = {}
        if "name" not in project:
            missing_fields["name"] = "your_package_name"
        _setuptools_scm = False
        if "version" not in project:
            if "version" in project.get("dynamic", []) and \
                    "setuptools_scm" in pyproject_options.get("tool", {}):
                try:
                    import setuptools_scm
                    project["version"] = setuptools_scm.get_version(
                        str(root), version_scheme=lambda v: str(v.tag), local_scheme=lambda x: "")
                    _setuptools_scm = True
                except ImportError:
                    raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                        setuptools-scm project detected (implied by the
                        [tool.setuptools_scm] section in the pyproject.toml).
                        polycotylus requires setuptools-scm to be installed to
                        process setuptools-scm versioned projects. Please pip
                        install setuptools-scm.
                    """))
            else:
                missing_fields["version"] = "1.2.3"
        if "description" not in project:
            missing_fields["description"] = "Give a one-line description of your package here"
        if project.get("urls", {}).get("Homepage"):
            project["urls"]["homepage"] = project["urls"]["Homepage"]
        if not project.get("urls", {}).get("homepage"):
            missing_fields["urls"] = {"homepage": "https://your.project.site"}
        if project.get("license", {}).get("file"):
            licenses = [project["license"]["file"]]
        else:
            licenses = []
            for file in os.listdir(root):
                for pattern in ['LICEN[CS]E*', 'COPYING*', 'NOTICE*', 'AUTHORS*']:
                    if fnmatch(file, pattern):
                        licenses.append(file)
                        break
            if not licenses:
                missing_fields["license"] = {"file": "LICENSE.txt"}
        if missing_fields:
            raise _exceptions.PolycotylusUsageError(
                f"Missing pyproject.toml fields {sorted(missing_fields)}. "
                "Add or migrate them to the pyproject.toml.\n\n"
                + textwrap.indent(toml.dumps({"project": missing_fields}), "    ")
                + "\nThey cannot be dynamic."
            )
        if invalid := re.sub(r"[\d.]", "", project["version"]):
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                Your project version "{project["version"]}" contains the
                disallowed characters "{invalid}". Linux distributions
                ubiquitously only support versions made up of numbers and periods.
            """))
        if maintainer_slug := polycotylus_options.get("maintainer"):
            match = re.fullmatch(_yaml_schema.maintainer_slug_re, maintainer_slug)
            maintainer = dict(zip(["name", "email"], match.groups()))
        else:
            maintainers = project.get("maintainers", project.get("authors", []))
            if not maintainers:
                raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                    No maintainer declared in either the pyproject.toml or
                    polycotylus.yaml. Nominate who will be responsible for
                    maintaining this and declare them using either:
                        # in pyproject.toml
                        [project]
                        maintainers = [{name="Your Name", email="your@email.com"}]
                    Or:
                        # polycotylus.yaml
                        maintainer: Your Name <your.email@address.com>
                """))
            if len(maintainers) > 1:
                raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                    Multiple maintainers declared in pyproject.toml.
                    Linux repositories require exactly one maintainer of the
                    Linux package. Nominate who that should be and specify
                    their contact details in the polycotylus.yaml.
                        maintainer: your name <your@email.org>"
                    """))
            maintainer, = maintainers
        check_maintainer(maintainer["name"])

        if polycotylus_options.get("spdx"):
            license_names = list(polycotylus_options["spdx"])
        elif poetry_spdx:
            license_names = [poetry_spdx]
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
        # Collect test dependencies on PyPI packages.
        test_dependencies = []
        extras = project.get("optional-dependencies", {})
        for requirement in dependencies.get("test", {}).get("pip", []):
            test_dependencies += expand_pip_requirements(
                requirement, root, extras)
        dependencies.setdefault("test", {})["pip"] = test_dependencies
        # Collect built time PyPI dependencies.
        _pip_build = dependencies.setdefault("build", {}).setdefault("pip", [])
        pip_build = []
        for item in _pip_build:
            for dependency in expand_pip_requirements(item, root):
                pip_build.append(Dependency(dependency, "polycotylus.yaml"))
        for dependency in pyproject_options.get("build-system", {}).get("requires", []):
            pip_build.append(Dependency(dependency, "pyproject.toml"))
        dependencies["build"]["pip"] = pip_build
        # Collect runtime PyPI dependencies.
        _pip_run = dependencies.setdefault("run", {}).setdefault("pip", [])
        pip_run = []
        for item in _pip_run:
            for dependency in expand_pip_requirements(item, root):
                pip_run.append(Dependency(dependency, "polycotylus.yaml"))
        pip_run += [Dependency(i, "pyproject.toml") for i in project.get("dependencies", [])]
        dependencies["run"]["pip"] = pip_run
        # Unpack grouped Linux dependencies.
        for group in dependencies:
            unpacked = {}
            for (distros, packages) in dependencies[group].items():
                for distro in distros.split():
                    unpacked.setdefault(distro, []).extend(packages)
            dependencies[group] = unpacked

        if "gui" in polycotylus_options:
            gui = polycotylus_options["gui"]
        else:
            gui = bool(project.get('gui-scripts'))

        if gui:
            if "test_command" in polycotylus_options:
                if "xvfb-run" not in polycotylus_options["test_command"]:
                    if "gui" in polycotylus_options:
                        message = _exceptions._unravel("""
                            GUI mode is enabled (specified by `gui: true` in the
                            polycotylus.yaml)
                        """)
                    else:
                        message = _exceptions._unravel("""
                            GUI mode is implicitly enabled (disable this by
                            setting `gui: false` in the polycotylus.yaml if this
                            your project does not use GUI elements)
                        """)
                    message += " " + _exceptions._unravel("""
                        but xvfb-run is not used in your test command.
                        GUI tests will fail to run without a virtual display.
                        Prepend xvfb-run to your test command
                    """)
                    _yaml_schema.revalidation_error(
                        polycotylus_yaml["test_command"], message)
            test_command = polycotylus_options.get("test_command", "xvfb-run pytest")
        else:
            test_command = polycotylus_options.get("test_command", "pytest")

        if "architecture" in polycotylus_options:
            architecture = polycotylus_options["architecture"]
        else:
            architecture = "none"
            for dependency in itertools.chain(*dependencies["build"].values()):
                if re.fullmatch("gcc|g[+][+]|clang|build-base|.*-(dev|devel)",
                                dependency):
                    architecture = "any"
                    break

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
            setuptools_scm=_setuptools_scm,
            description=project["description"],
            supported_python=project.get("requires-python", ""),
            dependencies=dependencies.get("run", {}),
            build_dependencies=dependencies["build"],
            test_dependencies=dependencies["test"],
            test_command=test_command,
            test_files=test_files,
            url=project["urls"]["homepage"],
            license_names=license_names,
            licenses=licenses,
            scripts={**project.get("scripts", {}), **project.get("gui-scripts", {})},
            desktop_entry_points=desktop_files,
            source_url=source,
            source_top_level=source_top_level,
            frontend=polycotylus_options["frontend"],
            architecture=architecture,
            gui=gui,
            root=root,
        )

    @property
    def maintainer_slug(self):
        return f"{self.maintainer} <{self.email}>"

    def tar(self):
        outputs = []
        for flag in ("-ocz", "-dz"):
            p = subprocess.run(["git", "ls-files", "--exclude-standard", flag],
                               text=True, cwd=str(self.root),
                               stdout=subprocess.PIPE)
            assert p.returncode == 0
            outputs.append(re.findall("[^\x00]+", p.stdout))
        files = [i for i in outputs[0] if i not in outputs[1]]
        buffer = io.BytesIO()

        def _strip_mtime(tar_info):
            tar_info.mtime = 0
            return tar_info

        with tarfile.TarFile("", mode="w", fileobj=buffer) as tar:
            top_level = self.source_top_level.format(version=self.version)
            for file in files:
                if str(file) == "pyproject.toml":
                    options = toml.load(self.root / file)
                    if not options.get("build-system"):
                        options["build-system"] = {
                            "build-backend": "setuptools.build_meta",
                            "requires": ["setuptools>=61.0"],
                        }
                        patched = toml.dumps(options).encode()
                        info = tarfile.TarInfo(str(PurePosixPath(top_level, file)))
                        info.size = len(patched)
                        tar.addfile(info, io.BytesIO(patched))
                        continue
                tar.add(self.root / file, PurePosixPath(top_level, file),
                        filter=_strip_mtime)
        return gzip.compress(buffer.getvalue(), mtime=0)

    def _desktop_file(self, id, options):
        out = {"Version": 1.0, "Type": "Application", "Terminal": False,
               "StartupNotify": False}
        out["Comment"] = self.description

        for (key, value) in options.items():
            _normalize_multistring = lambda x: ";".join(re.findall(r"[^\n;]+", x) + [""])
            if key in ("Actions", "Categories", "MimeType", "NotShowIn", "OnlyShowIn",
                       "X-XFCE-MimeType", "Implements"):
                value = _normalize_multistring(value)
            if key in ("Keywords", "X-AppInstall-Keywords", "X-GNOME-Keywords",
                       "X-Purism-FormFactor", "X-XFCE-MimeType"):
                value = {i: _normalize_multistring(j) for (i, j) in value.items()}
            if key in ("Comment", "GenericName", "Keywords",
                       "Name") and isinstance(value, dict):
                for (locale, translation) in value.items():
                    if locale == "":
                        out[key] = translation
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
            _misc.unix_write(path, self._desktop_file(id, options))

    def write_gitignore(self):
        path = self.root / ".polycotylus/.gitignore"
        if self.desktop_entry_points:
            _misc.unix_write(path, "*\n!.gitignore\n!*.desktop\n")
        else:
            _misc.unix_write(path, "*\n")

    def write_dockerignore(self):
        path = self.root / ".dockerignore"
        try:
            original = path.read_bytes().rstrip() + b"\n"
        except FileNotFoundError:
            original = b""
        if b".polycotylus" in original:
            return
        path.write_bytes(original + b".polycotylus\n")


class Dependency(str):
    @staticmethod
    def __new__(cls, name, origin):
        self = super().__new__(cls, name)
        self.origin = origin
        return self


def expand_pip_requirements(requirement, cwd, extras=None):
    if m := re.match("-r *([^ ].*)", requirement):
        # e.g. "-r requirements.txt"
        requirements_txt = cwd / m[1]
        text = requirements_txt.read_text("utf-8")
        for child in re.findall(r"^ *([^#\n\r]+)", text, re.MULTILINE):
            yield from expand_pip_requirements(child.strip(),
                                               requirements_txt.parent)

    elif m := re.match(r" *([^]]+) *\[([^]]+)\]", requirement):
        if m[1] == ".":
            # e.g. ".[test]"
            for group in re.findall("[^ ,]+", m[2]):
                for extra in extras[group]:
                    yield from expand_pip_requirements(extra, cwd)
        else:
            # e.g. "package[extra]"
            # Ignore extras from other packages. Figuring out what an extra
            # contains would require checking the version of the given package
            # available on each Linux distribution, downloading the wheel from
            # PyPI for whatever that version is, then fishing the metadata out
            # from the wheel.
            yield m[1]

    else:
        yield requirement


def check_maintainer(name):
    if re.search(r"\b(the|team|et al\.?|contributors|and|development|developers"
                 r"|llc|inc\.?|limited)\b", name.lower()):
        raise _exceptions.PolycotylusUsageError(
            f'Maintainer "{name}" appears to be a generic team or organization '
            'name. Linux repositories require personal contact details. '
            "Set them in the polycotylus.yaml.\n"
            "    maintainer: your name <your@email.org>"
        )


with resources.open_binary("polycotylus", "trove-spdx-licenses.json") as f:
    trove_to_spdx = json.load(f)
with resources.open_binary("polycotylus", "spdx-osi-approval.json") as f:
    spdx_osi_approval = json.load(f)

if __name__ == "__main__":
    self = Project.from_root(".")
    self.write_desktop_files()
    self.write_gitignore()
