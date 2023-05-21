import textwrap
import shlex
import re


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

    def textblock(self):
        return TextBlock(self)


class TextBlock:
    def __init__(self, formatter):
        self._contents = []
        self._formatter = formatter

    def __iadd__(self, text):
        self._contents.append(self._formatter(text))
        return self

    def add_indented(self, text, level):
        self._contents.append(self._formatter(text, level))

    def __str__(self):
        return "".join(self._contents)


class classproperty:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, cls):
        return self.method(instance, cls)
