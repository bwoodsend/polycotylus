import re

from polycotylus import _docker
from polycotylus._project import Project
from polycotylus._base import BaseDistribution
from polycotylus._fedora import Fedora


def strip_version(package):
    return re.split("[<=>]", package)[0].strip()


class RHEL(Fedora):
    name = "rhel"
    image = "registry.access.redhat.com/ubi9/ubi"

    def build_builder_image(self):
        base = BaseDistribution.build_builder_image(self)
        command = ["yum", "install", "-y", "rpm-build", "python3dist(wheel)"] + \
            self.build_dependencies + self.dependencies + self.test_dependencies
        return _docker.lazy_run(base, command, tty=True, volumes=self._mounted_caches)

    @property
    def build_dependencies(self):
        return [strip_version(i) for i in super().build_dependencies]

    @property
    def dependencies(self):
        return [strip_version(i) for i in super().dependencies]

    @property
    def test_dependencies(self):
        return [strip_version(i) for i in super().test_dependencies]

    @classmethod
    def python_package(cls, python_package):
        return f"python3dist({strip_version(python_package)})"


if __name__ == "__main__":
    self = RHEL(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
