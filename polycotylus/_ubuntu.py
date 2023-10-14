from polycotylus import _mirror
from polycotylus._debian import Debian


class Ubuntu(Debian):
    name = "ubuntu"
    image = "ubuntu:23.10"
    tag = "23.10"
    supported_architectures = {
        "amd64": "x86_64",
        "arm64": "aarch64",
        "armhf": "arm/v7",
        "ppc64el": "ppc64le",
        "s390x": "s390x",
    }
    mirror = _mirror.mirrors["ubuntu2310"]

    def _install_user(self):
        # Ubuntu docker images come with a user called ubuntu preinstalled with
        # the same UID that polycotylus normally uses. It messes with user
        # groups – get rid of it.
        return "RUN userdel ubuntu\n" + super()._install_user()


Ubuntu2310 = Ubuntu


class Ubuntu2304(Ubuntu):
    image = "ubuntu:23.04"
    tag = "23.04"
    mirror = _mirror.mirrors["ubuntu2304"]
