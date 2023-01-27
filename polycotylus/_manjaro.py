from polycotylus._mirror import mirrors
from polycotylus._project import Project
from polycotylus._arch import Arch


class Manjaro(Arch):
    name = "manjaro"
    mirror = mirrors[name]
    image = "manjarolinux/base"


if __name__ == "__main__":
    self = Manjaro(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
