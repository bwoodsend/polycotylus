from polycotylus._arch import Arch


class Manjaro(Arch):
    base_image = "docker.io/manjarolinux/base"
    supported_architectures = {
        "aarch64": "aarch64",
        "x86_64": "x86_64",
    }

    def _install_user(self):
        # Manjaro docker images come with a user called builder preinstalled
        # with the same UID that polycotylus normally uses. It moves the home
        # directory – get rid of it.
        return "RUN userdel builder\n" + super()._install_user()

    patch_gpg_locale = r"""RUN mv /usr/sbin/gpg /usr/sbin/_gpg && echo -e '#!/bin/sh\nLANG=C.UTF8 _gpg "$@"' > /usr/sbin/gpg && chmod +x /usr/sbin/gpg"""
