import re
import shlex

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._fedora import Fedora
from polycotylus.__main__ import cli
from tests import dumb_text_viewer, cross_distribution, ubrotli, silly_name


def test_pretty_spec():
    self = Fedora(Project.from_root(dumb_text_viewer))
    spec = self.spec()

    first, *others = re.finditer(r"^(\w+:( *))(.*)$", spec, flags=re.M)
    assert len(first[2]) >= 2
    for line in others:
        assert len(line[1]) == len(first[1])
        assert len(line[2]) >= 2

    assert "\n\n\n\n" not in spec


def test_python_extras():
    for (packages, imports) in cross_distribution._group_python_extras(Fedora.python_extras):
        _docker.run("fedora:37", f"""
            {Fedora.dnf_config_install}
            yum install -y {shlex.join(packages)} python3
            python3 -c 'import {", ".join(imports)}'
        """, volumes=Fedora._mounted_caches.fget(None))


def test_ubrotli():
    self = Fedora(Project.from_root(ubrotli))
    self.generate()
    self.test(self.build()["main"])


def test_dumb_text_viewer():
    self = Fedora(Project.from_root(dumb_text_viewer))
    self.generate()
    container = self.test(self.build()["main"])
    assert container.file("/usr/bin/dumb_text_viewer").startswith(b"#! /usr/bin/python3")
    container.file("/usr/share/applications/underwhelming_software-dumb_text_viewer.desktop")
    container.file("/usr/share/icons/hicolor/24x24/apps/underwhelming_software-dumb_text_viewer.png")
    container.file("/usr/share/icons/hicolor/scalable/apps/underwhelming_software-dumb_text_viewer.svg")


def test_silly_named_package():
    self = Fedora(Project.from_root(silly_name))
    self.generate()
    assert "certifi" not in self.spec()
    assert "setuptools" not in self.spec()
    assert "colorama" not in self.spec()
    self.test(self.build()["main"])


def test_cli(monkeypatch, capsys):
    monkeypatch.chdir(dumb_text_viewer)
    cli(["fedora"])
    capture = capsys.readouterr()
    assert "Built 1 artifact:\n" in capture.out

    monkeypatch.chdir(ubrotli)
    cli(["fedora"])
    capture = capsys.readouterr()
    assert "Built 3 artifacts:\n" in capture.out
