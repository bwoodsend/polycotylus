import os
from pathlib import Path
import contextlib

import platformdirs

from polycotylus import _misc, _exceptions

options = {"docker"}


def config_paths():
    return list(map(Path, [
        platformdirs.user_config_dir("polycotylus", appauthor=False),
        *platformdirs.site_config_dir("polycotylus", appauthor=False,
                                      multipath=True).split(os.pathsep),
    ]))


def read(key):
    for directory in config_paths():
        with contextlib.suppress(OSError):
            return (directory / key).read_text("utf-8")


def write(key, value):
    if key not in options:
        raise _exceptions.PolycotylusUsageError(
            f"Unknown configuration option {_exceptions.key(repr(key))}. "
            f"Supported options are {_exceptions.highlight_toml(str(options))}")
    path = Path(platformdirs.user_config_dir("polycotylus", appauthor=False), key)
    path.parent.mkdir(parents=True, exist_ok=True)
    _misc.unix_write(path, value)


def clear(key):
    for directory in config_paths():
        with contextlib.suppress(FileNotFoundError):
            (directory / key).unlink()
