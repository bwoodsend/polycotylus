from subprocess import run as _run, PIPE, DEVNULL, STDOUT, Popen
import re
import os
import io
import shlex
import textwrap
from tarfile import TarFile
from pathlib import Path
import platform
import json
import time
import sys
import contextlib
from functools import lru_cache

import termcolor
import platformdirs

from polycotylus import machine, _configuration

cache_root = Path(platformdirs.user_cache_dir("polycotylus"))
cache_root.mkdir(parents=True, exist_ok=True)


class DockerInfo(str):
    @staticmethod
    def __new__(cls):
        return super().__new__(cls, (_configuration.read("docker") or "docker").strip())

    @lru_cache()
    def _info(self):
        p = _run([self, "--version"], stdout=PIPE, stderr=STDOUT, text=True)
        m = re.match("(docker|podman) version ([^, ]+)", p.stdout.lower())
        variant, version = m.groups()
        if variant == "podman":
            if tuple(map(int, re.findall(r"\d+", version))) < (4, 3, 1):
                # Note that there may be versions after 3.4.4 which also work.
                # If ``podman run echo -n hello > /dev/null && podman logs -l``
                # prints hello, this version is usable.
                raise SystemExit("This version of podman is unsupported. "
                                 "At least 4.3.1 is needed")
        return variant, version

    @property
    def variant(self):
        return self._info()[0]

    @property
    def version(self):
        return self._info()[1]


docker = DockerInfo()
post_mortem = False


def images_cache():
    cache = cache_root / docker.variant
    cache.mkdir(exist_ok=True)
    return cache


class run:
    def __init__(self, base, command=None, *flags, volumes=(), check=True,
                 interactive=False, tty=False, root=True, post_mortem=False,
                 architecture=machine(), verbosity=None):
        tty = tty and sys.stdin.isatty()
        if interactive:
            verbosity = 2
        if verbosity is None:
            verbosity = _verbosity()
        __tracebackhide__ = True
        arguments = ["--network=host", "--platform=linux/" + architecture]
        for (source, dest) in volumes:
            arguments.append(f"-v{Path(source).resolve()}:{dest}:z")
        if interactive or command:
            arguments.append("-it" if tty else "-i")
        elif tty:  # pragma: no cover
            arguments.append("-t")
        arguments.extend(map(str, flags))
        if not root:
            if docker.variant == "podman":
                arguments += ["--userns", "keep-id", "--user=user:wheel"]
            elif platform.system() != "Windows":
                arguments += [f"--user={os.getuid()}"]
            else:  # pragma: no cover
                arguments += ["--user=1000"]
        if docker.variant == "docker":
            # https://github.com/moby/moby/issues/45436#issuecomment-1528445371
            arguments += ["--ulimit", "nofile=1024:1048576"]

        arguments.append(base)
        if isinstance(command, str):
            arguments += ["sh", "-ec", textwrap.dedent(command)]
        elif command is not None:
            arguments += command
        human_friendly = f"$ {docker} run --rm " + shlex.join(arguments)
        if verbosity >= 1:
            print(termcolor.colored(human_friendly, "blue"), flush=True)

        p = _run([docker, "create"] + arguments, stdout=PIPE, stderr=PIPE)
        if p.returncode:  # pragma: no cover
            raise SystemExit(p.stderr.decode())
        self.id = p.stdout.decode().splitlines()[-1]
        p = _run([docker, "container", "start", "-ia" if interactive else "-a", self.id],
                 stdout=None if verbosity >= 2 else DEVNULL,
                 stderr=STDOUT if verbosity >= 2 else PIPE)
        if verbosity >= 2 and self.output:
            print(flush=True)
        self.returncode = p.returncode
        if check and self.returncode:
            if post_mortem and globals()["post_mortem"]:
                for shell in ["/usr/bin/fish", "/usr/bin/zsh", "/usr/sbin/bash", "/usr/bin/bash"]:  # pragma: no branch
                    with contextlib.suppress(Exception):
                        self[shell]
                        break
                else:  # pragma: no cover
                    shell = "sh"

                print("Error occurred. Entering post-mortem debug shell.",
                      "The command polycotylus was trying to run was:",
                      shlex.join(command) if isinstance(command, list) else command, flush=True)
                image = self.commit()
                run(image, [shell], *flags, volumes=volumes, tty=True,
                    interactive=True, root=root, architecture=architecture,
                    verbosity=0)
                _run([docker, "image", "rm", image], stderr=DEVNULL, stdout=DEVNULL)
                (images_cache() / image).unlink()

                raise SystemExit(1)

            if not self.output and p.stderr:
                raise Error(human_friendly, p.stderr.decode())
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
                 stdout=PIPE, stderr=PIPE)
        if p.returncode:
            raise FileNotFoundError(f"{self.id}:{path}")
        return TarFile("", "r", io.BytesIO(p.stdout))

    def file(self, path):
        with self[path] as tar:
            with tar.extractfile(Path(path).name) as f:
                return f.read()

    def commit(self):
        command = [docker, "commit", self.id]
        if docker.variant == "podman":
            command.append("-q")
        return _audit_image(_run(command, stdout=PIPE, text=True).stdout.strip())


