"""
https://www.debian.org/doc/manuals/debmake-doc/index.en.html
https://www.debian.org/doc/manuals/maint-guide/
https://wiki.debian.org/Python/LibraryStyleGuide
"""

import shlex
import re
import textwrap
from functools import lru_cache

from polycotylus import _misc, _docker
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
                        out.append(" ; " + line)
                else:
                    out.append(key + ": " + value)
            out.append("")
        return "\n".join(out)


class Debian(BaseDistribution):
    python = "python3"
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
    image = "debian:unstable"
    supported_architectures = {
        "aarch64": "aarch64",
        "armv7": "arm",
        "ppc64le": "ppc64le",
        "s390x": "s390x",
        "x86": "i386",
        "x86_64": "x86_64",
    }
    _formatter = _misc.Formatter("\t")
    pkgdir = "$builddir"
    imagemagick = "imagemagick"
    imagemagick_svg = "librsvg2-2"
    xvfb_run = "xvfb"
    font = "fonts-dejavu"

    @classmethod
    @lru_cache()
    def available_packages(cls):
        with cls.mirror:
            output = _docker.run(cls.image, f"""
                {cls.mirror.install}
                apt-get update -qq
                apt list -qq
            """, verbosity=0).output
        return set(re.findall(r"^([^\n/]+)/", output, re.M))

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
        return f"{self.package_name}-{self.project.version}"

    def inject_source(self):
        self.distro_root.mkdir(exist_ok=True, parents=True)
        with open(self.distro_root / (self.source_name + ".tar.gz"), "wb") as f:
            f.write(self.project.tar())

    def dockerfile(self):
        return self._formatter(f"""
            FROM {self.image} AS build
            RUN {self.mirror.install}
            ENV LANG=C.UTF-8 LC_ALL=C LANGUAGE=C

            RUN apt-get update && apt-get install -y --no-install-recommends sudo
            RUN groupadd wheel
            {self._install_user()}

            ENV DEBEMAIL="{self.project.email}" DEBFULLNAME="{self.project.maintainer}"
            RUN apt-get update && apt-get install -y --no-install-recommends build-essential dh-python python3-all dh-make debmake devscripts fish {shlex.join(re.split("[<>=@]", i)[0] for i in self.build_dependencies + self.dependencies + self.test_dependencies)}

            RUN mkdir /io
            WORKDIR /io
        """)

    def control(self):
        writer = ControlFile()
        writer.add_paragraph(
            Source=self.package_name,
            Section="python",
            Priority="optional",
            Maintainer=self.project.maintainer_slug,
            Build_Depends=", ".join(["debhelper (>= 11~)", "dh-python", "python3-all"] + [re.split("[<>=@]", i)[0] for i in self.build_dependencies]),
            X_Python3_Version=self.project.supported_python,
            Standards_Version="4.5.1",
            Homepage=self.project.url,
            Rules_Requires_Root="no",
        )
        writer.add_paragraph(
            Package=self.package_name,
            Architecture={"any": "any", "noarch": "all"}.get(self.project.architecture) or " ".join(self.project.architectures),
            **(dict(Multi_Arch="foreign") if self.project.architecture != "noarch" else {}),
            Depends=", ".join(re.split("[<>=@]", i)[0] for i in self.dependencies),
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
        super().generate()
        debian_root = self.distro_root / self.source_name / "debian"
        debian_root.mkdir(exist_ok=True, parents=True)
        (debian_root / "control").write_text(self.control())
        (debian_root / "tests").mkdir(exist_ok=True)
        (debian_root / "tests" / "control").write_text(self.test_control())

    def build(self):
        with self.mirror:
            _docker.run(self.build_builder_image(), ["fish"], volumes=[(self.distro_root, "/io")], interactive=True, tty=True, root=False)

    def test(self, package):
        pass
