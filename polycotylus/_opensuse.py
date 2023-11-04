"""
Generic guide: https://en.opensuse.org/openSUSE:Packaging_guidelines
Python guide: https://en.opensuse.org/openSUSE:Packaging_Python
Approximate template: https://github.com/openSUSE/py2pack/blob/master/py2pack/templates/opensuse.spec
"""

import re
import os
from functools import lru_cache
from datetime import datetime
import platform
import shlex
import itertools

from packaging.requirements import Requirement

from polycotylus import _docker, _misc, _exceptions
from polycotylus._base import BaseDistribution


class OpenSUSE(BaseDistribution):
    base_image = "docker.io/opensuse/tumbleweed"
    tag = "tumbleweed"
    python_extras = {
        "tkinter": ["python3-tk"],
        "curses": ["python3-curses"],
        "curses.panel": ["python3-curses"],
        "dbm": ["python3-dbm"],
        "dbm.gnu": ["python3-dbm"],
        "dbm.ndbm": ["python3-dbm"],
    }
    supported_architectures = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
    }
    _formatter = _misc.Formatter("    ")
    _packages = {
        "python": "python3",
        "xvfb-run": "xvfb-run",
        "imagemagick": "ImageMagick",
        "imagemagick_svg": "librsvg",
        "font": "dejavu-fonts",
    }

    def __init__(self, project, architecture=None):
        if _docker.docker.variant == "podman":  # pragma: no cover
            # I think the incompatibility is in OpenSUSE's use of anonymous
            # UIDs. Leads to permission errors writing to /dev/null.
            raise _exceptions.PolycotylusUsageError(
                "Building for OpenSUSE is not supported with podman.")
        super().__init__(project, architecture)
        if self.project.architecture == "none":
            self.architecture = "noarch"

    @classmethod
    @lru_cache()
    def _package_manager_queries(cls):
        with cls.mirror:
            container = _docker.run(cls.base_image, f"""
                {cls.mirror.install_command}
                zypper refresh
                zypper search > /packages
                zypper info --requires osc > /osc-info
                zypper search --details '/python[0-9]+-base$/' > /python-versions
                zypper search --details 'python*-rpm' > /python-rpm-info
            """, tty=True)
        _read = lambda path: container.file(path).decode()
        _table = lambda x: dict(re.findall(r"^[^S] \| ([^ ]+) +\|[^|]+\| ([^ |]+)", x, re.M))
        cls._available_packages = {
            line.split("|")[1].strip()
            for line in _read("/packages").splitlines() if "|" in line
        }
        cls._build_base_packages = set()
        python_abi = re.search(r"python\(abi\) = (\S+)", _read("/osc-info"))[1]
        default_python_base = f"python{python_abi.replace('.', '')}-base"
        cls._python_version = _table(_read("/python-versions"))[default_python_base].split("-")[0]

        cls._active_python_abis = [
            i.split("-")[0] for i in _table(_read("/python-rpm-info"))]
        cls._default_python_abi = f"python{python_abi.replace('.', '')}"

    @classmethod
    def active_python_abis(cls):
        cls._package_manager_queries()
        return cls._active_python_abis

    @classmethod
    def default_python_abi(cls):
        cls._package_manager_queries()
        return cls._default_python_abi

    @classmethod
    def python_package_convention(cls, pypi_name):
        return "python-" + cls.fix_package_name(pypi_name)

    @staticmethod
    def fix_package_name(name):
        return re.sub(r"[^a-z0-9]+", "-", name.lower())

    @classmethod
    def python_package(cls, requirement, _=None):
        requirement = Requirement(requirement)
        name = re.sub("[._-]+", "-", requirement.name.lower())
        available = cls.available_packages_normalized()

        if not cls.evaluate_requirements_marker(requirement):
            return
        else:
            requirement.marker = None
        if (with_prefix := cls.default_python_abi() + "-" + name) in available:
            name = available[with_prefix][len(cls.default_python_abi()) + 1:]
        elif (with_prefix := cls.default_python_abi() + "-" + re.match("(?:python|py)?-?(.+)", name)[1]) in available:
            name = available[with_prefix][len(cls.default_python_abi()) + 1:]
        else:
            raise _exceptions.PackageUnavailableError(requirement.name, cls.name)

        requirement.name = name
        requirement.extras = set()
        requirement = str(requirement).replace(">=", " >= ")
        return f"%{{python_module {requirement}}}"

    @property
    def build_dependencies(self):
        out = ["python-rpm-macros", "fdupes"] + super().build_dependencies
        if self.project.architecture != "none":
            out.append("%{python_module devel}")
        if self.project.desktop_entry_points:
            out.append("update-desktop-files")
        if self.icons:
            out.append("hicolor-icon-theme")
        return out

    def _dependencies(self, dependencies):
        out = super()._dependencies(dependencies)
        to_replace = set().union(*(set(i) for i in self.python_extras.values()))
        for (i, dependency) in enumerate(out):
            if dependency in to_replace:
                out[i] = f"%{{python_module {dependency.split('python3-')[1]}}}"
        return out

    @property
    def dependencies(self):
        out = super().dependencies
        out.remove("python3" + self.project.supported_python)
        return out

    def spec(self):
        licenses = [{"custom": "NonFree"}.get(i, i) for i in self.project.license_names]
        out = self._formatter(f"""
            #
            # spec file for package {self.package_name}
            #
            # Copyright (c) {datetime.today().year} SUSE LLC
            #
            # All modifications and additions to the file contributed by third parties
            # remain the property of their copyright owners, unless otherwise agreed
            # upon. The license for this file, and modifications and additions to the
            # file, is the same license as for the pristine package itself (unless the
            # license for the pristine package is not an Open Source License, in which
            # case the license is the MIT License). An "Open Source License" is a
            # license that conforms to the Open Source Definition (Version 1.9)
            # published by the Open Source Initiative.

            # Please submit bugfixes or comments via https://bugs.opensuse.org/
            #


            %define {"pythons python3" if self.project.frontend else "skip_python2 1"}
            Name:             {self.package_name}
            Version:          {self.project.version}
            Release:          0
            Summary:          {self.project.description.rstrip(".")}
            License:          {" AND ".join(licenses)}
            URL:              {self.project.url}
            Source:           {self.project.source_url.format(version='%{version}')}
        """)
        for dependency in self.build_dependencies:
            out += self._formatter(f"BuildRequires:    {dependency}")
        if self.dependencies or self.test_dependencies:
            out += self._formatter("# SECTION test requirements")
            for dependency in self.dependencies + self.test_dependencies:
                out += self._formatter(f"BuildRequires:    {dependency}")
            out += self._formatter("# /SECTION")
        for dependency in self.dependencies:
            # For unspecified reasons, runtime dependencies use python-numpy
            # whereas build and test dependencies use %{python_module numpy}.
            # https://en.opensuse.org/openSUSE:Packaging_Python#Requires,_Provides_and_similar
            dependency = re.sub(r"%\{python_module ([^}]+)\}", r"python-\1", dependency)
            out += self._formatter(f"Requires:         {dependency}")
        if not self.project.frontend:
            out += self._formatter("""
                Requires(post):   update-alternatives
                Requires(postun): update-alternatives
            """)
        if self.project.architecture == "none":
            out += self._formatter("BuildArch:        noarch")
        out += "\n%python_subpackages\n\n"
        out += self._formatter(f"""
            %description
            foo

            %prep
            %autosetup -p1 -n {self.project.source_top_level.format(version="%{version}")}

            %build
        """)
        if self.project.architecture != "none":
            out += self._formatter('export CFLAGS="%{optflags}"')
        if self.project.setuptools_scm:
            out += self._formatter("export SETUPTOOLS_SCM_PRETEND_VERSION=%{version}")
        out += self._formatter("""
            %pyproject_wheel

            %install
            %pyproject_install
        """) + "\n"
        if self.project.architecture == "none":
            site_packages = "%{buildroot}%{python_sitelib}"
        else:
            site_packages = "%{buildroot}%{python_sitearch}"
        if not self.project.frontend:
            for script in self.project.scripts:
                out += self._formatter(f"%python_clone -a %{{buildroot}}%{{_bindir}}/{script}")
        if self.project.frontend:
            out += self._formatter(f"%fdupes {site_packages}")
        else:
            out += self._formatter(f"%python_expand %fdupes {site_packages}")
        if self.project.desktop_entry_points:
            out += self._formatter("mkdir -p %{buildroot}%{_datadir}/applications/")
        for id in self.project.desktop_entry_points:
            top_level = self.project.source_top_level.format(version="%{version}")
            out += self._formatter(f"""
                cp %_builddir/{top_level}/.polycotylus/{id}.desktop %{{buildroot}}%{{_datadir}}/applications/
                %suse_update_desktop_file %{{buildroot}}%{{_datadir}}/applications/{id}.desktop
            """)
        out += self.install_icons(0, "%{buildroot}").replace("/usr/share", "%{_datadir}")
        out += "\n"

        out += self._formatter("%check")
        out += self.test_command + "\n"
        if self.project.scripts and not self.project.frontend:
            out += "\n"
            out += self._formatter(f"""
                %post
                %python_install_alternative {_join(self.project.scripts)}

                %postun
                %python_uninstall_alternative {_join(self.project.scripts)}
            """)
        out += "\n"
        out += self._formatter(f"""
            %files %{{python_files}}
            %license {_join(self.project.licenses)}
        """)
        for script in self.project.scripts:
            if self.project.frontend:
                out += self._formatter(f"%{{_bindir}}/{script}")
            else:
                out += self._formatter(f"%python_alternative %{{_bindir}}/{script}")
        out += self._formatter(f"%{'python_sitearch' if self.project.architecture != 'none' else 'python_sitelib'}/*")
        for id in self.project.desktop_entry_points:
            out += self._formatter(f"%{{_datadir}}/applications/{id}.desktop")
        for (source, dest) in self.icons:
            if source.endswith(".svg"):  # pragma: no branch
                out += self._formatter(f"%{{_datadir}}/icons/hicolor/scalable/apps/{dest}.svg")
            out += self._formatter(f"%{{_datadir}}/icons/hicolor/*/apps/{dest}.png")
        out += "\n"

        out += self._formatter("%changelog")
        return out

    def dockerfile(self):
        dependencies = []
        for dependency in itertools.chain(self.build_dependencies, self.test_dependencies, self.dependencies):
            if m := re.fullmatch(r"%\{python_module ([^}]+)\}", dependency):
                for python in self.active_python_abis():
                    dependencies.append(python + "-" + m[1])
            else:
                dependencies.append(dependency)

        test_dependencies = []
        for dependency in self.test_dependencies:
            if m := re.fullmatch(r"%\{python_module ([^}]+)\}", dependency):
                test_dependencies.append(self.default_python_abi() + "-" + m[1])
            else:
                test_dependencies.append(dependency)

        out = self._formatter(f"""
            FROM {self.base_image} as base
            RUN {self.mirror.install_command}

            RUN mkdir /io
            WORKDIR /io

            FROM base AS build
            RUN zypper install -y which osc build perl-XML-Parser hostname python3-pip python3-setuptools awk
            # OpenSUSE's build tool "build" creates a fakeroot environment in
            # which it reinstalls all the base packages plus some core build
            # tools and all the declared dependencies. Unfortunately, it
            # downloads them one at a time in separate zypper processes meaning
            # that even bare-bones packages take several minutes to build – even
            # when polycotylus's package cache is able to serve zypper the
            # packages immediately. To work around this, symlink `build` and
            # zypper's caches together (so they share a cache) then have zypper
            # download (but not install) all the above packages.
            RUN mkdir -p /var/cache/build
            RUN for repo in /etc/zypp/repos.d/*.repo; do name=$(basename -s .repo $repo); hash=$(echo -n zypp://$name | md5sum | grep -Eo '[a-f0-9]+') ; ln -s /var/cache/zypp/packages/$name /var/cache/build/$hash ; done
            RUN zypper install -dfy rpm-build $(zypper search --installed-only --type=package | grep 'i. |' | awk '{{ print $3 }}') python-rpm-macros update-alternatives {shlex.join(dependencies)}

            FROM base AS test
            RUN zypper install -y shadow sudo
            RUN groupadd wheel
            {self._install_user()}
            RUN chown -R user /io
        """)
        if test_dependencies:
            out += f"RUN zypper install -y {shlex.join(test_dependencies)}\n"
        return out

    @property
    def test_command(self):
        command = self.project.test_command
        tokenizer = re.compile(r"( ?)\b(?:(python +-m *unittest)|(python)|(pytest))\b")
        if any(match[1] or match[3] for match in tokenizer.finditer(command)):
            command = tokenizer.sub(lambda m: m[1] + "$python -m pytest" if m[4] else m[1] + "$" + (m[2] or m[3]),
                                    self.project.test_command)
            if "\n" in command.strip():
                command = "%{python_expand export PYTHONPATH=%{buildroot}" \
                    + ("%{$python_sitelib}" if self.project.architecture == "none" else "%{$python_sitearch}") \
                    + "\n" + self._formatter(command) + "}\n"
            else:
                command = "%python_expand " + command
        elif self.project.architecture != "none":
            command = tokenizer.sub(lambda m: "%pytest_arch" if m[4] else "%pyunittest_arch", command)
        else:
            command = tokenizer.sub(lambda m: "%pytest" if m[4] else "%pyunittest", command)
        return command.strip(" \n")

    def generate(self):
        super().generate()
        (self.distro_root / "RPMS").mkdir(exist_ok=True)
        for path in self.distro_root.glob("*.spec"):
            path.unlink()
        _misc.unix_write(self.distro_root / (self.package_name + ".spec"), self.spec())

    def build(self):
        uid = "1000:1000" if platform.system() == "Windows" else f"{os.getuid()}:{os.getgid()}"
        command = ["build", f"--uid={uid}", "--dist=tumbleweed", "--vm-network"]
        volumes = [(self.distro_root, "/io"),
                   (self.distro_root / "RPMS", "/var/tmp/build-root/home/abuild/rpmbuild/RPMS")]
        with self.mirror:
            _docker.run(self.build_builder_image(), command, "--privileged",
                        volumes=volumes, post_mortem=True, tty=True,
                        architecture=self.docker_architecture)
        rpms = {}
        for python in ["python3"] if self.project.frontend else self.active_python_abis():
            arch = self.architecture
            name = f"{python}-{self.fix_package_name(self.project.name)}-{self.project.version}-0.{arch}.rpm"
            rpm = self.distro_root / "RPMS" / arch / name
            rpms["main" if self.project.frontend else python] = rpm
            assert rpm.exists(), rpm
            if python == self.default_python_abi():
                rpms["main"] = rpm
        return rpms

    def test(self, package):
        with self.mirror:
            base = self.build_test_image()
            volumes = [(package.parent, "/pkg")]
            for path in self.project.test_files:
                volumes.append((self.project.root / path, f"/io/{path}"))
            test_command = re.sub(r"\bpython\b", "python3", self.project.test_command)
            return _docker.run(base, f"""
                sudo zypper install --allow-unsigned-rpm -y /pkg/{package.name}
                {test_command}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)


def _join(args):
    return " ".join('"' + i + '"' if " " in i else i for i in args)
