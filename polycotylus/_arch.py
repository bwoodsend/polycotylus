import re
import textwrap
import shlex
from functools import lru_cache
from tarfile import TarFile
import io

import pkg_resources
from docker import from_env

from polycotylus._project import Project
from polycotylus._mirror import mirrors


def array(*items):
    return "(" + " ".join(map(shlex.quote, items)) + ")"


@lru_cache()
def available_packages():
    docker = from_env()
    with mirrors["arch"]:
        output = docker.containers.run("archlinux:base", ["bash", "-c", _w("""
            echo 'Server = http://0.0.0.0:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist
            pacman -Sysq
        """)
        ], network_mode="host")  # yapf: disable
    return set(re.findall("([^\n]+)", output.decode()))


def _shell_variables(**variables):
    items = ((i, array(*j) if isinstance(j, list) else j)
             for (i, j) in variables.items())
    return "".join(f"{key}={value}\n" for (key, value) in items)


def python_package(pypi_name):
    requirement = pkg_resources.Requirement(pypi_name)
    name = requirement.key
    if "python-" + name in available_packages():
        requirement.name = "python-" + name
    elif name.startswith("python-") and name in available_packages():
        pass
    else:
        assert 0
    return str(requirement)


def _w(text, level=0):
    return textwrap.indent(textwrap.dedent(text).strip(), "    " * level) + "\n"


@lru_cache()
def available_licenses():
    docker = from_env()
    container = docker.containers.create("archlinux:base")
    chunks, _ = container.get_archive("/usr/share/licenses/common")
    out = {}
    with TarFile("", "r", io.BytesIO(b"".join(chunks))) as tar:
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

python_extras = {
    "tkinter": ["tk"],
    "sqlite3": ["sqlite"],
    "decimal": ["mpdecimal"],
    "lzma": ["xz"],
    "zlib": [],
    "readline": [],
    "bz2": [],
}


def pkgbuild(p: Project):
    out = f"# Maintainer: {p.maintainer} <{p.email}>\n"
    depends = ["python" + p.supported_python]
    depends += map(python_package, p.dependencies)
    [depends.extend(python_extras[i]) for i in p.python_extras]

    package = _w("""
        package() {
            cd "$pkgname-"*
            metadata_dir="$(find "$pkgdir" -name '*.dist-info')"
            rm -f "${metadata_dir}/direct_url.json"
    """)
    license_names = []
    for license in p.licenses:
        content = _normalize_whitespace((p.root / license).read_bytes())
        license_name = std_license_path(content)
        if not license_name:
            for license_name in unshareable_license_identifiers:
                if unshareable_license_identifiers[license_name] in content:
                    break
            else:
                license_name = "custom"
            package += _w(
                f'install -Dm644 "$metadata_dir/{shlex.quote(license)}" '
                f'-t "$pkgdir/usr/share/licenses/{p.name}"', 1)
        license_names.append(license_name)
        package += _w(f'rm "$metadata_dir/{license}"', 1)

    make_depends = [python_package("wheel"), python_package("pip")]
    make_depends += map(python_package, p.build_dependencies)

    icons = [(i["icon"]["source"], i["icon"]["id"])
             for i in p.desktop_entry_points.values()]
    if icons:
        package += _w(icon_installer(icons), 1)
        make_depends.append("imagemagick")
    if any(source.endswith(".svg") for (source, dest) in icons):
        make_depends.append("librsvg")

    for id in p.desktop_entry_points:
        package += _w(
            f'install -Dm644 ".polycotylus/{id}.desktop" '
            f'"$pkgdir/usr/share/applications/{id}.desktop"', 1)

    package += "}\n"

    out += _shell_variables(
        pkgname=shlex.quote(p.name),
        pkgver=p.version,
        pkgrel=1,
        pkgdesc=shlex.quote(p.description),
        arch=["any"],
        url=p.url,
        license=license_names,
        depends=depends,
        makedepends=make_depends,
        checkdepends=[
            *map(python_package, p.test_dependencies), "xorg-server-xvfb",
            "ttf-dejavu"
        ],
        source=f"(${{TEST_SOURCE_URL:-{p.url}}})",
        sha256sums=["SKIP"],
    )
    out += "\n"
    out += build
    out += "\n"
    out += package
    out += "\n"
    out += check
    return out


def _normalize_whitespace(x: bytes):
    return b" ".join(re.findall(rb"\S+", x))


def std_license_path(content: bytes):
    content = _normalize_whitespace(content)
    for (name, body) in available_licenses().items():
        if b" ".join(re.findall(rb"\S+", body)) == content:
            return name


build = _w("""
build() {
    cd "$pkgname-"*
    /bin/pip install --no-compile --prefix="$pkgdir/usr" --no-warn-script-location --no-deps --no-build-isolation .
    python -m compileall --invalidation-mode=unchecked-hash -s "$pkgdir" "$pkgdir/usr/lib/"
}
""")

check = _w("""
check() {
    PYTHONPATH="$(echo "$pkgdir"/usr/lib/python*/site-packages/)"
    PYTHONPATH="$PYTHONPATH" xvfb-run pytest "$pkgname-"*/tests
}
""")

dockerfile = _w("""
FROM archlinux:base-devel AS build

RUN echo '%wheel ALL=(ALL:ALL) NOPASSWD: ALL' >> /etc/sudoers
RUN useradd -m -g wheel user
RUN echo 'Server = http://0.0.0.0:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist

RUN mkdir /io && chown user /io
WORKDIR /io
COPY .polycotylus/arch/PKGBUILD .
RUN source ./PKGBUILD && pacman -Sy --noconfirm ${makedepends[*]} ${checkdepends[*]}

ENTRYPOINT ["sudo", "--preserve-env", "-H", "-u", "user"]
CMD ["bash"]

FROM archlinux:base AS test
RUN echo 'Server = http://0.0.0.0:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist

RUN mkdir /io
WORKDIR /io
COPY .polycotylus/arch/PKGBUILD .
RUN source ./PKGBUILD && pacman -Sy --noconfirm ${checkdepends[*]}
""")


def icon_installer(icons):
    out = _w("""
        for size in 16 22 24 32 48 128; do
            icon_dir="$pkgdir/usr/share/icons/hicolor/${size}x$size/apps"
            mkdir -p "$icon_dir"
    """)
    for (source, dest) in icons:
        out += _w(
            f'convert -background "#00000000" -resize $size +set date:create '
            f'+set date:modify "{source}" "$icon_dir/{dest}.png"', 1)
    out += _w("done")
    return out


if __name__ == "__main__":
    p = Project.from_root(".")
    (p.root / ".polycotylus/arch/PKGBUILD").write_text(pkgbuild(p),
                                                       encoding="utf-8")
    (p.root / ".polycotylus/arch/Dockerfile").write_text(
        dockerfile, encoding="utf-8")
