import sys
import subprocess
import re
from textwrap import dedent
import json
import os

import pytest

from polycotylus import _docker


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


def test_interactive():
    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert re.fullmatch(
        br'(\$ (docker|podman) run --rm --network=host -i alpine\n)?hello\n+', p.stdout)

    code = dedent("""
        from polycotylus import _docker
        _docker.run("alpine", "echo foo && sh", interactive=True)
    """)
    p = subprocess.run([sys.executable, "-c", code], input=b"echo hello",
                       timeout=10, stdout=subprocess.PIPE)
    assert p.returncode == 0
    assert re.search(b"foo\nhello\n+$", p.stdout)

    pattern = ".*command:\n" \
        ".*(docker|podman) run --rm --network=host -it? alpine sh -ec 'cat .'\n" \
        ".*\n( Emulate Docker CLI using podman.*\n)?.*Is a directory"
    with pytest.raises(_docker.Error, match=pattern):
        _docker.run("alpine", "cat .", interactive=True)
    with pytest.raises(_docker.Error) as capture:
        _docker.run("alpine", "cat .\necho do not run me")
    assert "Is a directory" in capture.value.output
    assert "do not run me" not in capture.value.output


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

    "podman": ("""
[2/2] STEP 9/10: ENTRYPOINT ["/bin/intermediate"]
--> Using cache 9b06c6add543248f1d1efe7666769f80b6522fc7e5d906277fc1b89699568884
--> 9b06c6add54
[2/2] STEP 10/10: CMD ["ash"]
--> Using cache d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93
--> d39228d6bbf
d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93
""", "d39228d6bbf39d98ce875c9143aaa88a400ededa02ca8947aabe2ac49a197f93"),
}


def test_parse_build():
    for (name, (output, hash)) in docker_build_outputs.items():
        assert _docker._parse_build_output(output) == hash


def test_build(tmp_path):
    (tmp_path / "foo").write_text("hello")
    (tmp_path / "cake").write_text("FROM alpine\nCOPY foo .\n")
    image = _docker.build("cake", tmp_path)
    assert _docker.run(image, ["cat", "/foo"]).output == "hello"

    (tmp_path / "cake").write_text("FROM alpine\nCOPY non-existent .\n")
    with pytest.raises(_docker.Error,
                       match="(docker|podman) build -f cake --network=host ."):
        _docker.build("cake", tmp_path)


def test_mount_permissions(tmp_path):
    secret_file = tmp_path / "secrets"
    secret_file.write_text("some credentials")
    secret_file.chmod(0o600)
    assert _docker.run("alpine", """
        cat /io/secrets
        echo some more secrets >> /io/secrets
    """, root=False, volumes=[(tmp_path, "/io")]).output == "some credentials"
    assert "more" in secret_file.read_text()
    assert secret_file.stat().st_mode & 0o777 == 0o600
    assert secret_file.stat().st_uid == os.getuid()


def test_verbosity(monkeypatch, capsys, tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM alpine\nRUN touch /foo\n")
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
    assert capsys.readouterr().out == ""

    _docker.build("Dockerfile", tmp_path, verbosity=1)
    out = capsys.readouterr().out
    assert command_re.findall(out)
    assert not output_re.findall(out)
