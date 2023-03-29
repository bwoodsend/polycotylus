from argparse import ArgumentParser, Action
import os
import platform
from importlib import resources
import contextlib

import polycotylus


class CompletionAction(Action):
    files = {
        "fish": "polycotylus.fish",
    }

    def __call__(self, parser, namespace, shell, option_string=None):
        with resources.open_text("polycotylus._completions", self.files[shell]) as f:
            print(f.read(), end="")
        parser.exit()


class ListLocalizationAction(Action):
    def __call__(self, parser, namespace, key, option_string=None):
        from polycotylus._yaml_schema import localizations
        with contextlib.suppress(BrokenPipeError):
            print(key.title(), "Tag  Description")
            print("-" * (len(key) + 4), " -----------")
            for (tag, description) in localizations[key].items():
                print(f"{tag}{' ' * (4 + len(key) - len(tag))}  {description}")
        parser.exit()


parser = ArgumentParser("polycotylus",
                        description="Convert Python packages to Linux ones.")
parser.add_argument("distribution", choices=sorted(polycotylus.distributions))
parser.add_argument("--quiet", "-q", action="count", default=-2)
parser.add_argument("--completion", action=CompletionAction,
                    choices=sorted(CompletionAction.files))
parser.add_argument("--list-localizations", action=ListLocalizationAction,
                    choices=["language", "region", "modifier"])
parser.add_argument("--architecture", default=platform.machine())
parser.add_argument("--post-mortem", action="store_true",
                    help="Enter an in-container interactive shell whenever an "
                    "error occurs in a docker container")


def cli(argv=None):
    assert isinstance(argv, list) or argv is None
    options = parser.parse_args(argv)
    os.environ["POLYCOTYLUS_VERBOSITY"] = str(max(-options.quiet, 0))
    polycotylus._docker.post_mortem = options.post_mortem

    cls = polycotylus.distributions[options.distribution]
    try:
        self = cls(polycotylus.Project.from_root("."), options.architecture)
        self.generate()
        artifacts = self.build()
        self.test(artifacts["main"])
    except polycotylus.PolycotylusUsageError as ex:
        raise SystemExit(str(ex))
    print(f"Built {len(artifacts)} artifact{'s' if len(artifacts) != 1 else ''}:")
    for (variant, path) in artifacts.items():
        print(f"{variant}: {path}")


if __name__ == "__main__":
    cli()
