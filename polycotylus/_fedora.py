"""
Basic tutorial: https://docs.fedoraproject.org/en-US/package-maintainers/Packaging_Tutorial_GNU_Hello
Python specific tutorial: https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/
Nice template: https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_empty_spec_file
.spec format: https://rpm-software-management.github.io/rpm/manual/spec.html
Examples: https://src.fedoraproject.org/rpms/python-pyperclip/blob/rawhide/f/python-pyperclip.spec
"""

import re
import platform
import contextlib
import shlex

import toml
import pkg_resources

from polycotylus import _shell, _docker
from polycotylus._project import Project
from polycotylus._mirror import cache_root
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
    imagemagick = "ImageMagick"
    imagemagick_svg = "librsvg2-tools"
    _formatter = _shell.Formatter("    ")
    mirror = contextlib.nullcontext()
    font = "dejavu-fonts-all"
    pkgdir = "%{buildroot}"

    available_packages = NotImplemented
    fix_package_name = NotImplemented
    invalid_package_characters = r"[^\w\-_+.]"

    @staticmethod
    def fix_package_name(name):
        return re.sub(r"[^a-z0-9]+", "-", name.lower())

    @classmethod
    def python_package_convention(cls, name):
        # https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_naming
        return re.sub("^(?:python-)?(.*)", r"python3-\1", cls.fix_package_name(name))

    @classmethod
    def python_package(cls, requirement):
        requirement = pkg_resources.Requirement(requirement)
        requirement.name = "python3dist({})".format(requirement.name)
        return str(requirement).replace(">=", " >= ")

    @property
    def dependencies(self):
        out = [(self.python + self.project.supported_python).replace(">=", " >= ")]
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
            License:        {" AND ".join(self.project.license_names)}
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
            build_requires.append(f"python3dist({dependency})")
        if self.project.gui:
            build_requires.append(self.xvfb_run)
        if self.icons:
            build_requires.append(self.imagemagick)
            if any(source.endswith(".svg") for (source, _) in self.icons):
                build_requires.append(self.imagemagick_svg)
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
            %autosetup -p1 -n {self.project.source_top_level.format(version="%{version}")}


            %generate_buildrequires
            %pyproject_buildrequires


            %build
            %pyproject_wheel


            %install
            %pyproject_install
            %pyproject_save_files "*"
        """)
        out += self.install_icons(0).replace("/usr/share", "/%{_datadir}")
        if self.project.desktop_entry_points:
            out += self._formatter(r"""
                desktop-file-install \
                    --dir=%{{buildroot}}%{{_datadir}}/applications \
                    %{{_builddir}}/{}/.polycotylus/*.desktop
            """.format(self.project.source_top_level.format(version="%{version}")))

        out += "\n\n%check\n"
        if self.project.gui:
            out += "%global __pytest /usr/bin/xvfb-run -a %{python3} -m pytest\n"
        out += self._formatter(f"""
            %pytest


            %files -n {self.package_name} -f %{{pyproject_files}}
        """)
        licenses = shlex.join(self.project.licenses).replace("'", '"')
        out += f"%license {licenses}\n"
        options = toml.load(self.project.root / "pyproject.toml")
        for variant in ("gui-scripts", "scripts"):
            for script in options["project"].get(variant, ()):
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
    """)
    dnf_config_install = f"echo -e {repr(dnf_config)} > /etc/dnf/dnf.conf"

    def dockerfile(self):
        return self._formatter(f"""
            FROM fedora:37 AS base

            {self._install_user()}
            RUN groupadd --users user mock

            RUN {self.dnf_config_install}

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
        mock_cache = cache_root / ("fedora-mock-" + _docker.docker.variant)
        mock_cache.mkdir(parents=True, exist_ok=True)
        dnf_cache = cache_root / ("fedora-dnf-" + _docker.docker.variant)
        dnf_cache.mkdir(parents=True, exist_ok=True)
        return [(mock_cache, "/var/cache/mock"), (dnf_cache, "/var/cache/dnf")]

    def build_builder_image(self):
        base = super().build_builder_image()
        command = ["yum", "install", "-y", "fedpkg", "python3dist(wheel)"] + \
            self.build_dependencies + self.dependencies + self.test_dependencies
        return _docker.lazy_run(base, command, tty=True, volumes=self._mounted_caches)

    def build_test_image(self):
        command = ["yum", "install", "-y"] + self.test_dependencies
        if self.project.gui:
            command.append("util-linux")
        return _docker.lazy_run(super().build_test_image(), command, tty=True,
                                volumes=self._mounted_caches)

    def build(self):
        mock_cache = cache_root / "fedora-mock"
        mock_cache.mkdir(parents=True, exist_ok=True)
        _docker.run(self.build_builder_image(),
                    ["fedpkg", "--release", "f37", "compile", "--", "-bb"],
                    tty=True, root=False,
                    volumes=[(self.distro_root, "/io")] + self._mounted_caches)
        rpms = {}
        machine = "noarch" if self.project.architecture == "none" else platform.machine()
        pattern = re.compile(
            fr"{re.escape(self.package_name)}(?:-([^-]+))?-{self.project.version}.*\.{machine}\.rpm")
        for path in (self.distro_root / machine).glob("*.fc37.*.rpm"):
            if m := pattern.match(path.name):
                rpms[m[1] or "main"] = path
        assert "main" in rpms
        return rpms

    def test(self, rpm):
        volumes = [(rpm.parent, "/pkg")] + self._mounted_caches
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        test_dependencies = []
        for package in self.project.test_dependencies["pip"]:
            test_dependencies.append(f"python3dist({package})")
        return _docker.run(self.build_test_image(), f"""
            dnf install -y /pkg/{rpm.name}
            {self.project.test_command}
        """, volumes=volumes, tty=True)


if __name__ == "__main__":
    self = Fedora(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
