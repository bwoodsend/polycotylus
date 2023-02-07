from argparse import ArgumentParser
import os

import polycotylus

parser = ArgumentParser("polycotylus",
                        description="Convert Python packages to Linux ones.")
parser.add_argument("distribution", choices=sorted(polycotylus.distributions))
parser.add_argument("--quiet", "-q", action="count", default=-2)


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
