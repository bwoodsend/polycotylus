"""
Tutorial: https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package
Reference: https://wiki.alpinelinux.org/wiki/APKBUILD_Reference
"""

import os
import re
import shlex
from functools import lru_cache
import hashlib
from pathlib import Path
import contextlib
import platform

from polycotylus import _misc, _docker
from polycotylus._project import spdx_osi_approved, spdx_exceptions
from polycotylus._base import BaseDistribution


class Alpine(BaseDistribution):
    name = "alpine"
    version = "3.22"
    base_image = "alpine:3.22"
    python_extras = {
        "tkinter": ["python3-tkinter"],
        "dbm.gnu": ["python3-gdbm"],
    }
    _formatter = _misc.Formatter("\t")
    supported_architectures = {
        "aarch64": "aarch64",
        "armv7": "arm",
        "ppc64le": "ppc64le",
        "riscv64": "riscv64",
        # "s390x": "s390x",  sudo has started stalling on this platform
        "x86": "i386",
        "x86_64": "x86_64",
    }
    _packages = {
        "python": "python3",
        "image-conversion": ["imagemagick"],
        "svg-conversion": ["imagemagick", "librsvg"],
        "xvfb-run": "xvfb-run",
        "font": "ttf-dejavu",
    }

    @_misc.classproperty
    def tag(_, cls):
        return cls.version

    @classmethod
    @lru_cache()
    def _package_manager_queries(cls):
        with cls.mirror:
            container = _docker.run(cls.base_image, f"""
                {cls.mirror.install_command}
                apk update
                apk search -q > /packages
                apk info -q > /base-packages
                apk add --simulate alpine-sdk > /sdk-packages
                apk search -x python3 > /python-version
            """, tty=True)
        _read = lambda path: container.file(path).decode()
        cls._available_packages = set(re.findall("([^\n]+)", _read("/packages")))
        preinstalled = re.findall("([^\n]+)", _read("/base-packages"))
        sdk = re.findall("Installing ([^ ]+)", _read("/sdk-packages"))
        cls._build_base_packages = set(preinstalled + sdk)
        cls._python_version = re.match("python3-([^-]+)", _read("/python-version"))[1]

    @staticmethod
    def python_package_convention(pypi_name):
        return "py3-" + pypi_name

    @staticmethod
    def fix_package_name(name):
        return name.lower().replace(".", "-").replace("_", "-")

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

    def apkbuild(self):
        out = f"# Maintainer: {self.project.maintainer_slug}\n"
        if self.project.architecture == "none":
            architecture = "noarch"
        elif self.project.architecture == "any":
            architecture = "all"
        else:
            architecture = " ".join(self.project.architecture)
        top_level = self.project.source_top_level.format(version="$pkgver")
        license_osi_approved, license_devendorable = self._license_info()
        out += _misc.variables(
            pkgname=shlex.quote(self.package_name),
            pkgver=self.project.version,
            pkgrel=1,
            pkgdesc=shlex.quote(self.project.description),
            arch=shlex.quote(architecture),
            license=shlex.quote(self.project.license_spdx) if license_osi_approved else "custom",
            url=self.project.url,
            depends=shlex.quote(" ".join(self.dependencies)),
            makedepends=shlex.quote(" ".join(self.build_dependencies)),
            checkdepends=shlex.quote(" ".join(self.test_dependencies)),
            source=f'"$pkgname-$pkgver.tar.gz::{self.project.source_url.format(version="$pkgver")}"',
            builddir='"$srcdir/_build"',
        )
        subpackages = []
        from packaging.version import Version
        if self.project.contains_py_files:
            if self.version == "edge" or Version(self.version) >= Version("v3.18"):
                subpackages.append("$pkgname-pyc")
        if not license_devendorable:
            subpackages.append("$pkgname-doc")
        if subpackages:
            out += 'subpackages="{}"\n'.format(" ".join(subpackages))
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
        if not license_devendorable:
            for license in self.project.licenses:
                out += self._formatter(f"""
                    install -Dm644 {shlex.quote(license)} -t "$pkgdir-doc/usr/share/licenses/{self.package_name}"
                """, 1)
        out += self.install_desktop_files(1, dest="$builddir")
        out += self.install_icons(1, "$builddir")
        out += "}\n\n"

        _set_pythonpath = 'PYTHONPATH="$builddir/usr/lib/python$(_py3ver)/site-packages"'
        test_command = self.project.test_command.evaluate()
        out += self._formatter(f"""
            check() {{
                cd "$srcdir/{top_level}"
        """)
        if self.project.test_command.multistatement:
            out += self._formatter(f"export {_set_pythonpath}", 1)
            out += self._formatter(test_command, 1)
        else:
            out += self._formatter(f"{_set_pythonpath} {test_command.strip()}", 1)

        out += self._formatter("""
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
               self.package_name, self.project.version))
        return out

    def _license_info(self):
        # A package should use license=custom for non OSI approved license. It
        # should copy its license into /usr/share and ship it in a separate
        # $name-doc subpackage if its either non OSI approved or one of MIT or
        # ISC.
        # https://wiki.alpinelinux.org/wiki/Creating_an_Alpine_package#license
        devendorable = True
        terms = iter(re.findall("[^() ]+", self.project.license_spdx))
        for term in terms:
            if term.upper() in ("AND", "OR"):
                continue
            elif term in ("MIT", "ISC"):
                devendorable = False
            elif term.upper() == "WITH":
                term = next(terms)
                if term not in spdx_exceptions:
                    return (False, False)
            elif term not in spdx_osi_approved:
                return (False, False)
        return (True, devendorable)

    def dockerfile(self):
        public, private = self.abuild_keys()
        return self._formatter(f"""
            FROM {self.base_image} AS base

            RUN {self.mirror.install_command}
            RUN echo -e {repr(public.read_text("utf8"))} > "/etc/apk/keys/{public.name}"

            RUN apk add shadow sudo
            {self._install_user("abuild")}

            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base AS build
            RUN apk add alpine-sdk
            RUN echo 'PACKAGER="{self.project.maintainer_slug}"' >> /etc/abuild.conf
            RUN echo 'MAINTAINER="$PACKAGER"' >> /etc/abuild.conf

            RUN mkdir /home/user/.abuild
            RUN echo 'SRCDEST="/io/"' >> /home/user/.abuild/abuild.conf
            RUN echo 'PACKAGER_PRIVKEY="/home/user/.abuild/{private.name}"' >> /home/user/.abuild/abuild.conf
            RUN touch "/home/user/.abuild/{private.name}"
            RUN chown -R user /home/user/.abuild
            RUN cp "/etc/apk/keys/{public.name}" /home/user/.abuild/
            RUN apk add {shlex.join(self.dependencies + self.build_dependencies + self.test_dependencies)}

            FROM base AS test
            RUN apk add {shlex.join(self.test_dependencies)}

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
            match = re.search("PACKAGER_PRIVKEY=([^\r\n]+)", config.read_text("utf-8"))
            if match:
                private_key, = shlex.split(match[1])
                private_key = Path(os.path.expandvars(private_key)).expanduser()
                public_key = private_key.with_suffix(".rsa.pub")
                assert private_key.exists()
                assert public_key.exists()
                if platform.system() != "Windows":  # pragma: no cover
                    assert private_key.stat().st_uid == os.getuid()
                return public_key, private_key

        with self.mirror:
            container = _docker.run(self.base_image, f"""
                {self.mirror.install_command}
                apk add -q abuild
                echo 'PACKAGER="{self.project.maintainer_slug}"' >> /etc/abuild.conf
                echo 'MAINTAINER="$PACKAGER"' >> /etc/abuild.conf
                abuild-keygen -nq
            """)
        with container["/root/.abuild"] as tar:
            _misc.tar_extract_all(tar, Path.home())
            _, key, _ = sorted(tar.getnames(), key=len)

        if config.exists():
            content = config.read_text("utf-8").rstrip("\n") + "\n"
        else:
            content = ""
        content += f"PACKAGER_PRIVKEY={shlex.quote(str(Path.home() / key))}\n"
        _misc.unix_write(config, content)

        return self.abuild_keys()

    def generate(self):
        super().generate()
        _misc.unix_write(self.distro_root / "APKBUILD", self.apkbuild())
        (self.distro_root / self.version).mkdir(exist_ok=True)

    def build(self):
        public_key, private_key = self.abuild_keys()
        base = self.build_builder_image()
        volumes = [
            (self.distro_root, "/io"),
            (private_key, f"/home/user/.abuild/{private_key.name}"),
            (self.distro_root / self.version, "/home/user/packages"),
        ]
        with self.mirror:
            _docker.run(base, "abuild -f", root=False, volumes=volumes, tty=True,
                        architecture=self.docker_architecture, post_mortem=True)
        _dist = self.distro_root / self.version / self.architecture
        apk = _dist / f"{self.package_name}-{self.project.version}-r1.apk"
        doc = _dist / f"{self.package_name}-doc-{self.project.version}-r1.apk"
        pyc = _dist / f"{self.package_name}-pyc-{self.project.version}-r1.apk"
        apks = {"main": self._make_artifact(apk, "main")}
        if doc.exists():
            apks["doc"] = self._make_artifact(doc, "doc")
        if pyc.exists():
            apks["pyc"] = self._make_artifact(pyc, "pyc")
        return apks

    def test(self, package):
        base = self.build_test_image()
        volumes = [(package.path.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        with self.mirror:
            return _docker.run(base, f"""
                sudo apk add /pkg/{package.path.name}
                {self.project.test_command.evaluate()}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)


class Alpine317(Alpine):
    version = "3.17"
    base_image = "alpine:3.17"
    supported_architectures = {
        i: j for (i, j) in Alpine.supported_architectures.items()
        if i != "riscv64"
    }


class Alpine318(Alpine):
    version = "3.18"
    base_image = "alpine:3.18"
    supported_architectures = Alpine317.supported_architectures


class Alpine319(Alpine):
    version = "3.19"
    base_image = "alpine:3.19"
    supported_architectures = Alpine317.supported_architectures


class Alpine320(Alpine):
    version = "3.20"
    base_image = "alpine:3.20"


class Alpine321(Alpine):
    version = "3.21"
    base_image = "alpine:3.21"


Alpine322 = Alpine


class AlpineEdge(Alpine):
    version = "edge"
    base_image = "alpine:edge"
