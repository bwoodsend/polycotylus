import sys
import subprocess
import re
from textwrap import dedent
import json
import time
from pathlib import Path

import pytest

from polycotylus import _docker, _misc, _configuration


def test_container_removal():
    self = _docker.run("alpine")
    assert json.loads(
        subprocess.run([_docker.docker, "container", "inspect", self.id],
                       stdout=subprocess.PIPE).stdout)
    id = self.id
    del self
    assert not json.loads(
        subprocess.run([_docker.docker, "container", "inspect", id],
                       stdout=subprocess.PIPE).stdout)


def test_interactive(no_color):
    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert re.fullmatch(
        br'(\$ (docker|podman) run --rm --network=host --platform=\S+ -i (--ulimit nofile=1024:1048576 )?alpine\r?\n)?hello\n+', p.stdout)

    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", "echo foo && sh", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert re.search(b"foo\nhello\n+$", p.stdout)

    pattern = ".*command:\n" \
        r".*(docker|podman) run --rm --network=host --platform=\S+ -it? (--ulimit nofile=1024:1048576 )?alpine sh -ec 'cat .'\n" \
        ".*\n( Emulate Docker CLI using podman.*\n)?.*Is a directory"
    with pytest.raises(_docker.Error, match=pattern):
        _docker.run("alpine", "cat .", interactive=True)
    with pytest.raises(_docker.Error) as capture:
        _docker.run("alpine", "cat .\necho do not run me")
    assert "Is a directory" in capture.value.output
    assert "do not run me" not in capture.value.output


def test_non_interactive(monkeypatch, capsys):
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

    monkeypatch.setenv("POLYCOTYLUS_VERBOSITY", "0")
    with pytest.raises(_docker.Error, match="spaghetti.*not found"):
        _docker.run("alpine", ["spaghetti"])

    monkeypatch.setenv("POLYCOTYLUS_VERBOSITY", "2")
    capsys.readouterr()
    with pytest.raises(_docker.Error):
        _docker.run("alpine", ["spaghetti"])
    assert re.match(capsys.readouterr().err, "spaghetti.*not found")


docker_build_outputs = {
    "default": ("""
Step 27/28 : ENTRYPOINT ["/bin/intermediate"]
 ---> Using cache
 ---> b5d66ca3e222
Step 28/28 : CMD ["ash"]
 ---> Using cache
 ---> 2f119b7e8237
Successfully built 2f119b7e8237
""", "2f119b7e8237"),

    "buildx": ("""
#10 [test 5/8] RUN apk add py3-pytest
#10 CACHED

#11 [test 8/8] RUN chmod +x /bin/intermediate
#11 CACHED

#12 exporting to image
#12 exporting layers done
#12 writing image sha256:9314a15e8b1efbfe3c67426cd30d91fa1a36e072e904a401427b9a0ad9a161b8 done
#12 DONE 0.0s
""", "sha256:9314a15e8b1efbfe3c67426cd30d91fa1a36e072e904a401427b9a0ad9a161b8"),

    "new": ("""
=> exporting to image                                                                                                                                                                                                                   0.0s
 => => exporting layers                                                                                                                                                                                                                  0.0s
 => => writing image sha256:3ba522314faf4cca2a82cdc891e9f7945fd14d9ab5cc5ee7b3a6336551f37b15                                                                                                                                             0.0s
WARNING: failed to get git commit: fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'
""", "sha256:3ba522314faf4cca2a82cdc891e9f7945fd14d9ab5cc5ee7b3a6336551f37b15"),

    "podman": ("""
[2/2] STEP 9/10: ENTRYPOINT ["/bin/intermediate"]
--> Using cache 9b06c6add543248f1d1efe7666769f80b6522fc7e5d906277fc1b89699568884
--> 9b06c6add54
[2/2] STEP 10/10: CMD ["ash"]
--> Using cache d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93
--> d39228d6bbf
d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93
""", "d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93"),

    "containerd-snapshotter": ("""
#22 exporting to image
#22 exporting layers done
#22 exporting manifest sha256:8ff0d2f901ad92e8ee87ee460cd69b2afa1f35d3df74d2239965e39510f1ce4b done
#22 exporting config sha256:0b420318f6a1dc8eb26dd7d9a29c377805a8169b7e2dd9ac8f43bbe6ae8d5d2c done
#22 exporting attestation manifest sha256:b03ee1e6e462883a82ea1e7b0dc645e180b4eb6d2c5f2f7fd63695d9a5b3e79c done
#22 exporting manifest list sha256:af40dee35f527f685ed91a1c37b6080e66f6a361b3f07e4e8772d9165c56e79c done
#22 naming to moby-dangling@sha256:af40dee35f527f685ed91a1c37b6080e66f6a361b3f07e4e8772d9165c56e79c done
#22 unpacking to moby-dangling@sha256:af40dee35f527f685ed91a1c37b6080e66f6a361b3f07e4e8772d9165c56e79c done
#22 DONE 0.1s
""", "sha256:af40dee35f527f685ed91a1c37b6080e66f6a361b3f07e4e8772d9165c56e79c"),
}


