"""
https://www.debian.org/doc/manuals/debmake-doc/index.en.html
https://www.debian.org/doc/manuals/maint-guide/
https://wiki.debian.org/Python/LibraryStyleGuide
"""

import shlex
import re
import textwrap
from functools import lru_cache
import tarfile
import io
import contextlib
import shutil

from polycotylus import _misc, _docker, machine, _mirror
from polycotylus._base import BaseDistribution


class ControlFile:
    """
    https://www.debian.org/doc/debian-policy/ch-controlfields#syntax-of-control-files
    """

    def __init__(self):
        self._paragraphs = []

    def add_paragraph(self, **fields):
        self._paragraphs.append(fields)

    def __str__(self):
        out = []
        for paragraph in self._paragraphs:
            for (key, value) in paragraph.items():
                key = key.replace("_", "-")
                if "\n" in value:
                    value = textwrap.dedent(value)
                    first, *lines = value.strip("\n").split("\n")
                    out.append(f"{key}: {first}")
                    for line in lines:
                        out.append(" " * (len(key) + 2) + line)
                else:
                    out.append(key + ": " + value)
            out.append("")
        return "\n".join(out)


class Debian(BaseDistribution):
    python_prefix = "/usr"
    python_extras = {
        "tkinter": ["python3-tk"],
        "sqlite3": ["libsqlite3-0"],
        "decimal": ["libmpdec3"],
        "lzma": ["liblzma5"],
        "zlib": ["zlib1g"],
        "readline": ["libreadline8"],
        "bz2": ["libbz2-1.0"],
    }
    image = "debian:trixie-slim"
    supported_architectures = {
        "amd64": "x86_64",
        "arm64": "aarch64",
        "armel": "arm/v5",
        "armhf": "arm/v7",
        "i386": "i386",
        "mips64el": "mips64le",
        "ppc64el": "ppc64le",
        "riscv64": "riscv64",
        "s390x": "s390x",
    }
    _formatter = _misc.Formatter("\t")
    _packages = {
        "python": "python3:any",
        "imagemagick": "imagemagick",
        "imagemagick_svg": "librsvg2-bin",
        "xvfb-run": "xvfb xauth",
        "font": "fonts-dejavu",
    }
    tag = "13"
    mirror = _mirror.mirrors["debian13"]

    def __init__(self, package, architecture=None):
        if architecture is None:
            architecture = machine()
            architecture = {"x86_64": "amd64", "aarch64": "arm64"}.get(architecture, architecture)
        super().__init__(package, architecture)
        if self.project.architecture == "none":
            self.architecture = "all"

    @classmethod
    @lru_cache()
    def _package_manager_queries(cls):
        with cls.mirror:
            container = _docker.run(cls.image, f"""
                {cls.mirror.install}
                apt-get update
                apt list -qq > /available
                apt list --installed -qq > /installed
                echo n | apt-get install build-essential > /build-essential || true
            """, tty=True)
        _read = lambda path: container.file(path).decode()
        cls._available_packages = set(re.findall("^([^/\n]+)/", _read("/available"), flags=re.M))
        preinstalled = set(re.findall("^([^/\n]+)/", _read("/installed"), flags=re.M))
        build_essential = {j for i in re.findall(r"  .*", _read("/build-essential")) for j in i.split()}
        cls._build_base_packages = preinstalled.union(build_essential)
        cls._python_version = re.search("\npython3/.* (\d+\.\d+\.\d+)-", _read("/available"))[1]

    @classmethod
    def build_base_packages(self):
        return {"build-essential", "libc-dev", "gcc", "g++", "make", "dpkg-dev"}

    @staticmethod
    def fix_package_name(name):
        return name.replace("_", "-").lower()

    invalid_package_characters = "[]"

    @classmethod
    def python_package_convention(self, pypi_name):
        return "python3-" + pypi_name

    @property
    def source_name(self):
        return f"{re.sub('[._-]+', '-', self.project.name.lower())}_{self.project.version}"

    def inject_source(self):
        self.distro_root.mkdir(exist_ok=True, parents=True)
        with open(self.distro_root / (self.source_name + ".orig.tar.gz"), "wb") as f:
            f.write(self.project.tar())
        with tarfile.open("", "r", io.BytesIO(self.project.tar(""))) as tar:
            tar.extractall(self.distro_root / "build")

    def dockerfile(self):
        return self._formatter(f"""
            FROM {self.image} AS build
            RUN {self.mirror.install}
            ENV LANG=C.UTF-8 LC_ALL=C LANGUAGE=C

            RUN apt-get update && apt-get install -y --no-install-recommends sudo
            RUN groupadd wheel
            {self._install_user()}

            ENV DEBEMAIL="{self.project.email}" DEBFULLNAME="{self.project.maintainer}"
            RUN apt-get update && apt-get install -y --no-install-recommends build-essential dh-python python3-all dh-make debmake devscripts fish python3-all-dev:any pybuild-plugin-pyproject {shlex.join(re.split("[<>=@]", i)[0] for i in self.build_dependencies + self.dependencies + self.test_dependencies)}

            RUN mkdir -p /io/build && chown -R user /io
            WORKDIR /io/build
        """)

    def control(self):
        writer = ControlFile()
        writer.add_paragraph(
            Source=re.sub("[._-]+", "-", self.project.name.lower()),
            Section="python",
            Priority="optional",
            Maintainer=self.project.maintainer_slug,
            Build_Depends=",\n".join(["debhelper-compat (= 13)", "dh-python", "python3-all"] + [re.split("[<>=@]", i)[0] for i in self.build_dependencies]),
            Standards_Version="4.6.2",
            Homepage=self.project.url,
            Rules_Requires_Root="no",
        )
        writer.add_paragraph(
            Package=self.package_name,
            Architecture={"any": "any", "none": "all"}.get(self.project.architecture) or " ".join(self.project.architecture),
            **(dict(Multi_Arch="foreign") if self.project.architecture != "noarch" else {}),
            Depends=",\n".join(["${misc:Depends}", "${shlibs:Depends}"] + [re.split("[<>=@]", i)[0] for i in self.dependencies]),
            Description=self.project.description,
        )
        return str(writer)

    def copywrite(self):
        writer = ControlFile()
        writer.add_paragraph(
            Format="https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/",
            Upstream_Name=self.package_name,
            Upstream_Contact=self.project.maintainer_slug,
            Source=self.project.url,
        )
        return str(writer)

    def test_control(self):
        writer = ControlFile()
        writer.add_paragraph(
            Test_Command=f"""
                set -e
                cp -r {shlex.join(str(i) for i in self.project.test_files)} "$AUTOPKGTEST_TMP"
                for py in $(py3versions -r 2>/dev/null)
                do cd "$AUTOPKGTEST_TMP"
                $py -m pytest
                done
            """,
            Depends=", ".join(self.test_dependencies),
        )
        return str(writer)

    def generate(self):
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root / "build")
        super().generate()
        debian_root = self.distro_root / "build" / "debian"
        debian_root.mkdir(exist_ok=True, parents=True)
        (debian_root / "control").write_text(self.control())
        (debian_root / "tests").mkdir(exist_ok=True)
        (debian_root / "tests" / "control").write_text(self.test_control())
        _misc.unix_write(debian_root / "changelog", f"""\
{re.sub("[._-]+", "-", self.project.name.lower())} ({self.project.version}-1) unstable; urgency=low

  * Initial release (Closes: #0)

 -- {self.project.maintainer_slug}  {english_date()}
""")
        rules = self._formatter("""
            #! /usr/bin/make -f
            include /usr/share/dpkg/pkg-info.mk
            export PYBUILD_NAME=ubrotli
            export PYBUILD_SYSTEM=pyproject

            %:
                dh $@ --with python3 --buildsystem=pybuild

            override_dh_auto_test:
                debian/tests/test
        """)
        if self.project.desktop_entry_points or self.icons:
            rules += self._formatter("""
                override_dh_auto_install:
                    dh_auto_install
            """)
            sysroot = f"debian/{self.package_name}"
            for line in self.install_icons(1, sysroot).splitlines():
                line = line.replace("$", "$$")
                line = line.replace("-size $$_size", "-resize $$_size")
                if line[1] == "\t":
                    rules += line + "; \\\n"
                elif line.startswith("\tfor"):
                    rules += line + " \\\n"
                else:
                    rules += line + "\n"
            rules += self.install_desktop_files(1, sysroot)
        _misc.unix_write(debian_root / "rules", rules)
        (debian_root / "rules").chmod(0o700)

        test_script = debian_root / "tests/test"
        test_script.parent.mkdir(parents=True, exist_ok=True)
        _misc.unix_write(test_script, self._formatter("""
            #!/usr/bin/env sh
            set -e
            export PYTHONPATH=".pybuild/cpython3_$(python3 -c 'import sys; print("{0}.{1}".format(*sys.version_info))')_ubrotli/build/"
        """) + re.sub(r"\bpython\b", "python3", self.project.test_command))
        test_script.chmod(0o700)
        _misc.unix_write(debian_root / "watch", self._formatter("""
            version=3
            opts=uversionmangle=s/(rc|a|b|c)/~$1/ \\
            https://pypi.debian.net/ubrotli/ubrotli-(.+)\.(?:zip|tgz|tbz|txz|(?:tar\.(?:gz|bz2|xz)))
        """))
        (debian_root / "upstream").mkdir(exist_ok=True)
        _misc.unix_write(debian_root / "upstream" / "metadata", self._formatter("""
            Bug-Database: https://github.com/ultrajson/ultrajson/issues
            Bug-Submit: https://github.com/ultrajson/ultrajson/issues/new
            Repository: https://github.com/ultrajson/ultrajson.git
            Repository-Browse: https://github.com/ultrajson/ultrajson
        """))
        (debian_root / "source").mkdir(exist_ok=True)
        _misc.unix_write(debian_root / "source" / "format", "3.0 (quilt)\n")

    def build(self):
        with self.mirror:
            _docker.run(self.build_builder_image(), ["debuild", "-i", "-us", "-uc"],
                        volumes=[(self.distro_root, "/io")], tty=True, root=False, post_mortem=True, architecture=self.docker_architecture)
        path = self.distro_root / f"{self.package_name}_{self.project.version}-1_{self.architecture}.deb"
        assert path.exists(), path
        debug = path.with_name(f"{self.package_name}-dbgsym_{self.project.version}-1_{self.architecture}.deb")
        packages = {"main": path}
        if debug.exists():
            packages["dbgsym"] = debug
        return packages

    def test(self, package):
        test_command = re.sub(r"\bpython\b", "python3", self.project.test_command)
        with self.mirror:
            return _docker.run(self.build_builder_image(), f"""
                sudo apt-get update
                sudo apt-get install -y '/io/{package.name}'
                {test_command}
            """, volumes=[(self.distro_root, "/io")], tty=True, root=False,
            post_mortem=True, architecture=self.docker_architecture)


Debian13 = Debian


def english_date():
    from datetime import datetime
    date = datetime.now().astimezone()
    month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][date.month - 1]
    day = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][date.weekday()]
    return date.strftime(f"{day}, %d {month} %Y %H:%M:%S %z")
