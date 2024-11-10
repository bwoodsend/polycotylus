from packaging.requirements import Requirement

from polycotylus._alpine import Alpine


class Adelie(Alpine):
    name = "adelie"
    base_image = "docker.io/adelielinux/adelie"
    _packages = {**Alpine._packages, "sdk": "build-tools"}
    python = "python3"

    @classmethod
    def python_package(cls, requirement, dependency_name_map=None):
        if Requirement(requirement).name in {"setuptools", "pip"}:
            return
        return super().python_package(requirement, dependency_name_map)

    def dockerfile(self):
        out = super().dockerfile()
        before, after = out.split("\nFROM base AS test")
        return before + "RUN ln /usr/bin/python3 /usr/bin/python && ln /usr/bin/pip3 /usr/bin/pip\n\nFROM base AS test" + after

    @classmethod
    def _splits_pyc_files(cls):
        return False