def test_parse_build():
    for (name, (output, hash)) in docker_build_outputs.items():
        assert _docker._parse_build_output(output) == hash


def test_build(tmp_path):
    (tmp_path / "foo").write_text("hello")
    _misc.unix_write(tmp_path / "cake", "FROM alpine\nCOPY foo .\n")
    image = _docker.build("cake", tmp_path)
    assert _docker.run(image, ["cat", "/foo"]).output == "hello"

    (tmp_path / "cake").write_text("FROM alpine\nCOPY non-existent .\n")
    with pytest.raises(_docker.Error,
                       match="(docker|podman) build -f cake --network=host ."):
        _docker.build("cake", tmp_path)


def test_verbosity(monkeypatch, capsys, tmp_path, no_color):
    _misc.unix_write(tmp_path / "Dockerfile", "FROM alpine\nRUN touch /foo\n")
    run = lambda: _docker.run(_docker.build("Dockerfile", tmp_path), "seq 10")
    command_re = re.compile(r"^\$.+", re.M)
    output_re = re.compile(r"^[^\$]+", re.M)

    monkeypatch.setenv("POLYCOTYLUS_VERBOSITY", "0")
    run()
    assert capsys.readouterr().out == ""

    monkeypatch.setenv("POLYCOTYLUS_VERBOSITY", "1")
    run()
    out = capsys.readouterr().out
    assert len(command_re.findall(out)) == 2
    assert not output_re.findall(out)

    monkeypatch.setenv("POLYCOTYLUS_VERBOSITY", "2")
    run()
    out = capsys.readouterr().out
    assert len(command_re.findall(out)) == 2
    assert output_re.findall(out)

    monkeypatch.delenv("POLYCOTYLUS_VERBOSITY")
    run()
    out = capsys.readouterr().out
    assert output_re.findall(out)

    _docker.build("Dockerfile", tmp_path, verbosity=1)
    out = capsys.readouterr().out
    assert command_re.findall(out)
    assert not output_re.findall(out)


def test_lazy_run_timeout(monkeypatch):
    command = ["ash", "-c", "date +%s > /timestamp"]
    old = _docker.lazy_run("alpine", command)
    assert _docker.lazy_run("alpine", command.copy()) == old
    assert _docker.lazy_run("alpine", ["sh"] + command[1:]) != old
    assert _docker.lazy_run("alpine", command.copy()) == old

    next_week = time.time() + 3600 * 24 * 7
    monkeypatch.setattr(time, "time", lambda: next_week)
    assert _docker.lazy_run("alpine", command) != old


def test_too_old_podman(monkeypatch):
    fake_podman = Path(__file__).with_name("fake-podman.ps1")
    monkeypatch.setattr(_configuration, "read", lambda _: str(fake_podman))
    with pytest.raises(SystemExit, match="version of podman is unsupported"):
        docker = _docker.DockerInfo()
        docker.version