def _tee_run(command, verbosity, **kwargs):
    with Popen(command, stderr=STDOUT, stdout=PIPE, **kwargs) as p:
        chunks = []
        while (chunk := p.stdout.readline()) or p.poll() is None:
            chunks.append(chunk)
            if verbosity >= 2:
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
        if verbosity >= 2:
            print()
    return p.returncode, b"".join(chunks).decode()


def _audit_image(hash):
    path = images_cache() / hash
    path.write_bytes(b"")
    caches = list(images_cache().iterdir())
    if len(caches) > 100:  # pragma: no cover
        # Apply a dumb least recently used deletion policy for old polycotylus
        # generated docker image caches.
        caches.sort(key=lambda path: path.stat().st_mtime)
        for path in caches[:-100]:
            _run([docker, "image", "rm", path.name], stderr=DEVNULL, stdout=DEVNULL)
            path.unlink()
    return hash


def build(dockerfile, root, *flags, target=None, architecture=machine(), verbosity=None):
    command = [docker, "build", "-f", str(dockerfile), "--network=host", "."]
    if verbosity is None:
        verbosity = _verbosity()
    if target:
        command += ["--target", target]
    command += ["--pull", "--platform=linux/" + architecture, *flags]
    if verbosity >= 1:
        print(termcolor.colored("$ " + shlex.join(command), "blue"))
    returncode, output = _tee_run(command, verbosity, cwd=root,
                                  env={"DOCKER_SCAN_SUGGEST": "false", **os.environ})
    if returncode:
        raise Error("$ " + shlex.join(command), output)
    return _audit_image(_parse_build_output(output))


def _parse_build_output(output):
    match = re.search(r"Successfully built ([a-f0-9]{8,})\n*\Z", output) \
        or re.search(r"([a-f0-9]{64})\n*\Z", output) \
        or re.search(r".*writing image (sha256:[a-f0-9]{64})", output, re.DOTALL) \
        or re.search(r".*naming to moby-dangling@(sha256:[a-f0-9]{64})", output)
    return match[1]


def lazy_run(base, command, **kwargs):
    assert isinstance(command, list)
    base_info = json.loads(_run([docker, "image", "inspect", base], stdout=PIPE).stdout)
    base = base_info[0]["Id"]
    _images = _run([docker, "images", "-a", "-q"], stdout=PIPE).stdout.decode().split()
    images = json.loads(_run([docker, "image", "inspect"] + _images, stdout=PIPE).stdout)
    for image in images:
        if image.get("Parent", "").startswith((base, "sha256:" + base)):
            if (image.get("ContainerConfig") or image["Config"])["Cmd"] == command:
                _time = time.strptime(image["Created"].split(".")[0].rstrip("Z"),
                                      "%Y-%m-%dT%H:%M:%S")
                if time.time() - time.mktime(_time) < 3600 * 24 * 3:
                    return image["Id"]
    container = run(base, command, **kwargs)
    return container.commit()


def _verbosity():
    return int(os.environ.get("POLYCOTYLUS_VERBOSITY", 2))


class Error(Exception):
    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return f"Docker command:\n    {self.command}\n" \
            "returned an error:\n" + self.output


def setup_binfmt():
    if docker.variant == "podman":
        return
    if _run([docker, "image", "inspect", "docker.io/multiarch/qemu-user-static"],
            stderr=DEVNULL, stdout=DEVNULL).returncode:  # pragma: no cover
        _run([docker, "pull", "docker.io/multiarch/qemu-user-static"])
    p = _run([docker, "run", "--rm", "--privileged", "docker.io/multiarch/qemu-user-static",
              "--reset", "-p", "yes", "--credential", "yes"], stderr=STDOUT, stdout=PIPE)
    assert p.returncode == 0, p.stdout.decode()
