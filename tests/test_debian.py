import json
import contextlib
import re

import polycotylus
from polycotylus._project import Project
import shared


class TestCommon(shared.Base):
    cls = polycotylus.Debian
    package_install = "apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends"


def test_dumb_text_viewer():
    self = polycotylus.Debian(Project.from_root(shared.dumb_text_viewer))
    self.generate()
    packages = self.build()
    assert sorted(packages) == ["main"]
    container = self.test(packages["main"])
    self.update_artifacts_json(packages)
    shared.check_dumb_text_viewer_installation(container)


def test_ubrotli():
    with contextlib.suppress(FileNotFoundError):
        (shared.ubrotli / ".polycotylus/artifacts.json").unlink()

    for (architecture, Debian) in [("amd64", polycotylus.Debian13), ("i386", polycotylus.Debian14)]:
        self = Debian(Project.from_root(shared.ubrotli), architecture=architecture)
        self.generate()
        packages = self.build()
        assert sorted(packages) == ["dbgsym", "main"]
        container = self.test(packages["main"])
        with container["/usr/lib/python3/dist-packages"] as tar:
            # Test that only one architecture .so is present.
            binaries = [i for i in tar.getnames() if re.search("ubrotli.*.so", i)]
            # At times, Debian builds for multiple Python versions.
            without_abi = {re.sub(r"cpython-(\d+)-", "", i) for i in binaries}
            assert len(without_abi) == 1
        self.update_artifacts_json(packages)

    assert json.loads((shared.ubrotli / ".polycotylus/artifacts.json").read_bytes()) == [
        {
            "distribution": "debian",
            "tag": "13",
            "architecture": "amd64",
            "package_type": "dbgsym",
            "path": ".polycotylus/debian/13/python3-ubrotli-dbgsym_0.1.0-1_amd64.deb",
            "signature_path": None,
        },
        {
            "distribution": "debian",
            "tag": "13",
            "architecture": "amd64",
            "package_type": "main",
            "path": ".polycotylus/debian/13/python3-ubrotli_0.1.0-1_amd64.deb",
            "signature_path": None,
        },
        {
            "distribution": "debian",
            "tag": "14",
            "architecture": "i386",
            "package_type": "dbgsym",
            "path": ".polycotylus/debian/14/python3-ubrotli-dbgsym_0.1.0-1_i386.deb",
            "signature_path": None,
        },
        {
            "distribution": "debian",
            "tag": "14",
            "architecture": "i386",
            "package_type": "main",
            "path": ".polycotylus/debian/14/python3-ubrotli_0.1.0-1_i386.deb",
            "signature_path": None,
        }
    ]


def test_kitchen_sink(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "1.2.3.4")
    self = polycotylus.Debian(polycotylus.Project.from_root(shared.kitchen_sink))
    self.generate()
    packages = self.build()
    self.test(packages["main"])


def test_poetry():
    self = polycotylus.Debian(polycotylus.Project.from_root(shared.poetry_based))
    self.generate()
    packages = self.build()
    self.test(packages["main"])


def test_hatchling(monkeypatch):
    monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "10.20")
    self = polycotylus.Debian(Project.from_root(shared.hatchling_based))
    self.generate()
    packages = self.build()
    self.test(packages["main"])
