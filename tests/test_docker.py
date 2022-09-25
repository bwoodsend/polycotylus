import sys
import subprocess
from textwrap import dedent
import json

import pytest

from polycotylus import _docker


def test_container_removal():
    self = _docker.run("alpine")
    assert json.loads(
        subprocess.run(["docker", "container", "inspect", self.id],
                       stdout=subprocess.PIPE).stdout)
    id = self.id
    del self
    assert not json.loads(
        subprocess.run(["docker", "container", "inspect", id],
                       stdout=subprocess.PIPE).stdout)


def test_interactive():
    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert p.stdout == b'$ docker run --rm --network=host -i alpine\nhello\n'

    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", "sleep 0.1 && echo foo && sh", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert p.stdout.endswith(b"foo\nhello\n")

    pattern = ".*command:\n" \
        ".*docker run --rm --network=host -it? alpine sh -c 'cat .'\n" \
        ".*\n.*Is a directory"
    with pytest.raises(_docker.Error, match=pattern):
        _docker.run("alpine", "cat .", interactive=True)


def test_non_interactive():
    self = _docker.run("alpine", "echo 'hello\nworld\n' > /etc/foo")

    with self["/etc"] as tar:
        assert "etc/foo" in tar.getnames()
        with tar.extractfile("etc/foo") as f:
            assert b"hello\nworld\n" in f.read()

        assert "etc/os-release" in tar.getnames()
        with tar.extractfile("etc/os-release") as f:
            assert b"Alpine" in f.read()

    with pytest.raises(_docker.Error, match="File exists"):
        _docker.run("alpine", ["mkdir", "/etc"])


def test_build(tmp_path):
    (tmp_path / "foo").write_text("hello")
    (tmp_path / "cake").write_text("FROM alpine\nCOPY foo .\n")
    image = _docker.build("cake", tmp_path)
    assert _docker.run(image, ["cat", "/foo"]).output == "hello"

    (tmp_path / "cake").write_text("FROM alpine\nCOPY non-existent .\n")
    with pytest.raises(_docker.Error,
                       match="docker build -f cake --network=host ."):
        _docker.build("cake", tmp_path)
