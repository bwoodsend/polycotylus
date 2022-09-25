from subprocess import run as _run, PIPE, DEVNULL, STDOUT
import re
import io
import shlex
import textwrap
from tarfile import TarFile
import sys


class run:

    def __init__(self, base, command=None, volumes=(), check=True,
                 interactive=False):
        __tracebackhide__ = True
        arguments = ["--network=host"]
        for (source, dest) in volumes:
            arguments.append(f"-v{source}:{dest}")
        if interactive:
            arguments.append("-it" if sys.stdin.isatty() else "-i")
        arguments.append(base)
        if isinstance(command, str):
            arguments += ["sh", "-c", textwrap.dedent(command)]
        elif command is not None:
            arguments += command
        human_friendly = "$ docker run --rm " + shlex.join(arguments)
        print(human_friendly, flush=True)

        p = _run(["docker", "create"] + arguments, stdout=PIPE)
        self.id = p.stdout.decode().splitlines()[-1]
        if interactive:
            _run(["docker", "start", self.id], stdout=DEVNULL)
            if _run(["docker", "container", "attach", self.id]).returncode:
                logs = _run(["docker", "logs", self.id], stderr=STDOUT,
                            stdout=PIPE, text=True).stdout
                raise Error(human_friendly, logs)

        else:
            p = _run(["docker", "container", "start", "-a", self.id],
                     stderr=STDOUT, stdout=PIPE, text=True)
            if check and p.returncode:
                raise Error(human_friendly, p.stdout)
            self.output = p.stdout
            self.returncode = p.returncode

    def __del__(self):
        try:
            _run(["docker", "container", "rm", "-f", self.id], stdout=DEVNULL)
        except (AttributeError, ImportError, TypeError):  # pragma: no cover
            pass

    def __getitem__(self, path):
        p = _run(["docker", "container", "cp", f"{self.id}:{path}", "-"],
                 stdout=PIPE)
        return TarFile("", "r", io.BytesIO(p.stdout))

    def commit(self):
        return _run(["docker", "commit", self.id], stdout=PIPE,
                    text=True).stdout.strip()


def build(dockerfile, root, target=None):
    command = ["docker", "build", "-f", str(dockerfile), "--network=host", "."]
    if target:
        command += ["--target", target]
    print("$", shlex.join(command))
    p = _run(command, cwd=root, stdout=PIPE, text=True, stderr=STDOUT)
    if p.returncode:
        raise Error("$ " + shlex.join(command), p.stdout)
    return next(m for line in p.stdout.splitlines()[::-1] if (
        m := re.search("Successfully built (.*)", line)))[1]  # pragma: no cover


class Error(Exception):

    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return f"Docker command:\n    {self.command}\n" \
            "returned an error:\n" + textwrap.indent(self.output, "    ")
