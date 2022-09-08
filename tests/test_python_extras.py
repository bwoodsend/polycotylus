import pytest
from docker import from_env

from polycotylus._mirror import mirrors
from polycotylus import _arch


@pytest.mark.parametrize("name, extras", _arch.Arch.python_extras.items(),
                         ids=repr)
def test_arch(name, extras):
    docker = from_env()
    script = _arch._w("""
        {}
        pacman -Sy --noconfirm python {}
        python -c 'import {}'
    """.format(mirrors["arch"].install, " ".join(extras), name))
    with mirrors["arch"]:
        docker.containers.run("archlinux:base", ["sh", "-c", script],
                              network_mode="host")
