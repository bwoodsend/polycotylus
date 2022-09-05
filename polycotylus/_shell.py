import textwrap
import shlex


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
        text = textwrap.dedent(text).strip().replace("    ", self.indentation)
        return textwrap.indent(text, self.indentation * level) + "\n"
