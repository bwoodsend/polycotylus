from polycotylus import _mirror, _misc
from polycotylus._debian import Debian


class Ubuntu(Debian):
    name = "ubuntu"
    tag = "26.04"
    supported_architectures = {
        "amd64": "x86_64",
        "arm64": "aarch64",
        "armhf": "arm/v7",
        "ppc64el": "ppc64le",
        "s390x": "s390x",
    }

    @_misc.classproperty
    def base_image(_, cls):
        return "ubuntu:" + cls.tag

    @_misc.classproperty
    def mirror(_, cls):
        return _mirror.mirrors["ubuntu:" + cls.tag]

    def _install_user(self):
        # Ubuntu docker images come with a user called ubuntu preinstalled with
        # the same UID that polycotylus normally uses. It messes with user
        # groups – get rid of it.
        return "RUN userdel ubuntu\n" + super()._install_user()

    _imagemagick_convert = Debian._imagemagick_convert_legacy


class Ubuntu2404(Ubuntu):
    tag = "24.04"


class Ubuntu2504(Ubuntu):
    tag = "25.04"


class Ubuntu2510(Ubuntu):
    tag = "25.10"


Ubuntu2604 = Ubuntu


class Ubuntu2610(Ubuntu):
    tag = "26.10"
