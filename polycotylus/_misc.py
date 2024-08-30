import textwrap
import shlex
import re
import tarfile
import sys
import importlib.resources


def array(*items):
    return "(" + " ".join(map(shlex.quote, items)) + ")"


def variables(**variables):
    items = ((i, array(*j) if isinstance(j, list) else j)
             for (i, j) in variables.items())
    return "".join(f"{key}={value}\n" for (key, value) in items)


class Formatter:
    def __init__(self, indentation="  "):
        self.indentation = indentation

    def __call__(self, text, level=0):
        text = textwrap.dedent(text).strip()
        text = re.sub("^ +", lambda m: len(m[0]) // 4 * self.indentation, text, flags=re.M)
        return textwrap.indent(text, self.indentation * level) + "\n"


class classproperty:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, cls):
        return self.method(instance, cls)


def unix_write(path, text):
    """A Windows-proof equivalent to pathlib.Path(path).write_text(text).

    * Always use utf-8
    * Never convert LF line endings to CRLF

    """
    with open(path, "wb") as f:
        f.write(text.encode())


def tar_extract_all(tar, path):
    if hasattr(tarfile, "data_filter"):  # pragma: no cover
        tar.extractall(path, filter=tarfile.data_filter)
    else:  # pragma: no cover
        tar.extractall(path)


def read_resource(name):
    if sys.version_info >= (3, 12):
        return (importlib.resources.files("polycotylus") / name).read_bytes()
    else:
        parts = ("polycotylus", *name.split("/"))
        return importlib.resources.read_binary(".".join(parts[:-1]), parts[-1])
