import argparse
import os
from importlib import resources
import re
import contextlib
import sys
import json
from pathlib import Path

import polycotylus


class CompletionAction(argparse.Action):
    files = {
        "fish": "polycotylus.fish",
    }

    def __call__(self, parser, namespace, shell, option_string=None):
        with contextlib.suppress(Exception):
            if sys.stdout.isatty():  # pragma: no cover
                print("# Pipe the output of this command into source or ~/.config/fish/completions/polycotylus.fish\n",
                      file=sys.stderr, flush=True)
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


class AddToRepositoryAction(argparse.Action):
    def __call__(self, parser, namespace, path, option_string=None):
        by_distribution = {}
        for artifact in json.loads(Path(".polycotylus/artifacts.json").read_bytes()):
            cls = polycotylus.distributions[artifact["distribution"]]
            cls.copy_to_repository(path, artifact)
            by_distribution.setdefault(artifact["distribution"], []).append(artifact)

        for (distribution, artifacts) in by_distribution.items():
            cls = polycotylus.distributions[distribution]
            self = cls(polycotylus.Project.from_root("."))
            self.index_repository(Path(path, artifacts[0]["distribution"]), artifacts)
        parser.exit()


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
parser.add_argument("--architecture")
parser.add_argument("--gpg-signing-id")
parser.add_argument("--void-signing-certificate")
parser.add_argument("--post-mortem", action="store_true",
                    help="Enter an in-container interactive shell whenever an "
                    "error occurs in a docker container")
parser.add_argument("--presubmit-check", action=PresubmitCheckAction, nargs=0,
                    help="Run checks specific to submitting a package to official repositories")
parser.add_argument("--add-to-repository", action=AddToRepositoryAction)


def cli(argv=None):
    try:
        assert isinstance(argv, list) or argv is None
        options = parser.parse_args(argv)
        os.environ["POLYCOTYLUS_VERBOSITY"] = str(max(-options.quiet, 0))
        polycotylus._docker.post_mortem = options.post_mortem

        cls = polycotylus.distributions[options.distribution]
        signing_id = None
        if issubclass(cls, polycotylus._base.GPGBased):
            signing_id = options.gpg_signing_id
        elif issubclass(cls, polycotylus.Void):  # pragma: no branch
            signing_id = options.void_signing_certificate
        self = cls(polycotylus.Project.from_root("."), options.architecture,
                   signing_id)
        self.generate()
        artifacts = self.build()
        self.test(artifacts["main"])
        self.update_artifacts_json(artifacts)
    except polycotylus.PolycotylusUsageError as ex:
        raise SystemExit("Error: " + str(ex))
    print(f"Built {len({i.path for i in artifacts.values()})} artifact{'s' if len(artifacts) != 1 else ''}:")
    for (variant, package) in artifacts.items():
        print(f"{variant}: {package.path}")
    return artifacts


def _console_script():  # pragma: no cover
    cli()


if __name__ == "__main__":
    cli()
