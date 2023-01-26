"""
https://github.com/void-linux/void-packages/blob/master/Manual.md
"""
import re
from functools import lru_cache
import hashlib
import contextlib
import time
import shutil
import platform
import shlex
import textwrap

import pkg_resources

from polycotylus import _shell, _docker
from polycotylus._project import Project
from polycotylus._mirror import mirrors, cache_root
from polycotylus._base import BaseDistribution, _deduplicate


class Void(BaseDistribution):
    name = "void"
    mirror = mirrors[name]
    python_prefix = "/usr"
    python = "python3"
    python_extras = {
        "tkinter": ["python3-tkinter"],
        "sqlite3": [],
        "decimal": [],
        "lzma": [],
        "zlib": [],
        "readline": [],
        "bz2": [],
    }
    imagemagick = "ImageMagick"
    xvfb_run = "xvfb-run util-linux"
    font = "dejavu-fonts-ttf"
    _formatter = _shell.Formatter()
    image = "ghcr.io/void-linux/void-linux:latest-mini-x86_64-musl"
    invalid_package_characters = "[^a-zA-Z0-9_+.-]"

    @classmethod
    @lru_cache()
    def _lookup_packages(cls):
        with cls.mirror:
            output = _docker.run(cls.image, f"""
                {cls.mirror.install}
                xbps-install -ySu xbps > /dev/null
                echo '~~~~~~'
                xbps-query -Rs ''
                echo '~~~~~~'
                xbps-query -Rx base-chroot
            """, verbosity=0).output
        _, all, base = output.split("~~~~~~")
        cls._all_packages = re.findall(r"\[-\] ([^ ]+)-[^ ]", all)
        cls._base_packages = re.findall(r"^([^>]+)", base)

    @classmethod
    def available_packages(cls):
        cls._lookup_packages()
        return cls._all_packages

    @classmethod
    def build_base_packages(cls):
        cls._lookup_packages()
        return cls._base_packages

    @property
    def build_dependencies(self):
        out = super().build_dependencies
        out.remove(self.python_package("pip"))
        return out

    @classmethod
    def fix_package_name(cls, name):
        return name

    @classmethod
    def python_package_convention(cls, pypi_name):
        wheel_packaged_name = re.sub("-+", "-", pypi_name.replace("_", "-"))
        return "python3-" + wheel_packaged_name

    @classmethod
    def python_package(cls, requirement):
        requirement = pkg_resources.Requirement(requirement)
        normalised = re.sub("[._-]+", "-", requirement.name.lower())
        with_prefix = cls.python_package_convention(normalised)

        for package in cls.available_packages():
            _package = re.sub("[._-]+", "-", package.lower())
            if _package == normalised or _package == with_prefix:
                break
        else:
            assert 0
        requirement.name = package
        return str(requirement)

    def dockerfile(self):
        dependencies = _deduplicate(self.dependencies + self.build_dependencies
                                    + self.test_dependencies)
        return self._formatter(f"""
            FROM {self.image} AS base
            RUN {self.mirror.install}
            RUN xbps-install -ySu xbps bash shadow sudo
            CMD ["/bin/bash"]
            {self._install_user()}
            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base as build
            RUN xbps-install -ySu xbps git bash util-linux {" ".join(dependencies)}

            FROM base AS test
            RUN xbps-install -ySu xbps {" ".join(self.test_dependencies)}
        """)

    def template(self):
        out = f"# Template file for '{self.package_name}'\n"
        quote = lambda x: f'"{x}"'
        out += _shell.variables(
            pkgname=self.package_name,
            version=self.project.version,
            revision=1,
            build_style="python3-pep517",
            hostmakedepends=quote(" ".join(self.build_dependencies)),
            depends=quote(" ".join(self.dependencies)),
            checkdepends=quote(" ".join(self.test_dependencies)),
            short_desc=quote(self.project.description),
            maintainer=quote(self.project.maintainer_slug),
            license=quote(", ".join(self.project.license_names)),
            homepage=quote(self.project.url),
            distfiles=quote(self.project.source_url.format(version="${version}").replace("https://pypi.io/packages/source/", "${PYPI_SITE}/")),
            checksum=hashlib.sha256(self.project.tar()).hexdigest(),
        )
        out += self._formatter("post_install() {")
        for license in self.project.licenses:
            out += self._formatter("vlicense " + shlex.quote(license), 1)
        if self.icons:
            out += self._formatter("for size in 16 32 48 256; do", 1)
            for (source, dest) in self.icons:
                out += self._formatter(f"""
                    convert -background "#00000000" -size $size \\
                        "{source}" "{dest}.png"
                    vmkdir usr/share/icons/hicolor/${{size}}x${{size}}/apps
                    vcopy "{dest}.png" usr/share/icons/hicolor/${{size}}x${{size}}/apps/
                """, 2)
            out += self._formatter("done", 1)
        for id in self.project.desktop_entry_points:
            out += self._formatter(f"vinstall .polycotylus/{id}.desktop 644 /usr/share/applications", 1)

        out += "}\n"
        return out

    def inject_source(self):
        from urllib.parse import urlparse
        from pathlib import PurePosixPath

        url = self.project.source_url.format(version=self.project.version)
        name = PurePosixPath(urlparse(url).path).name
        path = self.distro_root / f"hostdir/sources/{self.package_name}-{self.project.version}/{name}"
        path.parent.mkdir(parents=True)
        path.write_bytes(self.project.tar())

    def generate(self):
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root)
        self.distro_root.parent.mkdir(exist_ok=True, parents=True)
        shutil.copytree(self.void_packages_repo(), self.distro_root, symlinks=True)
        (self.distro_root / "Dockerfile").write_text(self.dockerfile())
        self.project.write_desktop_files()
        self.distro_root.chmod(0o777)
        self.project.write_gitignore()
        package_root = self.distro_root / "srcpkgs" / self.package_name
        package_root.mkdir(parents=True)
        (package_root / "template").write_text(self.template())
        self.inject_source()

    @mirror.decorate
    def build(self):
        try:
            for command in [["./xbps-src", "-1", "binary-bootstrap"],
                            ["./xbps-src", "-1", "pkg", self.package_name]]:
                _docker.run(self.build_builder_image(), command,
                            "--privileged", root=False,
                            volumes=[(self.distro_root, "/io")], tty=True)
        except _docker.Error as ex:
            # If a dependency has been updated since the last sync of the
            # void-packages repo, xbps-src will, by default, build that
            # dependency from source which could take ages. The -1 flags above
            # make xbps-src raise an error instead if this happens. If that
            # error is triggered, catch it, resyncronise the cached
            # void-packages clone then start the build again.
            if not re.search("=> ERROR: .* not found: -1 passed: instructed not to build",
                             ex.output, flags=re.M):  # pragma: no cover
                raise
            shutil.rmtree(self.void_packages_repo())
            self.generate()
            return self.build()

        name = f"{self.package_name}-{self.project.version}_1.{platform.machine()}-musl.xbps"
        return {"main": self.distro_root / "hostdir/binpkgs" / name}

    @mirror.decorate
    def test(self, package):
        base = self.build_test_image()
        volumes = [(package.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        return _docker.run(base, f"""
            sudo xbps-install -ySu -R /pkg/ xbps {self.package_name}
            {self.project.test_command}
        """, volumes=volumes, tty=True, root=False)

    @classmethod
    def void_packages_repo(cls):
        """Clone/cache Void Linux's package build recipes repo."""
        # Void Linux's package building tools are unhelpfully part of the same
        # repo that houses the build scripts for every package on their
        # repositories so to build anything, we need to clone everything.
        # Currently, a shallow clone is about 12MB whereas a conventional clone
        # is 558MB.
        cache = cache_root / "void-packages"
        with contextlib.suppress(FileNotFoundError):
            if time.time() - cache.stat().st_mtime < 7 * 24 * 60 * 60:
                return cache
            else:
                # Updating a shallow git clone is so inefficient that it's
                # quicker to start from scratch each time.
                shutil.rmtree(cache)
        command = ["git", "clone", "--depth=1", "--progress",
                   "https://github.com/void-linux/void-packages", str(cache)]
        status, output = _docker._tee_run(command, _docker._verbosity())
        if status:  # pragma: no cover
            raise RuntimeError(
                f"Git command:\n    {shlex.join(command)}\n"
                "returned an error:\n" + textwrap.indent(output, "    "))
        cls._void_packages_inject_mirror(cache)
        return cache

    @staticmethod
    def _void_packages_inject_mirror(root):
        for path in (root / "etc/xbps.d").glob("repos-*"):
            path.write_bytes(path.read_bytes().replace(
                b"https://repo-default.voidlinux.org", b"http://0.0.0.0:8902"))


if __name__ == "__main__":
    self = Void(Project.from_root("."))
    self.generate()
    self.test(self.build()["main"])
