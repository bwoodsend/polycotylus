from argparse import ArgumentParser, Action
import os
from importlib import resources

import polycotylus


class CompletionAction(Action):
    files = {
        "fish": "polycotylus.fish",
    }

    def __call__(self, parser, namespace, shell, option_string=None):
        with resources.open_text("polycotylus._completions", self.files[shell]) as f:
            print(f.read())
        parser.exit()


parser = ArgumentParser("polycotylus",
                        description="Convert Python packages to Linux ones.")
parser.add_argument("distribution", choices=sorted(polycotylus.distributions))
parser.add_argument("--quiet", "-q", action="count", default=-2)
parser.add_argument("--completion", action=CompletionAction,
                    choices=sorted(CompletionAction.files))


def cli(argv=None):
    options = parser.parse_args(argv)
    os.environ["POLYCOTYLUS_VERBOSITY"] = str(max(-options.quiet, 0))

    cls = polycotylus.distributions[options.distribution]
    try:
        self = cls(polycotylus.Project.from_root("."))
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
