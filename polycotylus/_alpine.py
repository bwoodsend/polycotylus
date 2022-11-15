"""
Tutorial: https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package
Reference: https://wiki.alpinelinux.org/wiki/APKBUILD_Reference
"""

import os
import re
import shlex
from functools import lru_cache
import hashlib
import platform
from pathlib import Path
import contextlib

from polycotylus import _shell, _docker
from polycotylus._mirror import mirrors
from polycotylus._project import Project, spdx_osi_approval
from polycotylus._base import BaseDistribution


class Alpine(BaseDistribution):
    name = "alpine"
    mirror = mirrors[name]
    build_script_name = "APKBUILD"
    python_prefix = "/usr"
    python = "python3"
    python_extras = {
        "tkinter": ["python3-tkinter"],
        "sqlite3": ["sqlite"],
        "decimal": ["mpdecimal"],
        "lzma": ["xz"],
        "zlib": ["zlib"],
        "readline": ["readline"],
        "bz2": ["bzip2"],
    }
    _formatter = _shell.Formatter("\t")
    pkgdir = "$builddir"
    imagemagick = "imagemagick"
    imagemagick_svg = "librsvg"
    xvfb_run = "xvfb-run"
    font = "ttf-dejavu"

    @classmethod
    @lru_cache()
    def available_packages(cls):
        with cls.mirror:
            output = _docker.run("alpine", f"""
                {mirrors["alpine"].install}
                apk update -q
                apk search -q
            """, verbosity=0).output
        return set(re.findall("([^\n]+)", output))

    @staticmethod
    def python_package_convention(pypi_name):
        return "py3-" + pypi_name

    @staticmethod
    def fix_package_name(name):
        return name.lower().replace(".", "-").replace("_", "-")

    invalid_package_characters = r"[^.\-_+0-9a-z]"

    def inject_source(self):
        # abuild insists that the archive must be named something more than just
        # $version.tar.gz.
        # https://wiki.alpinelinux.org/wiki/APKBUILD_Reference#source
        name = f"{self.package_name}-{self.project.version}.tar.gz"
        path = self.distro_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            # Note that abuild does some rather nasty symlinking rather than
            # copying which breaks an `if path.exists():` check and the open()
            # call below if not removed.
            os.remove(path)
        with open(path, "wb") as f:
            f.write(self.project.tar())

    def pkgbuild(self):
        out = f"# Maintainer: {self.project.maintainer} <{self.project.email}>\n"
        if self.project.architecture == "none":
            architecture = "noarch"
        elif self.project.architecture == "any":
            architecture = "all"
        else:
            architecture = " ".join(self.project.architecture)
        top_level = self.project.source_top_level.format(version="$pkgver")

        license_names = [
            i if spdx_osi_approval.get(i) else "custom"
            for i in self.project.license_names
        ]
        out += _shell.variables(
            pkgname=shlex.quote(self.package_name),
            pkgver=self.project.version,
            pkgrel=1,
            pkgdesc=shlex.quote(self.project.description),
            arch=shlex.quote(architecture),
            license=shlex.quote(" ".join(license_names)),
            url=self.project.url,
            depends=shlex.quote(" ".join(self.dependencies)),
            makedepends=shlex.quote(" ".join(self.build_dependencies)),
            checkdepends=shlex.quote(" ".join(self.test_dependencies)),
            source=f'"$pkgname-$pkgver.tar.gz::{self.project.source_url.format(version="$pkgver")}"',
            builddir='"$srcdir/_build"',
        )
        if "custom" in license_names:
            out += _shell.variables(subpackages="$pkgname-doc")
        out += "\n"
        out += self.define_py3ver()

        out += self._formatter("""
            build() {
                cd "$srcdir/%s"
                rm -rf "$builddir"
        """ % top_level)
        out += self.pip_build_command(1, "$builddir")
        dist_info_name = re.sub("[-_]+", "_", self.project.name)
        out += self._formatter(f"""
            _metadata_dir="$builddir/usr/lib/python$(_py3ver)/site-packages/{dist_info_name}-$pkgver.dist-info"
            rm -f "$_metadata_dir/direct_url.json"
        """, 1)
        if "custom" in license_names:
            for license in self.project.licenses:
                out += self._formatter(f"""
                    install -Dm644 {shlex.quote(license)} -t "$pkgdir-doc/usr/share/licenses/{self.package_name}"
                """, 1)
        for license in self.project.licenses:
            out += self._formatter(f'rm -f "$_metadata_dir/{license}"', 1)
        out += self.install_desktop_files(1, dest="$builddir")
        out += self.install_icons(1)
        out += "}\n\n"

        out += self._formatter("""
            check() {
                PYTHONPATH="$builddir/usr/lib/python$(_py3ver)/site-packages" %s "$srcdir"
            }

            package() {
                mkdir -p "$(dirname "$pkgdir")"
                cp -r "$builddir" "$pkgdir"
            }
        """ % self.project.test_command)
        out += "\n"
        out += self._formatter("""
            sha512sums="
            %s  %s-%s.tar.gz
            "
        """ % (hashlib.sha512(self.project.tar()).hexdigest(),
               self.package_name, self.project.version))
        return out

    def dockerfile(self):
        public, private = self.abuild_keys()
        return self._formatter(f"""
            FROM alpine AS build
            RUN {self.mirror.install}

            RUN apk add alpine-sdk shadow sudo
            RUN echo 'PACKAGER="{self.project.maintainer} <{self.project.email}>"' >> /etc/abuild.conf
            RUN echo 'MAINTAINER="$PACKAGER"' >> /etc/abuild.conf
            RUN useradd --create-home --uid {os.getuid()} --groups wheel,abuild user

            RUN mkdir /io && chown user /io
            WORKDIR /io
            RUN mkdir /home/user/.abuild
            RUN echo 'SRCDEST="/io/"' >> /home/user/.abuild/abuild.conf
            RUN echo 'PACKAGER_PRIVKEY="/home/user/.abuild/{private.name}"' >> /home/user/.abuild/abuild.conf
            RUN touch "/home/user/.abuild/{private.name}"
            RUN chown -R user /home/user/.abuild
            RUN echo -e {repr(public.read_text())} > "/etc/apk/keys/{public.name}"
            RUN cp "/etc/apk/keys/{public.name}" /home/user/.abuild/

            RUN apk add {" ".join(self.dependencies + self.build_dependencies + self.test_dependencies)}

            ENTRYPOINT ["sudo", "-u", "user"]
            CMD ["ash"]
            COPY .polycotylus/alpine/APKBUILD .

            FROM alpine as test
            RUN {self.mirror.install}

            RUN mkdir /io
            WORKDIR /io
            RUN apk add {" ".join(self.test_dependencies)}
            RUN echo -e {repr(public.read_text())} > "/etc/apk/keys/{public.name}"

            # This seemingly redundant layer of indirection ensures that
            # xvfb-run (which calls exec) is never the top level process in the
            # container which otherwise leads to exec stalling.
            RUN echo -e '#!/usr/bin/env sh\\n"$@"' >> /bin/intermediate
            RUN chmod +x /bin/intermediate
            ENTRYPOINT ["/bin/intermediate"]
            CMD ["ash"]
            COPY .polycotylus/alpine/APKBUILD .
        """)

    def abuild_keys(self):
        abuild_dir = Path.home() / ".abuild"
        config = abuild_dir / "abuild.conf"
        if config.exists():
            match = re.search("PACKAGER_PRIVKEY=([^\r\n]+)", config.read_text())
            if match:
                private_key, = shlex.split(match[1])
                private_key = Path(os.path.expandvars(private_key)).expanduser()
                public_key = private_key.with_suffix(".rsa.pub")
                assert private_key.exists()
                assert public_key.exists()
                assert private_key.stat().st_uid == os.getuid()
                return public_key, private_key

        with self.mirror:
            container = _docker.run("alpine", f"""
                {self.mirror.install}
                apk add -q abuild
                echo 'PACKAGER="{self.project.maintainer} <{self.project.email}>"' >> /etc/abuild.conf
                echo 'MAINTAINER="$PACKAGER"' >> /etc/abuild.conf
                abuild-keygen -nq
            """)
        with container["/root/.abuild"] as tar:
            tar.extractall(Path.home())
            _, key, _ = sorted(tar.getnames(), key=len)

        if config.exists():
            content = config.read_text().rstrip("\n") + "\n"
        else:
            content = ""
        content += f"PACKAGER_PRIVKEY={shlex.quote(str(Path.home() / key))}\n"
        config.write_text(content)

        return self.abuild_keys()

    def generate(self):
        super().generate()
        (self.distro_root / "dist").mkdir(exist_ok=True)

    @mirror.decorate
    def build(self, verbosity=None):
        public_key, private_key = self.abuild_keys()
        base = self.build_builder_image(verbosity)
        volumes = [
            (self.distro_root, "/io"),
            (private_key, f"/home/user/.abuild/{private_key.name}"),
            (self.distro_root / "dist", "/home/user/packages"),
        ]
        _docker.run(base, "abuild", volumes=volumes, verbosity=verbosity)
        _dist = self.distro_root / "dist" / platform.machine()
        apk, = _dist.glob(f"{self.package_name}-{self.project.version}-r*.apk")
        _stem = re.sub(r"^(.*)(-.*-r\d+)$", r"\1-doc\2", apk.stem)
        doc = apk.with_name(_stem + apk.suffix)
        apks = {"main": apk}
        if doc.exists():
            apks["doc"] = doc
        return apks

    @mirror.decorate
    def test(self, package, verbosity=None):
        base = self.build_test_image(verbosity=verbosity)
        volumes = [(package.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        return _docker.run(base, f"""
            apk add /pkg/{package.name}
            {self.project.test_command}
        """, volumes=volumes, verbosity=verbosity)


if __name__ == "__main__":
    self = Alpine(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
