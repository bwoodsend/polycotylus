import pytest
from docker import from_env

from polycotylus._mirror import mirrors
from polycotylus._arch import python_extras, _w


@pytest.mark.parametrize("name, extras", python_extras.items(), ids=repr)
def test_arch(name, extras):
    docker = from_env()
    script = _w("""
        echo 'Server = http://0.0.0.0:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist
        pacman -Sy --noconfirm python {}
        python -c 'import {}'
    """.format(" ".join(extras), name))
    with mirrors["arch"]:
        docker.containers.run("archlinux:base", ["sh", "-c", script],
                              network_mode="host")
