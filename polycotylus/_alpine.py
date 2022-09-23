"""
Tutorial: https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package
Reference: https://wiki.alpinelinux.org/wiki/APKBUILD_Reference
"""

import os
import re
import shlex
from functools import cached_property
import hashlib
from pathlib import Path
import tarfile
import io

from docker import from_env

from polycotylus import _shell
from polycotylus._mirror import mirrors
from polycotylus._project import Project
from polycotylus._base import BaseDistribution


class Alpine(BaseDistribution):
    name = "alpine"
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

    @cached_property
    def available_packages(self):
        docker = from_env()
        with mirrors["alpine"]:
            output = docker.containers.run("alpine", ["ash", "-c", self._formatter(f"""
                {mirrors["alpine"].install}
                apk update -q
                apk search -q
            """)
            ], network_mode="host", remove=True)  # yapf: disable
        return set(re.findall("([^\n]+)", output.decode()))

    def python_package_convention(self, pypi_name):
        return "py3-" + pypi_name

    def inject_source(self):
        # abuild insists that the archive must be named something more than just
        # $version.tar.gz.
        # https://wiki.alpinelinux.org/wiki/APKBUILD_Reference#source
        name = f"{self.project.name}-{self.project.version}.tar.gz"
        path = self.distro_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Note that abuild does some rather nasty symlinking rather than
            # copying which breaks an `if path.exists():` check and the open()
            # call below if not removed.
            os.remove(path)
        except OSError:
            pass
        with open(path, "wb") as f:
            f.write(self.project.tar())

    def pkgbuild(self):
        out = f"# Maintainer: {self.project.maintainer} <{self.project.email}>\n"

        out += _shell.variables(
            pkgname=shlex.quote(self.project.name),
            pkgver=self.project.version,
            pkgrel=1,
            pkgdesc=shlex.quote(self.project.description),
            arch="noarch",
            license='MIT',
            url=self.project.url,
            depends=shlex.quote(" ".join(self.dependencies)),
            makedepends=shlex.quote(" ".join(self.make_dependencies)),
            checkdepends=shlex.quote(" ".join(self.test_dependencies)),
            install="",
            source=
            f'"$pkgname-$pkgver.tar.gz::{self.project.source_url.format(version="$pkgver")}"',
            builddir='"$srcdir/_build"',
        )
        out += "\n"

        out += self._formatter("""
            _py3ver() {
                python3 -c 'import sys; print("{0}.{1}".format(*sys.version_info))'
            }
        """)
        out += "\n"

        out += self._formatter("""
            build() {
                cd "$srcdir"
                tar xf "$pkgname-$pkgver.tar.gz" --strip-components=1
                rm -rf "$builddir"
        """)
        out += self.pip_build_command(1, "$builddir")
        out += self._formatter(
            """
                _metadata_dir="$(find "$builddir" -name '*.dist-info')"
                rm -f "$_metadata_dir/direct_url.json"
        """, 1)
        for license in self.project.licenses:
            out += self._formatter(f'rm -f "$_metadata_dir/{license}"', 1)
        out += self.install_desktop_files(1, dest="$builddir")
        out += self.install_icons(1)
        out += "}\n\n"

        out += self._formatter("""
            check() {
                PYTHONPATH="$builddir/usr/lib/python$(_py3ver)/site-packages" xvfb-run pytest "$srcdir/tests"
            }

            package() {
                mkdir -p "$(dirname "$pkgdir")"
                cp -r "$builddir" "$pkgdir"
            }
        """)
        out += "\n"
        out += self._formatter("""
            sha512sums="
            %s  %s-%s.tar.gz
            "
        """ % (hashlib.sha512(self.project.tar()).hexdigest(),
               self.project.name, self.project.version))
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

            COPY .polycotylus/alpine/APKBUILD .
            RUN source ./APKBUILD && apk add $makedepends $checkdepends $depends

            ENTRYPOINT ["sudo", "-u", "user"]
            CMD ["ash"]

            FROM alpine as test
            RUN {self.mirror.install}

            RUN mkdir /io
            WORKDIR /io
            COPY .polycotylus/alpine/APKBUILD .
            RUN source ./APKBUILD && apk add $checkdepends
            RUN echo -e {repr(public.read_text())} > "/etc/apk/keys/{public.name}"

            # This seemingly redundant layer of indirection ensures that
            # xvfb-run (which calls exec) is never the top level process in the
            # container which otherwise leads to exec stalling.
            RUN echo -e '#!/usr/bin/env sh\\n"$@"' >> /bin/intermediate
            RUN chmod +x /bin/intermediate
            ENTRYPOINT ["/bin/intermediate"]
            CMD ["ash"]
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

        docker = from_env()
        with self.mirror:
            container = docker.containers.run("alpine", [
                "ash", "-c",
                self._formatter(f"""
                {self.mirror.install}
                apk add -q abuild
                echo 'PACKAGER="{self.project.maintainer} <{self.project.email}>"' >> /etc/abuild.conf
                echo 'MAINTAINER="$PACKAGER"' >> /etc/abuild.conf
                abuild-keygen -nq
            """)
            ], network_mode="host", detach=True)
            assert container.wait()["StatusCode"] == 0, container.logs().decode(
            )
        raw = b"".join(container.get_archive("/root/.abuild")[0])
        with tarfile.TarFile("", "r", io.BytesIO(raw)) as tar:
            tar.extractall(Path.home())
            _, key, _ = sorted(tar.getnames(), key=len)
        container.remove()

        if config.exists():
            content = config.read_text().rstrip("\n") + "\n"
        else:
            content = ""
        content += f"PACKAGER_PRIVKEY={shlex.quote(str(Path.home() / key))}\n"
        config.write_text(content)

        return self.abuild_keys()


if __name__ == "__main__":
    self = Alpine(Project.from_root("."))
    self.generate()
