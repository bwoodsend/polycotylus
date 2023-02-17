from polycotylus._mirror import mirrors
from polycotylus._arch import Arch


class Manjaro(Arch):
    name = "manjaro"
    mirror = mirrors[name]
    image = "manjarolinux/base"
    supported_architectures = {
        "aarch64": "aarch64",
        "x86_64": "x86_64",
    }
