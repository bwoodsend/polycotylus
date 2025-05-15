from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
import subprocess
import io
import tarfile
import json
import gzip
import itertools
import textwrap
import os
from fnmatch import fnmatch
import glob
import contextlib

import toml

from polycotylus import _exceptions, _yaml_schema, _misc


class TestCommandLexer:
    _pattern = re.compile(r"\+([^+\n]*)\+")

    def __init__(self, source):
        self.template = source

    @property
    def placeholders(self):
        return [m[1] for m in self._pattern.finditer(self.template) if m[1]]

    def evaluate(self, replace=lambda x: x):
        return self._pattern.sub(lambda m: replace(m[1]) if m[1] else "+", self.template)

    @property
    def multistatement(self):
        return re.search("[\n;&|]", self.template.strip()) is not None


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
    dependency_name_map: dict
    test_command: TestCommandLexer
    test_files: list
    license_spdx: str
    licenses: list
    contains_py_files: bool
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
        from polycotylus._exceptions import comment, string, key, highlight_toml

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
                    Field {key(repr(ex.args[0]))} is missing from poetry's
                    configuration (the [{key("tool.poetry")}] section of the
                    pyproject.toml). See
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
                    raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                        setuptools-scm project detected (implied by the
                        [{key("tool.setuptools_scm")}] section in the
                        pyproject.toml). polycotylus requires setuptools-scm to
                        be installed to process setuptools-scm versioned
                        projects. Please {string("pip install setuptools-scm")}
                    """))
            else:
                missing_fields["version"] = "1.2.3"
        if "description" not in project:
            missing_fields["description"] = "Give a one-line description of your package here"
        if project.get("urls", {}).get("Homepage"):
            project["urls"]["homepage"] = project["urls"]["Homepage"]
        if not project.get("urls", {}).get("homepage"):
            missing_fields["urls"] = {"homepage": "https://your.project.site"}
        if missing_fields:
            raise _exceptions.PolycotylusUsageError(
                f"Missing pyproject.toml fields {highlight_toml(str(sorted(missing_fields)))}. "
                "Add or migrate them to the pyproject.toml.\n\n"
                + highlight_toml("# pyproject.toml\n" +
                                 toml.dumps({"project": missing_fields}))
            )
        if invalid := re.sub(r"[\d.]", "", project["version"]):
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                Your project version {string(repr(project["version"]))} contains
                the disallowed characters {string(repr(invalid))}. Linux
                distributions ubiquitously only support versions made up of
                numbers and periods.
            """))
        if not (maintainer := polycotylus_options.get("maintainer")):
            maintainers = project.get("maintainers", project.get("authors", []))
            if not maintainers:
                raise _exceptions.PolycotylusUsageError(
                    "No maintainer declared in either the pyproject.toml or "
                    "polycotylus.yaml. Nominate who will be responsible for "
                    "maintaining this and declare them using either:\n" +
                    highlight_toml(textwrap.dedent("""
                        # pyproject.toml
                        [project]
                        maintainers = [{name="Your Name", email="your@email.com"}]
                    """)) + textwrap.dedent(f"""
                        Or:

                        {comment(f"# polycotylus.yaml")}
                        {key("maintainer")}: Your Name <your.email@address.com>
                    """)
                )
            if len(maintainers) > 1:
                raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                    Multiple maintainers declared in pyproject.toml.
                    Linux repositories require exactly one maintainer of the
                    Linux package. Nominate who that should be and specify
                    their contact details in the polycotylus.yaml.
                """) + textwrap.dedent(f"""

                    {comment("# polycotylus.yaml")}
                    {key("maintainer")}: your name <your@email.org>
                """))
            maintainer, = maintainers

        license_spdx, licenses = parse_licenses(
            polycotylus_options, project, poetry_spdx, root)

        dependencies = polycotylus_options.get("dependencies", {})
        # Collect test dependencies on PyPI packages.
        test_dependencies = []
        extras = project.get("optional-dependencies", {})
        for requirement in dependencies.get("test", {}).get("pip", []):
            test_dependencies += expand_pip_requirements(
                requirement, root, "polycotylus.yaml", extras)
        dependencies.setdefault("test", {})["pip"] = test_dependencies
        # Collect built time PyPI dependencies.
        _pip_build = dependencies.setdefault("build", {}).setdefault("pip", [])
        pip_build = []
        for item in _pip_build:
            for dependency in expand_pip_requirements(item, root, "polycotylus.yaml"):
                pip_build.append(Dependency(dependency, "polycotylus.yaml"))
        for dependency in pyproject_options.get("build-system", {}).get("requires", []):
            pip_build.append(Dependency(dependency, "pyproject.toml"))
        dependencies["build"]["pip"] = pip_build
        # Collect runtime PyPI dependencies.
        _pip_run = dependencies.setdefault("run", {}).setdefault("pip", [])
        pip_run = []
        for item in _pip_run:
            for dependency in expand_pip_requirements(item, root, "polycotylus.yaml"):
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
            test_command = polycotylus_options.get("test_command", "xvfb-run +pytest+")
        else:
            test_command = polycotylus_options.get("test_command", "+pytest+")
        test_command = TestCommandLexer(test_command)
        if test_command.template.strip() and not test_command.placeholders:
            _yaml_schema.revalidation_error(
                polycotylus_yaml["test_command"], _exceptions._unravel(f"""
                    The {key("test_command")} contains no Python command
                    placeholders. Polycotylus requires executables from Python
                    environments to be marked as such by wrapping them in plus
                    signs. E.g. replace {string("python")} with
                    {string("+python+")} or {string("pytest")} with
                    {string("+pytest+")}. Wrapper scripts or tools like tox can
                    not be used
            """))

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
            for (action_id, action) in desktop_file.get("actions", {}).items():
                if isinstance(icon := action.get("icon"), str):
                    action["icon"] = {"id": id + "-" + action_id, "source": icon}

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
            dependency_name_map=polycotylus_options.get("dependency_name_map", {}),
            test_files=test_files,
            url=project["urls"]["homepage"],
            license_spdx=license_spdx,
            licenses=licenses,
            contains_py_files=polycotylus_options["contains_py_files"],
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

    def tar(self, prefix=None):
        if prefix is None:
            prefix = self.source_top_level.format(version=self.version)
        outputs = []
        for flag in ("-ocz", "-dz"):
            p = subprocess.run(["git", "ls-files", "--exclude-standard", flag],
                               text=True, cwd=str(self.root),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if "not a git repository" in p.stderr:
                raise _exceptions.PolycotylusUsageError(
                    "Not a git repository. Polycotylus must be ran from inside a git project.")
            assert p.returncode == 0, p.stderr
            outputs.append(re.findall("[^\x00]+", p.stdout))
        files = [i for i in outputs[0] if i not in outputs[1]]
        buffer = io.BytesIO()

        def _strip_mtime(tar_info):
            tar_info.mtime = 0
            return tar_info

        with tarfile.TarFile("", mode="w", fileobj=buffer) as tar:
            for file in files:
                if str(file) == "pyproject.toml":
                    options = toml.load(self.root / file)
                    if not options.get("build-system"):
                        options["build-system"] = {
                            "build-backend": "setuptools.build_meta",
                            "requires": ["setuptools>=61.0"],
                        }
                        patched = toml.dumps(options).encode()
                        info = tarfile.TarInfo(str(PurePosixPath(prefix, file)))
                        info.size = len(patched)
                        tar.addfile(info, io.BytesIO(patched))
                        continue
                tar.add(self.root / file, PurePosixPath(prefix, file),
                        filter=_strip_mtime)
        return gzip.compress(buffer.getvalue(), mtime=0)

    def _desktop_file(self, id, options):
        out = {"Version": 1.0, "Type": "Application", "Terminal": False,
               "StartupNotify": False}
        out["Comment"] = self.description

        def _normalize_multistring(x):
            # Strip comments, replace newlines with ';', .strip() each item, append trailing ';'
            return ";".join([i.strip() for i in re.findall(r"[^\n;]+", re.sub("#.*", "", x))] + [""])

        for (key, value) in options.items():
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
            elif key == "actions":
                out["Actions"] = "".join(i + ";" for i in value)
            elif key == "icon":
                out["Icon"] = value["id"]
            else:
                out[key] = value

        for (key, value) in out.items():
            if not isinstance(value, str):
                assert key != "Comment"
                out[key] = json.dumps(value)
        out = "".join(f"{key}={out[key]}\n" for key in sorted(out))
        out = "[Desktop Entry]\n" + out

        for (action_id, action_options) in options.get("actions", {}).items():
            action = {"Name": action_options["Name"], "Exec": action_options["Exec"]}
            if "icon" in action_options:
                action["Icon"] = action_options["icon"]["id"]
            out += f"\n[Desktop Action {action_id}]\n"
            out += "".join(f"{key}={action[key]}\n" for key in sorted(action))

        return out

    def write_desktop_files(self):
        for (id, options) in self.desktop_entry_points.items():
            path = (self.root / ".polycotylus" / f"{id}.desktop")
            _misc.unix_write(path, self._desktop_file(id, options))
        # Delete any unused desktop files, most likely left by a desktop file ID
        # being renamed.
        for path in (self.root / ".polycotylus").glob("*.desktop"):
            if path.stem not in self.desktop_entry_points:
                path.unlink()

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

    def presubmit_missing_build_backend(self):
        pyproject_options = toml.load(str(self.root / "pyproject.toml"))
        if pyproject_options.get("build-system", {}).get("build-backend") is None:
            from polycotylus._exceptions import highlight_toml, key
            raise _exceptions.PresubmitCheckError(_exceptions._unravel(f"""
                No build backend specified via the
                {key("build-system.build-backend")} key in the pyproject.toml.
                Pip/build correctly defaults to setuptools but Fedora does not
                handle this case properly. Add the following to your
                pyproject.toml to keep fedpkg happy.
            """) + highlight_toml(textwrap.dedent('''

                # pyproject.toml
                [build-system]
                requires = ["setuptools>=61.0"]
                build-backend = "setuptools.build_meta"''')))

    def presubmit_nonfunctional_dependencies(self):
        prohibited = []
        for package in self.test_dependencies["pip"]:
            _package = re.sub("[._-]+", "-", package)
            if re.fullmatch("""
                # Linters
                .*flake8.* | pylint | pyflakes | bandit | beniget | mccabe |
                pep8 | pep8-naming | pycodestyle | pydocstyle | ruff |
                pytest-flake[s8] | safety | codespell | mypy(-extensions)? |
                # Formatters
                autopep8 | autoflake | black | yapf | isort | blue |
                # Coverage
                coverage(py)? | pytest-cov | coverage-.*-plugin | codecov
                covdefaults | coveralls
            """, _package, flags=re.VERBOSE):
                prohibited.append(package)
        if prohibited:
            raise _exceptions.NonFunctionalTestDependenciesError(prohibited)

    def presubmit(self):
        checks = {
            "Implicit build backend": self.presubmit_missing_build_backend,
            "Nonfunctional dependencies": self.presubmit_nonfunctional_dependencies,
            "Non human maintainer": lambda: check_maintainer(self.maintainer),
        }
        exit_code = 0
        for (i, (name, method)) in enumerate(checks.items(), start=1):
            try:
                method()
                print("✅", name, flush=True)
            except _exceptions.PresubmitCheckError as ex:
                exit_code += (1 << i)
                print("❌", name + ":\n")
                print(str(ex) + "\n", flush=True)
        return exit_code

    @contextlib.contextmanager
    def artifacts_database(self):
        import portalocker
        json_path = self.root / ".polycotylus/artifacts.json"
        with portalocker.Lock(json_path.with_name(".artifacts.lock")):
            try:
                artifacts = json.loads(json_path.read_bytes())
            except:
                artifacts = []
            for artifact in artifacts:
                artifact["path"] = self.root / artifact["path"]
                if artifact.get("signature_path"):
                    artifact["signature_path"] = self.root / artifact["signature_path"]
            artifacts = [Artifact(**i) for i in artifacts]
            artifacts = [i for i in artifacts if (self.root / i.path).exists()]
            try:
                yield artifacts
            finally:
                deduplicated = {}
                for artifact in artifacts:
                    deduplicated[artifact._identifier] = artifact
                artifacts = [deduplicated[i] for i in sorted(deduplicated)]
                artifacts = [i.to_dict(self.root) for i in artifacts]
                _misc.unix_write(json_path, json.dumps(artifacts, indent="  "))


def parse_licenses(polycotylus_options, project, poetry_spdx, root):
    """Sources of license name (in order of preference):

    # polycotylus.yaml
    license: MIT and BSD-3-Clause

    # pyproject.toml
    license = "MIT and BSD-3-Clause"
    license = { text="MIT" }  # or  license = { text="some nonsense" }
    classifiers = [
        "License :: OSI Approved :: MIT License",
        "License :: OSI Approved :: Apache License",
    ]  # Ambiguous if more than one

    """
    spdx = polycotylus_options.get("license") or poetry_spdx
    if not spdx and isinstance(project.get("license"), str):
        spdx = project["license"]
    if not spdx:
        license_names = []
        for classifier in project.get("classifiers", []):
            if _spdx := trove_to_spdx.get(classifier):
                if _spdx == "ignore":
                    continue
                if isinstance(_spdx, list):
                    raise _exceptions.AmbiguousLicenseError(classifier, _spdx)
                license_names.append(_spdx)
        if len(license_names) > 1:
            raise _exceptions.MultipleLicenseClassifiersError(license_names)
        if license_names:
            spdx = license_names[0]
    if not spdx and isinstance(project.get("license"), dict):
        if (_spdx := project["license"].get("text")) in spdx_osi_approved:
            spdx = _spdx
    if not spdx:
        raise _exceptions.NoLicenseSpecifierError()

    """Sources of license files:

    # pyproject.toml
    license-files = ["LICEN[CS]E*", "AUTHORS*"]
    license = { file="LICENSE" }

    Implicitly glob for ['LICEN[CS]E*', 'COPYING*', 'NOTICE*', 'AUTHORS*']

    """
    if project.get("license-files"):
        licenses = []
        for pattern in project["license-files"]:
            for path in glob.glob(str(root / pattern)):
                licenses.append(Path(path).relative_to(root).as_posix())
    elif isinstance(project.get("license"), dict) and project["license"].get("file"):
        licenses = [project["license"]["file"]]
    else:
        licenses = []
        for file in os.listdir(root):
            for pattern in ['LICEN[CS]E*', 'COPYING*', 'NOTICE*', 'AUTHORS*']:
                if fnmatch(file, pattern):
                    licenses.append(file)
        if not licenses:
            raise _exceptions.PolycotylusUsageError(_exceptions._unravel("""
                No license file found. Create a file called LICENSE next to the
                pyproject.toml containing the terms under which this package
                can be distributed.
            """))
    return spdx, licenses


@dataclass
class Artifact:
    distribution: str
    tag: str
    architecture: str
    package_type: str
    path: Path
    signature_path: str = None

    @property
    def _identifier(self):
        return self.distribution, self.tag, self.architecture, self.package_type, self.path.name

    def to_dict(self, root):
        return {i: j.relative_to(root).as_posix() if isinstance(j, Path) else j
                for (i, j) in self.__dict__.items()}


class Dependency(str):
    @staticmethod
    def __new__(cls, name, origin):
        self = super().__new__(cls, name)
        self.origin = origin
        return self


def expand_pip_requirements(requirement, cwd, source, extras=None):
    if m := re.match("-r *([^ ].*)", requirement):
        # e.g. "-r requirements.txt"
        requirements_txt = cwd / m[1]
        text = requirements_txt.read_text("utf-8")
        for child in re.findall(r"^ *([^#\n\r]+)", text, re.MULTILINE):
            yield from expand_pip_requirements(child.strip(),
                                               requirements_txt.parent,
                                               requirements_txt)

    elif m := re.match(r" *([^]]+) *\[([^]]+)\]", requirement):
        if m[1] == ".":
            # e.g. ".[test]"
            for group in re.findall("[^ ,]+", m[2]):
                for extra in extras[group]:
                    yield from expand_pip_requirements(extra, cwd, "pyproject.toml")
        else:
            # e.g. "package[extra]"
            # Ignore extras from other packages. Figuring out what an extra
            # contains would require checking the version of the given package
            # available on each Linux distribution, downloading the wheel from
            # PyPI for whatever that version is, then fishing the metadata out
            # from the wheel.
            yield Dependency(m[1], source)

    else:
        yield Dependency(requirement, source)


def check_maintainer(name):
    if re.search(r"\b(the|team|et al\.?|contributors|and|development|developers"
                 r"|llc|inc\.?|limited)\b", name.lower()):
        from polycotylus._exceptions import comment, key, string
        raise _exceptions.PresubmitCheckError(
            f'Maintainer {string(repr(name))} appears to be a generic team or '
            'organization name. Linux repositories require personal contact details. '
            "Set them in the polycotylus.yaml:\n\n"
            f"{comment('# polycotylus.yaml')}\n{key('maintainer')}: your name <your@email.org>"
        )


trove_to_spdx = json.loads(_misc.read_resource("trove-spdx-licenses.json"))
spdx_osi_approved = set(re.findall("[^\n]+", _misc.read_resource("spdx-osi-approved.txt").decode()))
spdx_exceptions = set(re.findall("[^\n]+", _misc.read_resource("spdx-exceptions.txt").decode()))

if __name__ == "__main__":
    self = Project.from_root(".")
    self.write_desktop_files()
    self.write_gitignore()
