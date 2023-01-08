"""
Tutorial: https://docs.fedoraproject.org/en-US/package-maintainers/Packaging_Tutorial_GNU_Hello
.spec format: https://rpm-software-management.github.io/rpm/manual/spec.html
Examples: https://src.fedoraproject.org/rpms/python-pyperclip/blob/rawhide/f/python-pyperclip.spec
"""

import re
from functools import cache
import platform
import os

import tomli

from polycotylus import _shell, _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors, cache_root
from polycotylus._base import BaseDistribution, _deduplicate


class Fedora(BaseDistribution):
    name = "fedora"
    python_prefix = "/usr"
    python_extras = {
        "tkinter": ["python3-tkinter"],
        "sqlite3": [],
        "decimal": [],
        "lzma": [],
        "zlib": [],
        "readline": [],
        "bz2": [],
    }
    xvfb_run = "/usr/bin/xvfb-run"
    _formatter = _shell.Formatter("")
    mirror = mirrors[name]
    font = "dejavu-fonts-all"

    @classmethod
    @cache
    def available_packages(cls):
        with cls.mirror:
            output = _docker.run("fedora:37", f"""
                {cls.mirror.install}
                yum repoquery -q
            """, verbosity=0).output
        return set(re.findall(r"([^\n:]+)-\d+:", output))

    invalid_package_characters = r"[^\w\-_+.]"

    @staticmethod
    def fix_package_name(name):
        return name

    @staticmethod
    def python_package_convention(pypi_name):
        return "python3-" + pypi_name

    def spec(self):
        out = self._formatter(f"""
            Name:           {self.package_name}
            Version:        {self.project.version}
            Release:        1%{{?dist}}
            Summary:        {self.project.description}
            License:        {" AND ".join(self.project.license_names)}
            URL:            {self.project.url}
            Source0:        {self.project.source_url.format(version="%{version}")}
        """)
        out += "\n"
        if self.project.architecture == "none":
            out += "BuildArch:      noarch\n"
        build_requires = ["python3-devel"]
        for group in (self.project.build_dependencies, self.project.test_dependencies):
            build_requires += group.get("fedora", ())
        for dependency in self.project.test_dependencies.get("pip", ()):
            build_requires.append(f"python3dist({dependency})")
        if self.project.gui:
            build_requires.append(self.xvfb_run)
        for dependency in _deduplicate(build_requires):
            out += f"BuildRequires:  {dependency}\n"
        for extra in self.project.dependencies.get("python", ()):
            for package in self.python_extras[extra]:
                out += f"BuildRequires:  {package}\n"
                out += f"Requires:       {package}\n"
        out += "\n\n"
        out += self._formatter(f"""
            %description
            foo


            %prep
            %autosetup -p1 -n {self.project.name}-%{{version}}


            %generate_buildrequires
            %pyproject_buildrequires


            %build
            %pyproject_wheel


            %install
            %pyproject_install
            %pyproject_save_files {self.project.name}


            %check
        """)
        if self.project.gui:
            out += "%global __pytest /usr/bin/xvfb-run -a %{python3} -m pytest\n"
        out += self._formatter(f"""
            %pytest


            %files -n {self.package_name} -f %{{pyproject_files}}
        """)
        for license in self.project.licenses:
            out += f"%license {license}\n"
        options = tomli.loads((self.project.root / "pyproject.toml").read_text())
        for variant in ("gui-scripts", "scripts"):
            for script in options["project"].get(variant, ()):
                out += f"%{{_bindir}}/{script}\n"
        out += "\n"
        out += self._formatter(f"""
            %changelog
            * Sat Sep 17 2022 {self.project.maintainer_slug} - {self.project.version}-1
            - Initial version of the package
        """)
        return out

    def dockerfile(self):
        dnf_config = self._formatter("""
            [main]
            gpgcheck=True
            installonly_limit=3
            clean_requirements_on_remove=True
            best=True
            skip_if_unavailable=False
            tsflags=nodocs\nkeepcache=1
        """)
        return self._formatter(f"""
            FROM fedora:37 AS base
            RUN echo '%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
            RUN useradd --create-home --gid wheel --uid {os.getuid()} user
            RUN groupadd --users user mock
            RUN echo -e {repr(dnf_config)} > /etc/dnf/dnf.conf

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
        (self.distro_root / f"{self.package_name}.spec").write_text(self.spec())

    @property
    def _mounted_caches(self):
        mock_cache = cache_root / "fedora-mock"
        mock_cache.mkdir(parents=True, exist_ok=True)
        dnf_cache = cache_root / "fedora-dnf"
        dnf_cache.mkdir(parents=True, exist_ok=True)
        return [(mock_cache, "/var/cache/mock"), (dnf_cache, "/var/cache/dnf")]

    def build(self):
        mock_cache = cache_root / "fedora-mock"
        mock_cache.mkdir(parents=True, exist_ok=True)
        _docker.run(self.build_builder_image(), """
                sudo yum install -y fedpkg
                fedpkg --release f37 mockbuild
            """, "--privileged", tty=True, root=False,
                    volumes=[(self.distro_root, "/io")] + self._mounted_caches,
                    )
        rpms = {}
        pattern = re.compile(fr"{re.escape(self.package_name)}(?:-([^-]+))?-{self.project.version}.*\.(?:{platform.machine()}|noarch)\.rpm")

        for path in (self.distro_root / f"results_{self.package_name}/{self.project.version}").glob("*.fc37/*.rpm"):
            if m := pattern.match(path.name):
                rpms[m[1] or "main"] = path
        assert "main" in rpms
        return rpms

    def test(self, rpm):
        volumes = [(rpm.parent, "/pkg")] + self._mounted_caches
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        return _docker.run(self.build_test_image(), f"""
            dnf install -y /pkg/{rpm.name}
            yum install -y {" ".join(self.test_dependencies)} util-linux
            {self.project.test_command}
        """, volumes=volumes, tty=True)


if __name__ == "__main__":
    self = Fedora(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
