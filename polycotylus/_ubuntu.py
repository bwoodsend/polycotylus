from polycotylus import _mirror
from polycotylus._debian import Debian


class Ubuntu(Debian):
    name = "ubuntu"
    base_image = "ubuntu:24.04"
    tag = "24.04"
    supported_architectures = {
        "amd64": "x86_64",
        "arm64": "aarch64",
        "armhf": "arm/v7",
        "ppc64el": "ppc64le",
        "s390x": "s390x",
    }
    mirror = _mirror.mirrors["ubuntu2404"]

    def _install_user(self):
        # Ubuntu docker images come with a user called ubuntu preinstalled with
        # the same UID that polycotylus normally uses. It messes with user
        # groups – get rid of it.
        return "RUN userdel ubuntu\n" + super()._install_user()


Ubuntu2404 = Ubuntu


class Ubuntu2410(Ubuntu):
    base_image = "ubuntu:24.10"
    tag = "24.10"
    mirror = _mirror.mirrors["ubuntu2410"]


class Ubuntu2504(Ubuntu):
    base_image = "ubuntu:25.04"
    tag = "25.04"
    mirror = _mirror.mirrors["ubuntu2504"]


class Ubuntu2510(Ubuntu):
    base_image = "ubuntu:25.10"
    tag = "25.10"
    mirror = _mirror.mirrors["ubuntu2510"]
