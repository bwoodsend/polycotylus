"""
https://wiki.manjaro.org/index.php/PKGBUILD
"""
import re
import shlex
from functools import lru_cache
import contextlib
import shutil
import os
from pathlib import Path

from polycotylus import _misc, _docker
from polycotylus._base import BaseDistribution, GPGBased


class Arch(GPGBased, BaseDistribution):
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
        "image-conversion": ["imagemagick"],
        "svg-conversion": ["imagemagick", "librsvg"],
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
        with container["/usr/share/licenses/spdx"] as tar:
            cls._devendorable_licenses = []
            cls._devendorable_license_exceptions = []
            for path in tar.getnames():
                if m := re.fullmatch("spdx/([^/]+).txt", path):
                    cls._devendorable_licenses.append(m[1])
                elif m := re.fullmatch("spdx/exceptions/([^/]+).txt", path):
                    cls._devendorable_license_exceptions.append(m[1])
            assert cls._devendorable_licenses
            assert cls._devendorable_license_exceptions

    @staticmethod
    def fix_package_name(name):
        return name.lower().replace("_", "-").replace(".", "-")

    @staticmethod
    def python_package_convention(pypi_name):
        return "python-" + pypi_name

    @classmethod
    def devendorable_licenses(cls):
        cls._package_manager_queries()
        return cls._devendorable_licenses

    @classmethod
    def devendorable_license_exceptions(cls):
        cls._package_manager_queries()
        return cls._devendorable_license_exceptions

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
        license_array, shareable_license = self._license_info()
        if not shareable_license:
            for license in self.project.licenses:
                package += self._formatter(
                    f'install -Dm644 {shlex.quote(license)} '
                    f'-t "$pkgdir/usr/share/licenses/{self.package_name}"', 1)

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
            license=license_array,
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
                local _site_packages="$(python -c "import site; print(site.getsitepackages()[0])")"
        """)
        test_command = self.project.test_command.evaluate()
        if self.project.test_command.multistatement:
            out += self._formatter("""export PYTHONPATH="$PWD/_build/$_site_packages" """, 1)
            out += self._formatter(test_command, 1)
        else:
            out += self._formatter(f"""
                PYTHONPATH="$PWD/_build/$_site_packages" {test_command.strip()}
            """, 1)
        out += self._formatter("}")
        return out

    patch_gpg_locale = ""
    pacman_install = "pacman -Sy --noconfirm --needed archlinux-keyring && pacman -Su --noconfirm --needed"

    def dockerfile(self):
        dependencies = self.dependencies + self.build_dependencies + self.test_dependencies
        out = self._formatter(f"""
            FROM {self.base_image} AS base

            RUN {self.mirror.install_command}
            RUN {self.pacman_install} sudo
            {self._install_user()}
            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base AS build
            RUN echo 'PACKAGER="{self.project.maintainer_slug}"' >> /etc/makepkg.conf
            RUN {self.pacman_install} base-devel {shlex.join(dependencies)}
            {self.patch_gpg_locale}

            FROM base AS test
            RUN {self.pacman_install} {shlex.join(self.test_dependencies)}
        """)
        if self.signing_id:
            out += self._formatter(f"""
                RUN pacman-key --init
                RUN echo '{self.public_key}' | base64 -d | pacman-key --add - && pacman-key --lsign '{self.signing_id}'
            """)
        return out

    def _license_info(self):
        # A package should use license=custom for licenses/exceptions not found
        # in /usr/share/licenses/spdx. It should copy its license into
        # /usr/share/licenses if custom or one of MIT or BSD. License
        # expressions should be split up into an array of identifier.
        # https://wiki.archlinux.org/title/PKGBUILD#license
        devendorable = True
        terms_in = iter(re.findall("[^() ]+", self.project.license_spdx))
        terms_out = []
        for term in terms_in:
            if term.upper() in ("AND", "OR"):
                continue
            elif term.startswith(("MIT", "BSD", "0BSD", "Python", "ZLIB")):
                devendorable = False
            elif term.upper() == "WITH":
                term = next(terms_in)
                if term not in self.devendorable_license_exceptions():
                    devendorable = False
                    term = "custom:" + term
            elif term not in self.devendorable_licenses():
                if term.replace("+", "-or-later") not in self.devendorable_licenses():
                    devendorable = False
                    if not term.startswith("LicenseRef-"):
                        term = "custom:" + term
            terms_out.append(term)
        return (terms_out, devendorable)

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
        if self.signing_id:
            signing_flags = ["--sign", "--key", self.signing_id]
            gpg_home = os.environ.get("GNUPGHOME", Path.home() / ".gnupg")
            gpg_volume = [(str(gpg_home), "/home/user/.gnupg")]
        else:
            signing_flags = []
            gpg_volume = []
        with self.mirror:
            _docker.run(self.build_builder_image(),
                        ["makepkg", "-fs", "--noconfirm", *signing_flags],
                        volumes=[(self.distro_root, "/io"), *gpg_volume],
                        root=False, architecture=self.docker_architecture,
                        tty=True, post_mortem=True, interactive=True)
        architecture = self.architecture if self.project.architecture != "none" else "any"
        package, = self.distro_root.glob(
            f"{self.package_name}-{self.project.version}-*-{architecture}.pkg.tar.zst")
        artifact = self._make_artifact(package, "main")
        if self.signing_id:
            artifact.signature_path = package.with_name(package.name + ".sig")
        return {"main": artifact}

    def test(self, package):
        with self.mirror:
            base = self.build_test_image()
            volumes = [(package.path.parent, "/pkg")]
            for path in self.project.test_files:
                volumes.append((self.project.root / path, f"/io/{path}"))
            return _docker.run(base, f"""
                sudo pacman -Syu --noconfirm
                sudo pacman -U --noconfirm /pkg/{package.path.name}
                {self.project.test_command.evaluate()}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)
