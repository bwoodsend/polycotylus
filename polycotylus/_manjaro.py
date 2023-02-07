from polycotylus._mirror import mirrors
from polycotylus._arch import Arch


class Manjaro(Arch):
    name = "manjaro"
    mirror = mirrors[name]
    image = "manjarolinux/base"
