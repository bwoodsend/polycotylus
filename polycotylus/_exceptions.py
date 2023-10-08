import textwrap
import re


def _unravel(text):
    return re.sub("(^ .*\n)|\n(?! )", lambda m: m[1] or " ",
                  textwrap.dedent(text.lstrip("\n")), flags=re.M).strip()


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
                  {self.possibilities[-1]}:
        """) + "\n"


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
                  MIT:
        """)


class PackageUnavailableError(PolycotylusUsageError):
    def __init__(self, package, distribution):
        self.package = package
        self.distribution = distribution

    def __str__(self):
        return _unravel(f"""
            Dependency "{self.package}" appears to be unavailable on
            {self.distribution.title()} Linux. You will need to submit
            {self.package} to {self.distribution.title()} Linux's package
            repositories before you can build your own project. It's also
            possible that it is already there but is named something weird,
            in which case, supply its name to the dependency_name_map option in
            the polycotylus.yaml:

            # polycoylus.yaml
            dependency_name_map:
              {self.package}:
                {self.distribution}: whatever-its-really-called
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
        out += _unravel("""
            Linux distributions do not allow linters, formatters or coverage
            tools in testing. Such checks do not reflect the correctness of
            packaging and when new versions of these tools come out, they bring
            new and stricter rules which break builds unnecessarily (bear in
            mind that Linux distributions can not pin the versions of these
            tools).
        """)
        return out
