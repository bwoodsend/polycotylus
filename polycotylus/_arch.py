"""
https://wiki.manjaro.org/index.php/PKGBUILD
"""
import re
import shlex
from functools import lru_cache

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
        package = self._formatter("""
            package() {
                cd "%s-%s"
                cp -r _build/* "$pkgdir"
                _metadata_dir="$(find "$pkgdir" -name '*.dist-info')"
                rm -f "$_metadata_dir/direct_url.json"
        """ % (self.project.name, self.project.version))
        license_names = []
        for license in self.project.licenses:
            content = _normalize_whitespace(
                (self.project.root / license).read_bytes())
            license_name = std_license_path(content)
            if not license_name:
                for license_name in unshareable_license_identifiers:
                    if unshareable_license_identifiers[license_name] in content:
                        break
                else:
                    license_name = "custom"
                package += self._formatter(
                    f'install -Dm644 "$_metadata_dir/{shlex.quote(license)}" '
                    f'-t "$pkgdir/usr/share/licenses/{self.package_name}"', 1)
            license_names.append(license_name)
            package += self._formatter(f'rm "$_metadata_dir/{license}"', 1)

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
                cd "{self.project.name}-{self.project.version}"
        """)
        out += self.pip_build_command(1, into="_build")
        out += self._formatter("}")
        out += "\n"
        out += package
        out += "\n"
        out += self._formatter(f"""
            check() {{
                cd "{self.project.name}-{self.project.version}"
                PYTHONPATH="$(echo _build/usr/lib/python*/site-packages/)"
                PYTHONPATH="$PYTHONPATH" {self.project.test_command}
            }}
        """)
        return out

    def dockerfile(self):
        return self._formatter("""
            FROM archlinux:base-devel AS build

            RUN echo '%%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
            RUN useradd -m -g wheel user
            RUN %s

            RUN mkdir /io && chown user /io
            WORKDIR /io
            COPY .polycotylus/arch/PKGBUILD .
            RUN source ./PKGBUILD && pacman -Sy --noconfirm ${makedepends[*]} ${checkdepends[*]}

            ENTRYPOINT ["sudo", "--preserve-env", "-H", "-u", "user"]
            CMD ["bash"]

            FROM archlinux:base AS test
            RUN %s

            RUN mkdir /io
            WORKDIR /io
            COPY .polycotylus/arch/PKGBUILD .
            RUN source ./PKGBUILD && pacman -Sy --noconfirm ${checkdepends[*]}
    """ % (self.mirror.install, self.mirror.install))

    @mirror.decorate
    def build(self, verbosity=None):
        _docker.run(self.build_builder_image(), "makepkg -fs --noconfirm",
                    volumes=[(self.distro_root, "/io")], verbosity=verbosity)
        package, = self.distro_root.glob(
            f"{self.package_name}-{self.project.version}-*-*.pkg.tar.zst")
        return package

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
    out = {}
    with _docker.run("archlinux:base",
                     verbosity=0)["/usr/share/licenses/common"] as tar:
        for member in tar.getmembers():
            m = re.fullmatch("common/([^/]+)/license.txt", member.name)
            if m:
                with tar.extractfile(member.name) as f:
                    out[m[1]] = f.read()
    return out


unshareable_license_identifiers = {
    "BSD":
        b'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.',
    "MIT":
        b'Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:',
    "ZLIB":
        b"1. The origin of this software must not be misrepresented; you must not claim that you wrote the original software. If you use this software in a product, an acknowledgment in the product documentation would be appreciated but is not required. 2. Altered source versions must be plainly marked as such, and must not be misrepresented as being the original software. 3. This notice may not be removed or altered from any source distribution.",
}

build_script_name = "PKGBUILD"


def _normalize_whitespace(x: bytes):
    return b" ".join(re.findall(rb"\S+", x))


def std_license_path(content: bytes):
    content = _normalize_whitespace(content)
    for (name, body) in available_licenses().items():
        if b" ".join(re.findall(rb"\S+", body)) == content:
            return name


if __name__ == "__main__":
    self = Arch(Project.from_root("."))
    self.generate()
    self.test(self.build())
