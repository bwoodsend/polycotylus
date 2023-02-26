import textwrap
import re


def _unravel(text):
    return re.sub("(^ .*\n)|\n(?! )", lambda m: m[1] or " ",
                  textwrap.dedent(text.lstrip("\n")), flags=re.M)


class PolycotylusUsageError(Exception):
    pass


class PolycotylusYAMLParseError(PolycotylusUsageError):
    pass


class AmbiguousLicenseError(PolycotylusUsageError):
    def __init__(self, classifier, possibilities):
        self.classifier = classifier
        self.possibilities = possibilities

    def __str__(self):
        return _unravel(f"""
            Polycotylus can't determine the SPDX license type. The Trove
            classifier '{self.classifier}' could refer to any of the SPDX codes
            {self.possibilities}. Either choose a more specific classifier from
            https://pypi.org/classifiers/ if such a classifier exists or choose
            the appropriate SPDX identifier from https://spdx.org/licenses/ and
            set it in your polycotylus.yaml as:
                spdx:
                  - {self.possibilities[-1]}:
        """)


class NoLicenseSpecifierError(PolycotylusUsageError):
    def __str__(self):
        return _unravel("""
            No license classifier specified in the pyproject.toml. Choose a
            Trove license classifier from https://pypi.org/classifiers/ and add
            it to your pyproject.toml:
                [project]
                classifiers = [
                    "License :: OSI Approved :: MIT License",
                ]
            Or select the appropriate SPDX identifier from
            https://spdx.org/licenses/ and set it in your polycotylus.yaml:
                spdx:
                  - MIT:
        """)
