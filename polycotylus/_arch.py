"""
https://wiki.manjaro.org/index.php/PKGBUILD
"""
import re
import shlex
from functools import lru_cache
import contextlib

from polycotylus import _shell, _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors
from polycotylus._base import BaseDistribution


class Arch(BaseDistribution):
    name = "arch"
    mirror = mirrors[name]
    python_prefix = "/usr"
    python_extras = {
        "tkinter": ["tk"],
        "sqlite3": ["sqlite"],
        "decimal": ["mpdecimal"],
        "lzma": ["xz"],
        "zlib": [],
        "readline": [],
        "bz2": [],
    }
    xvfb_run = "xorg-server-xvfb"
    _formatter = _shell.Formatter()

    @staticmethod
    @lru_cache()
    def available_packages():
        with mirrors["arch"]:
            output = _docker.run(
                "archlinux:base", f"""
                {mirrors["arch"].install}
                pacman -Sysq
            """, verbosity=0).output
        return set(re.findall("([^\n]+)", output))

    invalid_package_characters = "[^a-z0-9-]"

    @staticmethod
    def fix_package_name(name):
        return name.lower().replace("_", "-").replace(".", "-")

    @staticmethod
    def python_package_convention(pypi_name):
        return "python-" + pypi_name

    def pkgbuild(self):
        out = f"# Maintainer: {self.project.maintainer} <{self.project.email}>\n"
        top_level = self.project.source_top_level.format(version="$pkgver")
        package = self._formatter("""
            package() {
                cd "%s"
                cp -r _build/* "$pkgdir"
                _metadata_dir="$(find "$pkgdir" -name '*.dist-info')"
                rm -f "$_metadata_dir/direct_url.json"
        """ % top_level)
        license_names = []
        sharable = True
        for spdx in self.project.license_names:
            for name in available_licenses():
                if spdx.replace("-", "").startswith(name):
                    license_names.append(name)
                    break
            else:
                for name in ("MIT", "BSD", "ZLIB"):
                    if spdx.upper().startswith(name):
                        license_names.append(name)
                        sharable = False
                        break
                else:
                    sharable = False
                    license_names.append(spdx)
        if not sharable:
            for license in self.project.licenses:
                package += self._formatter(
                    f'install -Dm644 {shlex.quote(license)} '
                    f'-t "$pkgdir/usr/share/licenses/{self.package_name}"', 1)
        for license in self.project.licenses:
            package += self._formatter(f'rm -f "$_metadata_dir/{license}"', 1)

        package += self.install_icons(1)
        package += self.install_desktop_files(1)

        package += "}\n"
        if self.project.architecture == "none":
            architecture = "any"
        else:
            architecture = "x86_64"

        out += _shell.variables(
            pkgname=shlex.quote(self.package_name),
            pkgver=self.project.version,
            pkgrel=1,
            pkgdesc=shlex.quote(self.project.description),
            arch=[architecture],
            url=self.project.url,
            license=license_names,
            depends=self.dependencies,
            makedepends=self.build_dependencies,
            checkdepends=self.test_dependencies,
            source=f'("{self.project.source_url.format(version="$pkgver")}")',
            sha256sums=["SKIP"],
        )
        out += "\n"
        out += self._formatter(f"""
            build() {{
                cd "{top_level}"
        """)
        out += self.pip_build_command(1, into="_build")
        out += self._formatter("}")
        out += "\n"
        out += package
        out += "\n"
        out += self._formatter(f"""
            check() {{
                cd "{top_level}"
                PYTHONPATH="$(echo _build/usr/lib/python*/site-packages/)"
                PYTHONPATH="$PYTHONPATH" {self.project.test_command}
            }}
        """)
        return out

    def dockerfile(self):
        return self._formatter(f"""
            FROM archlinux:base-devel AS build

            RUN echo '%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
            RUN useradd -m -g wheel user
            RUN {self.mirror.install}
            ENV LANG C
            RUN echo 'PACKAGER="{self.project.maintainer} <{self.project.email}>"' >> /etc/makepkg.conf

            RUN mkdir /io && chown user /io
            WORKDIR /io
            RUN pacman -Sy --noconfirm {" ".join(self.dependencies + self.build_dependencies + self.test_dependencies)}

            ENTRYPOINT ["sudo", "--preserve-env", "-H", "-u", "user"]
            CMD ["bash"]
            COPY .polycotylus/arch/PKGBUILD .

            FROM archlinux:base AS test
            RUN {self.mirror.install}

            RUN mkdir /io
            WORKDIR /io
            RUN pacman -Sy --noconfirm {" ".join(self.test_dependencies)}
            COPY .polycotylus/arch/PKGBUILD .
    """)

    def generate(self):
        with contextlib.suppress(FileNotFoundError):
            (self.distro_root / "pkg").chmod(0o755)
        super().generate()

    @mirror.decorate
    def build(self, verbosity=None):
        _docker.run(self.build_builder_image(), "makepkg -fs --noconfirm",
                    volumes=[(self.distro_root, "/io")], verbosity=verbosity)
        package, = self.distro_root.glob(
            f"{self.package_name}-{self.project.version}-*-*.pkg.tar.zst")
        return {"main": package}

    @mirror.decorate
    def test(self, package, verbosity=None):
        base = self.build_test_image(verbosity=verbosity)
        volumes = [(package.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        return _docker.run(
            base, f"""
            pacman -Sy
            pacman -U --noconfirm /pkg/{package.name}
            {self.project.test_command}
        """, volumes=volumes, verbosity=verbosity)


@lru_cache()
def available_licenses():
    out = []
    with _docker.run("archlinux:base",
                     verbosity=0)["/usr/share/licenses/common"] as tar:
        for member in tar.getmembers():
            m = re.fullmatch("common/([^/]+)/license.txt", member.name)
            if m:
                out.append(m[1])
    return out


if __name__ == "__main__":
    self = Arch(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
