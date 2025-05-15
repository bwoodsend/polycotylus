import textwrap
import re

import termcolor


def _unravel(text):
    return re.sub("(^ .*\n)|\n(?! )", lambda m: m[1] or " ",
                  textwrap.dedent(text.lstrip("\n")), flags=re.M).strip()


class PolycotylusUsageError(Exception):
    pass


class PolycotylusYAMLParseError(PolycotylusUsageError):
    pass


def key(x):
    return termcolor.colored(x, "cyan")


def comment(x):
    return termcolor.colored(x, "grey")


def string(x):
    return termcolor.colored(x, "green")


def highlight_toml(x):
    x = re.sub(r"\[([\w.-]+)\]", lambda m: "[" + key(m[1]) + "]", x)
    x = re.sub(r"([\"'])[^\"']+\1", lambda m: string(m[0]), x)
    x = re.sub(r"^([\w-]+) =", lambda m: key(m[1]) + " =", x, flags=re.M)
    x = re.sub(r"#.*", lambda m: comment(m[0]), x)
    return x


class AmbiguousLicenseError(PolycotylusUsageError):
    def __init__(self, classifier, possibilities):
        self.classifier = classifier
        self.possibilities = possibilities

    def __str__(self):
        return _unravel(f"""
            Polycotylus can't determine the SPDX license type. The Trove
            classifier {string(repr(self.classifier))} could refer to any of the
            SPDX codes [{", ".join(string(repr(i)) for i in self.possibilities)}].
            Either choose a more specific classifier from
            https://pypi.org/classifiers/ if such a classifier exists or choose
            the appropriate SPDX identifier from https://spdx.org/licenses/ and
            set it in your polycotylus.yaml:
        """) + "\n" + textwrap.dedent(f"""
            {comment("# polycotylus.yaml")}
            {key("license")}: {self.possibilities[-1]}
        """)


class MultipleLicenseClassifiersError(PolycotylusUsageError):
    def __init__(self, names):
        self.names = names

    def __str__(self):
        return _unravel(f"""
            Multiple license classifiers found in the pyproject.toml. It is
            ambiguous whether this means that the project has multiple parts
            with differing licenses or if the whole project is dual licensed.
            Set the {key("license")} field in the polycotylus.yaml to
            disambiguate.
        """) + textwrap.dedent(f"""

                {comment("# polycotylus.yaml")}
                {comment("# For dual license use:")}
                {key("license")}: {" OR ".join(self.names)}
                # {comment("Or for mixed license use:")}
                {key("license")}: {" AND ".join(self.names)}
        """)


class NoLicenseSpecifierError(PolycotylusUsageError):
    def __str__(self):
        return _unravel("""
            No license classifier specified in the pyproject.toml. Choose a
            Trove license classifier from https://pypi.org/classifiers/ and add
            it to your pyproject.toml:
        """) + highlight_toml(textwrap.dedent("""

            # pyproject.toml
            [project]
            classifiers = [
                "License :: OSI Approved :: MIT License",
            ]

        """)) + _unravel("""
            Or select the appropriate SPDX identifier from
            https://spdx.org/licenses/ and set it in your polycotylus.yaml:
        """) + textwrap.dedent(f"""

            {comment("# polycotylus.yaml")}
            {key("license")}: MIT
        """)


class PackageUnavailableError(PolycotylusUsageError):
    def __init__(self, package, distribution):
        self.package = package
        self.distribution = distribution

    def __str__(self):
        return _unravel(f"""
            Dependency {string(repr(self.package))} appears to be unavailable on
            {self.distribution.title()} Linux. Polycotylus does not yet have any
            way of depending on packages which are not already available on
            Linux distributions. You may be able to request it. It also might
            already be there but named something weird, in which case, supply
            its real name to the {key("dependency_name_map")} option in the
            polycotylus.yaml:
        """) + textwrap.dedent(f"""

            {comment("# polycotylus.yaml")}
            {key("dependency_name_map")}:
              {key(self.package)}:
                {key(self.distribution)}: whatever-its-really-called
        """)


class PresubmitCheckError(Exception):
    pass


class NonFunctionalTestDependenciesError(PresubmitCheckError):
    def __init__(self, packages):
        self.packages = packages

    def __str__(self):
        padding = max(map(len, self.packages))
        out = ""
        for package in self.packages:
            out += f"  - {package.ljust(padding)} (from {package.origin})\n"
        out += "\n" + _unravel("""
            Linux distributions do not allow linters, formatters or coverage
            tools in testing. Such checks do not reflect the correctness of
            packaging and when new versions of these tools come out, they bring
            new and stricter rules which break builds unnecessarily (bear in
            mind that Linux distributions can not pin the versions of these
            tools).
        """)
        return out
