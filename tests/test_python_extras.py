import pytest
from docker import from_env

from polycotylus._mirror import mirrors
from polycotylus import _arch, _alpine


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
                              network_mode="host", remove=True)


@pytest.mark.parametrize("name, extras", _alpine.Alpine.python_extras.items(),
                         ids=repr)
def test_alpine(name, extras):
    docker = from_env()
    script = _arch._w("""
        {}
        apk add python3 {}
        python3 -c 'import {}'
    """.format(mirrors["alpine"].install, " ".join(extras), name))
    with mirrors["alpine"]:
        docker.containers.run("alpine", ["ash", "-c", script],
                              network_mode="host", remove=True)
