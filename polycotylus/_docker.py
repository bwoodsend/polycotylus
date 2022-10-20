from subprocess import run as _run, PIPE, DEVNULL, STDOUT, Popen
import re
import io
import shlex
import textwrap
from tarfile import TarFile
import sys


class run:

    def __init__(self, base, command=None, volumes=(), check=True,
                 interactive=False, verbosity=0):
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
        if verbosity >= 1:
            human_friendly = "$ docker run --rm " + shlex.join(arguments)
            Logger(verbosity).command(human_friendly)

        p = _run(["docker", "create"] + arguments, stdout=PIPE)
        self.id = p.stdout.decode().splitlines()[-1]
        if interactive:
            _run(["docker", "start", self.id], stdout=DEVNULL)
            if _run(["docker", "container", "attach", self.id]).returncode:
                logs = _run(["docker", "logs", self.id], stderr=STDOUT,
                            stdout=PIPE, text=True).stdout
                raise Error(human_friendly, logs)

        else:
            self.returncode, self.output = _tee_run(
                ["docker", "container", "start", "-a", self.id], verbosity)
            if check and self.returncode:
                raise Error(human_friendly, self.output)

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


def _tee_run(command, verbosity=0, **kwargs):
    with Popen(command, stderr=STDOUT, stdout=PIPE, text=True, **kwargs) as p:
        chunks = []
        while (chunk := p.stdout.readline()) or p.poll() is None:
            chunks.append(chunk)
            Logger(verbosity).output(chunk)
    return p.returncode, "".join(chunks)


def build(dockerfile, root, target=None, verbosity=0):
    command = ["docker", "build", "-f", str(dockerfile), "--network=host", "."]
    if target:
        command += ["--target", target]
    Logger(verbosity).command(shlex.join(command))
    returncode, output = _tee_run(command, verbosity, cwd=root)
    if returncode:
        raise Error("$ " + shlex.join(command), output)
    return next(m for line in output.splitlines()[::-1] if (
        m := re.search("Successfully built (.*)", line)))[1]  # pragma: no cover


class Error(Exception):

    def __init__(self, command, output):
        self.command = command
        self.output = output

    def __str__(self):
        return f"Docker command:\n    {self.command}\n" \
            "returned an error:\n" + textwrap.indent(self.output, "    ")


class Logger:
    def __init__(self, level=0):
        self.level = level

    def command(self, *message):
        if self.level >= 1:
            print(*message, flush=True)
        self.any()

    def output(self, *message):
        if self.level >= 2:
            print(*message, end="")
        self.any()

    def any(self):
        if self.level >= 3:
            import random
            import time
            import uuid
            print(time.ctime(), uuid.uuid1(), "INFO", random.choice([
                "Executing logging command",
                "Processing something",
                "Wasting screen space",
                "Entering active method",
                "Thinking",
                "Executing code",
                "Proceeding with current step",
                "Misc logging statement",
                "Choosing next logging message"
                "Running procedural process whose procedure is being processed",
                "Constructing function arguments",
                "Adding two integers together",
                "Setting current status to \"logging\"",
                "Writing to console stdout",
                "Formatting string",
                "Piffle wiffle waffle poff",
            ]), sep=" :: ")
        if self.level >= 4:
            print(pink_flying_unicorn)


pink_flying_unicorn = "\x1b[35m" r"""\
                      . . . .
                      ,`,`,`,`,
. . . .               `\`\`\`\;
`\`\`\`\`,            ~|;!;!;\!
 ~\;\;\;\|\          (--,!!!~`!       .
(--,\\\===~\         (--,|||~`!     ./
 (--,\\\===~\         `,-,~,=,:. _,//
  (--,\\\==~`\        ~-=~-.---|\;/J,
   (--,\\\((```==.    ~'`~/       a |
     (-,.\\('('(`\\.  ~'=~|     \_.  \
        (,--(,(,(,'\\. ~'=|       \\_;>
          (,-( ,(,(,;\\ ~=/        \
          (,-/ (.(.(,;\\,/          )
           (,--/,;,;,;,\\         ./------.
             (==,-;-'`;'         /_,----`. \
     ,.--_,__.-'                    `--.  ` \
    (='~-_,--/        ,       ,!,___--. \  \_)
   (-/~(     |         \   ,_-         | ) /_|
   (~/((\    )\._,      |-'         _,/ /
    \\))))  /   ./~.    |           \_\;
 ,__/////  /   /    )  /
  '===~'   |  |    (, <.
           / /       \. \
         _/ /          \_\
        /_!/            >_\
""" "\x1b[0m"
