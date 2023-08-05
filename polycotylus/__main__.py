import argparse
import os
from importlib import resources
import re
import contextlib

import polycotylus


class CompletionAction(argparse.Action):
    files = {
        "fish": "polycotylus.fish",
    }

    def __call__(self, parser, namespace, shell, option_string=None):
        with resources.open_text("polycotylus._completions", self.files[shell]) as f:
            print(f.read(), end="")
        parser.exit()


class ListLocalizationAction(argparse.Action):
    def __call__(self, parser, namespace, key, option_string=None):
        from polycotylus._yaml_schema import localizations
        with contextlib.suppress(BrokenPipeError):
            print(key.title(), "Tag  Description")
            print("-" * (len(key) + 4), " -----------")
            for (tag, description) in localizations[key].items():
                print(f"{tag}{' ' * (4 + len(key) - len(tag))}  {description}")
        parser.exit()


class ConfigureAction(argparse.Action):
    def __call__(self, parser, namespace, key, option_string=None):
        if not key:
            for option in polycotylus._configuration.options:
                print(f"{option}={polycotylus._configuration.read(option) or ''}")
        else:
            for argument in key:
                match = re.fullmatch(r"([a-z]+)=(.*)", argument)
                if match:
                    if match[2]:
                        polycotylus._configuration.write(*match.groups())
                    else:
                        polycotylus._configuration.clear(match[1])
                else:
                    print(polycotylus._configuration.read(argument) or "")
        parser.exit()


class PresubmitCheckAction(argparse.Action):
    def __call__(self, parser, namespace, key, option_string=None):
        self = polycotylus.Project.from_root(".")
        parser.exit(self.presubmit())


parser = argparse.ArgumentParser(
    "polycotylus",
    description="Convert Python packages to Linux ones.",
    formatter_class=argparse.RawTextHelpFormatter)
parser.add_argument("distribution", choices=sorted(polycotylus.distributions))
parser.add_argument("--quiet", "-q", action="count", default=-2)
parser.add_argument("--completion", action=CompletionAction,
                    choices=sorted(CompletionAction.files))
parser.add_argument("--configure", nargs="*", action=ConfigureAction,
                    help="Manipulate global settings. This is an overloaded syntax:\n"
                    "  * List all settings:  polycotylus --configure\n"
                    "  * Read a setting:     polycotylus --configure docker\n"
                    "  * Write a setting:    polycotylus --configure docker=podman\n"
                    "  * Clear a setting:    polycotylus --configure docker=")
parser.add_argument("--list-localizations", action=ListLocalizationAction,
                    choices=["language", "region", "modifier"])
parser.add_argument("--architecture", default=polycotylus.machine())
parser.add_argument("--post-mortem", action="store_true",
                    help="Enter an in-container interactive shell whenever an "
                    "error occurs in a docker container")
parser.add_argument("--presubmit-check", action=PresubmitCheckAction, nargs=0,
                    help="Run checks specific to submitting a package to official repositories")


def cli(argv=None):
    try:
        assert isinstance(argv, list) or argv is None
        options = parser.parse_args(argv)
        os.environ["POLYCOTYLUS_VERBOSITY"] = str(max(-options.quiet, 0))
        polycotylus._docker.post_mortem = options.post_mortem

        cls = polycotylus.distributions[options.distribution]
        self = cls(polycotylus.Project.from_root("."), options.architecture)
        self.generate()
        artifacts = self.build()
        self.test(artifacts["main"])
    except polycotylus.PolycotylusUsageError as ex:
        raise SystemExit("Error: " + str(ex))
    print(f"Built {len(artifacts)} artifact{'s' if len(artifacts) != 1 else ''}:")
    for (variant, path) in artifacts.items():
        print(f"{variant}: {path}")


if __name__ == "__main__":
    cli()
