"""
https://wiki.manjaro.org/index.php/PKGBUILD
"""
import re
import shlex
from functools import lru_cache
import contextlib
import shutil

from polycotylus import _misc, _docker
from polycotylus._base import BaseDistribution


class Arch(BaseDistribution):
    base_image = "archlinux:base"
    python_prefix = "/usr"
    python_extras = {
        "tkinter": ["tk"],
        "sqlite3": ["sqlite"],
        "decimal": ["mpdecimal"],
        "lzma": ["xz"],
    }
    _formatter = _misc.Formatter()
    _packages = {
        "python": "python",
        "imagemagick": "imagemagick",
        "imagemagick_svg": "librsvg",
        "xvfb-run": "xorg-server-xvfb",
        "font": "ttf-dejavu",
    }
    supported_architectures = {
        "x86_64": "x86_64",
    }
    tag = ""

    @classmethod
    @lru_cache()
    def _package_manager_queries(cls):
        with cls.mirror:
            container = _docker.run(cls.base_image, f"""
                {cls.mirror.install_command}
                pacman -Sy
                pacman -Ssq > /packages
                pacman -Qq > /base-packages
                pacman -Sp --needed base-devel > /sdk-packages
                pacman -Si python > /python-version
            """, architecture=cls.supported_architectures[cls.preferred_architecture], tty=True)
        _read = lambda path: container.file(path).decode()
        cls._available_packages = set(re.findall("([^\n]+)", _read("/packages")))
        preinstalled = re.findall("([^\n]+)", _read("/base-packages"))
        sdk = re.findall(r".*/(.+?)(?:-[^-]+){3}\.pkg\.tar\.zst", _read("/sdk-packages"))
        cls._build_base_packages = set(preinstalled + sdk)
        cls._python_version = re.search("Version +: ([^ -]+)", _read("/python-version"))[1]

    @staticmethod
    def fix_package_name(name):
        return name.lower().replace("_", "-").replace(".", "-")

    @staticmethod
    def python_package_convention(pypi_name):
        return "python-" + pypi_name

    def pkgbuild(self):
        out = f"# Maintainer: {self.project.maintainer_slug}\n"
        top_level = self.project.source_top_level.format(version="$pkgver")
        package = self._formatter("""
            package() {
                cd "%s"
                cp -r _build/* "$pkgdir"
                _metadata_dir="$(find "$pkgdir" -name '*.dist-info')"
                rm -f "$_metadata_dir/direct_url.json"
        """ % top_level)
        license_names = []
        shareable = True
        for spdx in self.project.license_names:
            for name in self.available_licenses():
                if spdx.replace("-", "").startswith(name):
                    license_names.append(name)
                    break
            else:
                for name in ("MIT", "BSD", "ZLIB"):
                    if spdx.upper().startswith(name):
                        license_names.append(name)
                        shareable = False
                        break
                else:
                    shareable = False
                    license_names.append(spdx)
        if not shareable:
            for license in self.project.licenses:
                package += self._formatter(
                    f'install -Dm644 {shlex.quote(license)} '
                    f'-t "$pkgdir/usr/share/licenses/{self.package_name}"', 1)
        for license in self.project.licenses:
            package += self._formatter(f'rm -f "$_metadata_dir/{license}"', 1)

        package += self.install_icons(1, "$pkgdir")
        package += self.install_desktop_files(1, "$pkgdir")

        package += "}\n"
        if self.project.architecture == "none":
            architecture = ["any"]
        elif self.project.architecture == "any":
            architecture = sorted(self.supported_architectures)
        else:
            architecture = sorted(i for i in self.supported_architectures
                                  if i in self.project.architecture)

        out += _misc.variables(
            pkgname=shlex.quote(self.package_name),
            pkgver=self.project.version,
            pkgrel=1,
            pkgdesc=shlex.quote(self.project.description),
            arch=architecture,
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
        dependencies = self.dependencies + self.build_dependencies + self.test_dependencies
        return self._formatter(f"""
            FROM {self.base_image} AS base

            RUN {self.mirror.install_command}
            RUN pacman -Syu --noconfirm --needed sudo
            {self._install_user()}
            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base as build
            ENV LANG C
            RUN echo 'PACKAGER="{self.project.maintainer_slug}"' >> /etc/makepkg.conf
            RUN pacman -Syu --noconfirm --needed base-devel {shlex.join(dependencies)}

            FROM base AS test
            RUN pacman -Syu --noconfirm --needed {shlex.join(self.test_dependencies)}
    """)

    def generate(self):
        with contextlib.suppress(FileNotFoundError):
            (self.distro_root / "pkg").chmod(0o755)
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root / "src")
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root / "pkg")
        super().generate()
        _misc.unix_write(self.distro_root / "PKGBUILD", self.pkgbuild())

    def build(self):
        with self.mirror:
            _docker.run(self.build_builder_image(), "makepkg -fs --noconfirm",
                        volumes=[(self.distro_root, "/io")], root=False,
                        architecture=self.docker_architecture, tty=True, post_mortem=True)
        architecture = self.architecture if self.project.architecture != "none" else "any"
        package, = self.distro_root.glob(
            f"{self.package_name}-{self.project.version}-*-{architecture}.pkg.tar.zst")
        return {"main": package}

    def test(self, package):
        with self.mirror:
            base = self.build_test_image()
            volumes = [(package.parent, "/pkg")]
            for path in self.project.test_files:
                volumes.append((self.project.root / path, f"/io/{path}"))
            return _docker.run(base, f"""
                sudo pacman -Syu --noconfirm
                sudo pacman -U --noconfirm /pkg/{package.name}
                {self.project.test_command}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)

    @classmethod
    @lru_cache()
    def available_licenses(cls):
        out = []
        container = _docker.run(cls.base_image, verbosity=0,
                                architecture=cls.preferred_architecture)
        with container["/usr/share/licenses/common"] as tar:
            for member in tar.getmembers():
                m = re.fullmatch("common/([^/]+)/license.txt", member.name)
                if m:
                    out.append(m[1])
        return out
