from subprocess import run as _run, PIPE, DEVNULL, STDOUT, Popen
import re
import os
import io
import shlex
import textwrap
from tarfile import TarFile
from pathlib import Path
import json
import time
import sys


class DockerInfo(str):
    @staticmethod
    def __new__(cls):
        self = super().__new__(cls, os.environ.get("docker", "docker"))
        p = _run([self, "--version"], stdout=PIPE, stderr=STDOUT, text=True)
        m = re.match("(docker|podman) version ([^, ]+)", p.stdout.lower())
        self.variant, self.version = m.groups()
        return self


docker = DockerInfo()


class run:
    def __init__(self, base, command=None, *flags, volumes=(), check=True,
                 interactive=False, tty=False, root=True, verbosity=None):
        tty = tty and sys.stdin.isatty()
        if verbosity is None:
            verbosity = _verbosity()
        __tracebackhide__ = True
        arguments = ["--network=host"]
        for (source, dest) in volumes:
            arguments.append(f"-v{Path(source).resolve()}:{dest}:z")
        if interactive:
            arguments.append("-it" if tty else "-i")
        elif tty:
            arguments.append("-t")
        arguments.extend(map(str, flags))
        if not root:
            if docker.variant == "podman":
                arguments += ["--userns", "keep-id"]
            else:
                arguments += [f"--user={os.getuid()}"]

        arguments.append(base)
        if isinstance(command, str):
            arguments += ["sh", "-ec", textwrap.dedent(command)]
        elif command is not None:
            arguments += command
        human_friendly = f"$ {docker} run --rm " + shlex.join(arguments)
        if verbosity >= 1:
            print(human_friendly, flush=True)

        p = _run([docker, "create"] + arguments, stdout=PIPE)
        self.id = p.stdout.decode().splitlines()[-1]
        if interactive:
            if _run([docker, "start", "-ia", self.id]).returncode:
                logs = _run([docker, "logs", self.id], stderr=STDOUT,
                            stdout=PIPE, text=True).stdout
                raise Error(human_friendly, logs)

        else:
            p = _run([docker, "container", "start", "-a", self.id],
                     stdout=None if verbosity >= 2 else DEVNULL,
                     stderr=STDOUT if verbosity >= 2 else DEVNULL)
            self.returncode = p.returncode
            if check and self.returncode:
                raise Error(human_friendly, self.output)

    @property
    def output(self):
        return _run([docker, "logs", self.id],
                    stdout=PIPE, stderr=STDOUT).stdout.decode()

    def __del__(self):
        try:
            _run([docker, "container", "rm", "-f", self.id], stdout=DEVNULL)
        except (AttributeError, ImportError, TypeError):  # pragma: no cover
            pass

    def __getitem__(self, path):
        path = Path("/", path)
        p = _run([docker, "container", "cp", f"{self.id}:{path}", "-"],
                 stdout=PIPE)
        return TarFile("", "r", io.BytesIO(p.stdout))

    def file(self, path):
        with self[path] as tar:
            with tar.extractfile(Path(path).name) as f:
                return f.read()

    def commit(self):
        return _run([docker, "commit", self.id], stdout=PIPE,
                    text=True).stdout.strip()


def _tee_run(command, verbosity, **kwargs):
    with Popen(command, stderr=STDOUT, stdout=PIPE, **kwargs) as p:
        chunks = []
        while (chunk := p.stdout.readline()) or p.poll() is None:
            chunks.append(chunk)
            if verbosity >= 2:
                sys.stdout.buffer.write(chunk)
        if verbosity >= 2:
            print()
    return p.returncode, b"".join(chunks).decode()


def build(dockerfile, root, target=None, verbosity=None):
    command = [docker, "build", "-f", str(dockerfile), "--network=host", "."]
    if verbosity is None:
        verbosity = _verbosity()
    if target:
        command += ["--target", target]
    if verbosity >= 1:
        print("$", shlex.join(command))
    returncode, output = _tee_run(command, verbosity, cwd=root)
    if returncode:
        raise Error("$ " + shlex.join(command), output)
    return _parse_build_output(output)


def _parse_build_output(output):
    match = re.search(r"Successfully built ([a-f0-9]{8,})\n*\Z", output) \
        or re.search(r"([a-f0-9]{64})\n*\Z", output) \
        or re.search(r"writing image (sha256:[a-f0-9]{64}) done\n.* DONE .*\n*\Z", output)
    return match[1]


def lazy_run(base, command, **kwargs):
    assert isinstance(command, list)
    base_info = json.loads(_run([docker, "image", "inspect", base], stdout=PIPE).stdout)
    base = base_info[0]["Id"]
    _images = _run([docker, "images", "-q"], stdout=PIPE).stdout.decode().split()
    images = json.loads(_run([docker, "image", "inspect"] + _images, stdout=PIPE).stdout)
    for image in images:
        _time = time.strptime(image["Created"].split(".")[0].rstrip("Z"),
                              "%Y-%m-%dT%H:%M:%S")
        if image["Parent"].startswith((base, "sha256:" + base)):
            if (image.get("ContainerConfig") or image["Config"])["Cmd"] == command:
                if time.time() - time.mktime(_time) < 3600 * 24 * 3:
                    return image["Id"]
    container = run(base, command, **kwargs)
    return container.commit()


def _verbosity():
    return int(os.environ.get("POLYCOTYLUS_VERBOSITY", 0))


class Error(Exception):
    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return f"Docker command:\n    {self.command}\n" \
            "returned an error:\n" + self.output
