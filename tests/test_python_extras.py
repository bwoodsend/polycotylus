import pytest
from docker import from_env

from polycotylus._mirror import mirrors
from polycotylus._arch import python_extras, _w


@pytest.mark.parametrize("name, extras", python_extras.items(), ids=repr)
def test_arch(name, extras):
    docker = from_env()
    script = _w("""
        {}
        pacman -Sy --noconfirm python {}
        python -c 'import {}'
    """.format(mirrors["arch"].install, " ".join(extras), name))
    with mirrors["arch"]:
        docker.containers.run("archlinux:base", ["sh", "-c", script],
                              network_mode="host")
