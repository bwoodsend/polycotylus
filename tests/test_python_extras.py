from docker import from_env

from polycotylus._arch import python_extras


def test_arch():
    docker = from_env()
    base = docker.containers.run("archlinux:base",
                                 ["pacman", "-Syq", "--noconfirm", "python"],
                                 detach=True)
    base.wait()
    image = base.commit()
    for (name, extras) in python_extras.items():
        if extras:
            command = f"pacman -S --noconfirm {' '.join(extras)} && "
        else:
            command = ""
        command += f"python -c 'import {name}'"
        docker.containers.run(image, ["sh", "-c", command])
