import shlex
import collections
from fnmatch import fnmatch
from pathlib import Path
import io

from PIL import Image
import pytest

from polycotylus import _docker, _exceptions
from polycotylus._mirror import RequestHandler
from polycotylus._project import Project

dumb_text_viewer = Path(__file__, "../../examples/dumb_text_viewer").resolve()
ubrotli = dumb_text_viewer.with_name("ubrotli")
bare_minimum = dumb_text_viewer.with_name("bare-minimum")
kitchen_sink = Path(__file__, "../mock-packages/kitchen-sink").resolve()
fussy_arch = kitchen_sink.with_name("fussy_arch")
poetry_based = kitchen_sink.with_name("poetry-based")

gpg_home = Path(__file__).with_name("gpg-home").resolve()

awkward_pypi_packages = [
    "zope.event",  # Contains a '.'
    "ruamel.yaml",
    "jaraco.classes",
    "prompt_toolkit",  # Contains a '_'
    "nest_asyncio",
    "setuptools_scm",
    "Pygments",  # Contains uppercase letters
    "cython",  # Ignores the standard Python package prefix on all distributions
    "urllib3",  # Contains a number
    "python-dateutil",  # Already has py/python prefix.
    "PyQt5",
    "pyyaml",
]


def _group_python_extras(dependencies):
    extras = ["tkinter", "sqlite3", "decimal", "lzma", "zlib", "readline",
              "bz2", "curses", "ctypes", "ssl", "hashlib", "venv", "uuid",
              "curses.panel", "dbm.gnu", "dbm.ndbm", "binascii"]
    grouped = collections.defaultdict(list)
    for extra in extras:
        # ~ yield dependencies.get(extra, ()), (extra,)
        grouped[tuple(dependencies.get(extra, ()))].append(extra)
    return grouped.items()


class Base:
    cls: type

    def test_available_packages(self):
        packages = self.cls.available_packages()
        assert len(packages) > 1000
        for package in packages:
            assert " " not in package

    def test_python_package(self):
        for pypi_name in awkward_pypi_packages:
            assert self.cls.python_package(pypi_name) in self.cls.available_packages()

        with pytest.raises(_exceptions.PackageUnavailableError):
            self.cls.python_package("i-am-a-unicorn")

    package_install: str

    def test_python_extras(self, monkeypatch):
        requests = []
        original_do_GET = RequestHandler.do_GET
        monkeypatch.setattr(RequestHandler, "do_GET",
                            lambda self: requests.append(self.path) or original_do_GET(self))
        for (packages, imports) in _group_python_extras(self.cls.python_extras):
            mirror = self.cls.mirror
            script = self.cls._formatter(f"""
                {mirror.install_command}
                {self.package_install} python3 {shlex.join(packages)}
                python3 -c 'import {", ".join(imports)}'
            """)
            with mirror:
                _docker.run(self.cls.base_image, script,
                            architecture=self.cls.preferred_architecture)
            assert requests, "Mirror is being ignored"


def qemu(cls):
    packages = {}

    @pytest.mark.parametrize("architecture", cls.supported_architectures, ids=str)
    def test_multiarch(architecture):
        self = cls(Project.from_root(ubrotli), architecture)
        self.generate()
        package = self.build()["main"]
        packages[architecture] = package
        for (_architecture, _package) in packages.items():
            assert _package.is_file()
        container = self.test(package)
        with container[self.python_prefix] as tar:
            files = tar.getnames()
        binaries = [i for i in files if fnmatch(i, "**/ubrotli*.so*")]
        assert len(binaries) == 1
        binary, = binaries

        if architecture == "armv7":
            assert "arm" in binary
        elif architecture.startswith("ppc"):
            assert architecture.replace("ppc", "powerpc") in binary
        elif architecture == "x86":
            "i386" in binary
        else:
            architecture in binary

    return test_multiarch


def check_dumb_text_viewer_installation(container, shebang=b"#!/usr/bin/python",
                                        icon_sizes=(16, 24, 128)):
    for size in icon_sizes:
        raw = container.file(f"/usr/share/icons/hicolor/{size}x{size}/apps/underwhelming_software-dumb_text_viewer.png")
        png = Image.open(io.BytesIO(raw)).convert("RGBA")
        assert png.size == (size, size)
        assert png.getpixel((0, 0))[3] == 0
        container.file(f"/usr/share/icons/hicolor/{size}x{size}/apps/underwhelming_software-dumb_text_viewer-pink-mode.png")

    assert "Comment[zh_CN]=讀取純文本文件".encode() in container.file(
        "/usr/share/applications/underwhelming_software-dumb_text_viewer.desktop")
    assert container.file(
        "/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg"
    ).startswith(b"<svg")
    assert b'fill="#fe55fe"' in container.file(
        "/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer-pink-mode.svg")
    assert container.file("/usr/bin/dumb_text_viewer").startswith(shebang)
