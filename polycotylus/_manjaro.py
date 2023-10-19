from polycotylus._arch import Arch


class Manjaro(Arch):
    base_image = "docker.io/manjarolinux/base"
    supported_architectures = {
        "aarch64": "aarch64",
        "x86_64": "x86_64",
    }
