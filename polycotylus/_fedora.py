"""
Basic tutorial: https://docs.fedoraproject.org/en-US/package-maintainers/Packaging_Tutorial_GNU_Hello
Python specific tutorial: https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/
Nice template: https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_empty_spec_file
.spec format: https://rpm-software-management.github.io/rpm/manual/spec.html
Examples: https://src.fedoraproject.org/rpms/python-pyperclip/blob/rawhide/f/python-pyperclip.spec
"""

import re
import contextlib
import shlex
from functools import lru_cache
import platform
import os
from pathlib import Path

from packaging.requirements import Requirement

from polycotylus import _misc, _docker, _exceptions
from polycotylus._project import TestCommandLexer
from polycotylus._mirror import cache_root
from polycotylus._base import BaseDistribution, _deduplicate, GPGBased


class Fedora(GPGBased, BaseDistribution):
    name = "fedora"
    version = "42"
    python_extras = {
        "tkinter": ["python3-tkinter"],
    }
    _formatter = _misc.Formatter("    ")
    mirror = contextlib.nullcontext()
    supported_architectures = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
    }
    _packages = {
        "python": "python3",
        "xvfb-run": "/usr/bin/xvfb-run",
        "image-conversion": ["ImageMagick"],
        "svg-conversion": ["ImageMagick", "librsvg2-tools"],
        "font": "dejavu-fonts-all",
    }

    def __init__(self, project, architecture=None, signing_id=None):
        if platform.system() == "Windows":  # pragma: no cover
            # The mounting of DNF's cache onto the host filesystem requires UNIX
            # permissions that Windows filesystems lack support for.
            raise _exceptions.PolycotylusUsageError(
                "Building for Fedora is not supported on Windows.")
        super().__init__(project, architecture, signing_id)
        if self.project.architecture == "none":
            self.architecture = "noarch"

    available_packages = NotImplemented

    @_misc.classproperty
    def tag(_, cls):
        return cls.version

    @_misc.classproperty
    def base_image(_, cls):
        return "docker.io/fedora:" + cls.version

    @staticmethod
    def fix_package_name(name):
        return re.sub(r"[^a-z0-9]+", "-", name.lower())

    @classmethod
    def python_package_convention(cls, name):
        # https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_naming
        return re.sub("^(?:python-)?(.*)", r"python3-\1", cls.fix_package_name(name))

    @classmethod
    @lru_cache()
    def python_version(cls):
        command = ["dnf", "info", "python3"]
        output = _docker.run(cls.base_image, command, volumes=cls._mounted_caches, verbosity=0).output
        return re.search(r"Version\s*:\s*(.+)", output)[1]

    @classmethod
    def python_package(cls, requirement, _=None):
        requirement = Requirement(requirement)
        requirement.name = f"python3dist({cls.fix_package_name(requirement.name)})"
        if not cls.evaluate_requirements_marker(requirement):
            return
        else:
            requirement.marker = None
        return str(requirement).replace(">=", " >= ")

    @property
    def dependencies(self):
        out = [(self._packages["python"] + self.project.supported_python).replace(">=", " >= ")]
        out += self._dependencies(self.project.dependencies)
        return _deduplicate(out)

    @property
    def build_dependencies(self):
        return _deduplicate(["python3-devel"] + super().build_dependencies[2:])

    def spec(self):
        out = self._formatter(f"""
            Name:           {self.package_name}
            Version:        {self.project.version}
            Release:        1%{{?dist}}
            Summary:        {self.project.description}
            License:        {self.project.license_spdx}
            URL:            {self.project.url}
            Source0:        {self.project.source_url.format(version="%{version}")}
        """)
        out += "\n"
        if self.project.architecture == "none":
            out += "BuildArch:      noarch\n"
        build_requires = []
        for group in (self.project.build_dependencies, self.project.test_dependencies):
            build_requires += group.get("fedora", ())
        for dependency in self.project.test_dependencies.get("pip", ()):
            build_requires.append(self.python_package(dependency))
        if self.project.gui:
            build_requires.append(self._packages["xvfb-run"])
        if self.icons:
            if any(not source.endswith(".svg") for (source, _) in self.icons):
                build_requires += self._packages["image-conversion"]
            if any(source.endswith(".svg") for (source, _) in self.icons):
                build_requires += self._packages["svg-conversion"]
        for dependency in _deduplicate(build_requires):
            out += f"BuildRequires:  {dependency}\n"
        for extra in self.project.dependencies.get("python", ()):
            for package in self.python_extras[extra]:
                out += f"BuildRequires:  {package}\n"
                out += f"Requires:       {package}\n"
        for package in self.project.dependencies["pip"]:
            if package.origin == "polycotylus.yaml":
                out += f"Requires:       {self.python_package(package)}\n"
        for package in self.project.dependencies.get(self.name, ()):
            out += f"Requires:       {package}\n"
        out += "\n\n"
        out += self._formatter(f"""
            %description
            foo


            %prep
            %autosetup -p1 -n {self.project.source_top_level.format(version="%{version}")}


            %generate_buildrequires
        """)
        if self.project.setuptools_scm:
            out += self._formatter('export SETUPTOOLS_SCM_PRETEND_VERSION="%{version}"')
        out += self._formatter("""
            %pyproject_buildrequires


            %build
        """)
        if self.project.setuptools_scm:
            out += self._formatter('export SETUPTOOLS_SCM_PRETEND_VERSION="%{version}"')
        out += self._formatter("""
            %pyproject_wheel


            %install
            %pyproject_install
            %pyproject_save_files "*"
        """)
        out += self.install_icons(0, "%{buildroot}").replace("/usr/share", "/%{_datadir}")
        if self.project.desktop_entry_points:
            out += self._formatter(r"""
                desktop-file-install \
                    --dir=%{{buildroot}}%{{_datadir}}/applications \
                    %{{_builddir}}/{}/.polycotylus/*.desktop
            """.format(self.project.source_top_level.format(version="%{version}")))

        out += "\n\n%check\n"
        # '%' is a special character to RPM specs and needs to be escaped.
        escaped = TestCommandLexer(self.project.test_command.template.replace("%", "%%"))
        # Fedora expects you to use a hellish mess of macros.
        #  * %pytest expands to SOME=random ENVIRONMENT=variables /usr/bin/pytest
        #  * %python3 (usually written as %{python3}) expands to /usr/bin/python3
        #  * %tox expands to MORE=variables /usr/bin/python3 -m tox --current-env -q --recreate -e py313
        #    (although a package test using tox is a complete waste of time)
        # Due to the prepended inline environment variables, %pytest can only be
        # safely used if there's nothing before it (xvfb-run %pytest)
        allow_pytest_macro = escaped.template.strip().find("+pytest+") == 0
        test_command = escaped.evaluate(lambda x: {
            "python": "%{python3}",
            "pytest": "%pytest" if allow_pytest_macro else "%{python3} -m pytest",
        }.get(x, x))
        # Double blank lines signify the end of the tests block so mustn't be
        # present in the test command.
        test_command = re.sub("([\t ]*\n){3,}", "\n\n", test_command)
        out += self._formatter(test_command)
        out += "\n\n" + self._formatter(f"""
            %files -n {self.package_name} -f %{{pyproject_files}}
        """)
        licenses = shlex.join(self.project.licenses).replace("'", '"')
        out += f"%license {licenses}\n"
        for script in sorted(self.project.scripts):
            out += f"%{{_bindir}}/{script}\n"
        for (_, name) in self.icons:
            out += f"%{{_datadir}}/icons/hicolor/*/apps/{name}.png\n"
        for (source, dest) in self.icons:
            if source.endswith(".svg"):
                out += f"%{{_datadir}}/icons/hicolor/scalable/apps/{dest}.svg\n"
        for id in self.project.desktop_entry_points:
            out += f"%{{_datadir}}/applications/{id}.desktop\n"
        out += "\n\n"
        out += self._formatter(f"""
            %changelog
            * Sat Sep 17 2022 {self.project.maintainer_slug} - {self.project.version}-1
            - Initial version of the package
        """)
        return out

    dnf_config = _formatter("""
        [main]
        gpgcheck=True
        installonly_limit=3
        clean_requirements_on_remove=True
        best=True
        skip_if_unavailable=False
        tsflags=nodocs
        keepcache=1
        install_weak_deps=False
    """)
    dnf_config_install = f"echo -e {repr(dnf_config)} > /etc/dnf/dnf.conf"

    def dockerfile(self):
        return self._formatter(f"""
            FROM {self.base_image} AS base

            {self._install_user()}
            RUN groupadd --users user mock

            RUN {self.dnf_config_install}
            RUN mkdir -p /var/cache/mock /var/cache/dnf

            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base AS build

            FROM base AS test
            # This seemingly redundant layer of indirection ensures that
            # xvfb-run (which calls exec) is never the top level process in the
            # container which otherwise leads to exec stalling.
            RUN echo -e '#!/usr/bin/env sh\\n"$@"' >> /bin/intermediate
            RUN chmod +x /bin/intermediate
            ENTRYPOINT ["/bin/intermediate"]
            CMD ["bash"]
    """)

    @classmethod
    def build_base_packages(cls):
        return set()

    def generate(self):
        super().generate()
        for path in self.distro_root.glob("*.spec"):
            path.unlink()
        _misc.unix_write(self.distro_root / f"{self.package_name}.spec", self.spec())

    @_misc.classproperty
    def _mounted_caches(_, cls):
        if int(cls.version) >= 41:
            dnf_cache = cache_root / f"fedora-{cls.version}-libdnf5-{_docker.docker.variant}"
            dnf_cache.mkdir(parents=True, exist_ok=True)
            return [(dnf_cache, "/var/cache/libdnf5")]
        else:
            mock_cache = cache_root / ("fedora-mock2-" + _docker.docker.variant)
            mock_cache.mkdir(parents=True, exist_ok=True)
            dnf_cache = cache_root / ("fedora-dnf-" + _docker.docker.variant)
            dnf_cache.mkdir(parents=True, exist_ok=True)
            return [(mock_cache, "/var/cache/mock"), (dnf_cache, "/var/cache/dnf")]

    def build_builder_image(self):
        base = super().build_builder_image()
        command = ["dnf", "install", "-y", "fedpkg", "python3dist(wheel)", "python3dist(pip)", "rpm-sign", "pinentry-tty"] + \
            self.build_dependencies + self.dependencies + self.test_dependencies
        return _docker.lazy_run(base, command, tty=True, volumes=self._mounted_caches,
                                architecture=self.docker_architecture)

    def build_test_image(self):
        command = ["dnf", "install", "-y"] + self.test_dependencies
        if self.project.gui:
            command.append("util-linux")
        elif not self.test_dependencies:
            return super().build_test_image()
        return _docker.lazy_run(super().build_test_image(), command, tty=True,
                                volumes=self._mounted_caches,
                                architecture=self.docker_architecture)

    def build(self):
        machine = self.architecture
        command = ["fedpkg", "--release", "f" + self.version, "compile", "--", "-bb"]
        if self.signing_id:
            gpg_home = os.environ.get("GNUPGHOME", Path.home() / ".gnupg")
            gpg_volume = [(str(gpg_home), "/home/user/.gnupg")]
            command = self._formatter(f"""
                {shlex.join(command)}
                gpg --export -a '{self.signing_id}' > /tmp/key
                sudo rpmkeys --import /tmp/key
                echo '%_gpg_name {self.signing_id}' > ~/.rpmmacros
                rpm --addsign {self.architecture}/{self.package_name}-*{self.project.version}-*.{machine}.rpm
            """)
        else:
            gpg_volume = []
        with self.mirror:
            _docker.run(self.build_builder_image(), command,
                        tty=True, root=False, interactive=bool(self.signing_id),
                        volumes=[(self.distro_root, "/io")] + gpg_volume + self._mounted_caches,
                        architecture=self.docker_architecture, post_mortem=True)
        rpms = {}
        pattern = re.compile(
            fr"{re.escape(self.package_name)}(?:-([^-]+))?-{self.project.version}.*\.{machine}\.rpm")
        for path in (self.distro_root / machine).glob(f"*.fc{self.version}.*.rpm"):
            if m := pattern.match(path.name):
                rpms[m[1] or "main"] = self._make_artifact(path, m[1] or "main")
        assert "main" in rpms
        return rpms

    def test(self, rpm):
        volumes = [(rpm.path.parent, "/pkg")] + self._mounted_caches
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        test_dependencies = []
        for package in self.project.test_dependencies["pip"]:
            test_dependencies.append(self.python_package(package))
        test_command = self.project.test_command.evaluate(
            lambda x: "python3" if x == "python" else x)
        with self.mirror:
            return _docker.run(self.build_test_image(), f"""
                sudo dnf install -y /pkg/{rpm.path.name}
                {test_command}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)


class Fedora37(Fedora):
    version = "37"
    _imagemagick_convert = BaseDistribution._imagemagick_convert_legacy


class Fedora38(Fedora):
    version = "38"


class Fedora39(Fedora):
    version = "39"


class Fedora40(Fedora):
    version = "40"


class Fedora41(Fedora):
    version = "41"


Fedora42 = Fedora


class Fedora43(Fedora):
    version = "43"


class Fedora44(Fedora):
    version = "44"
