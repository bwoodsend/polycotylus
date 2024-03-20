import re
from functools import lru_cache

from polycotylus import _docker
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

    @classmethod
    @lru_cache()
    def available_licenses(cls):
        out = []
        container = _docker.run(cls.base_image, verbosity=0,
                                architecture=cls.preferred_architecture)
        with container["/usr/share/licenses/spdx"] as tar:
            for member in tar.getmembers():
                m = re.fullmatch("spdx/([^/]+).txt", member.name)
                if m:
                    out.append(m[1])
        assert out
        return out
