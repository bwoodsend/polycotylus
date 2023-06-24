"""
https://github.com/void-linux/void-packages/blob/master/Manual.md
"""
import re
from functools import lru_cache
import hashlib
import platform
import shlex
from urllib.request import urlopen
import json
import shutil
import contextlib

from polycotylus import _misc, _docker
from polycotylus._mirror import cache_root
from polycotylus._base import BaseDistribution, _deduplicate


class Void(BaseDistribution):
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
    _formatter = _misc.Formatter()
    supported_architectures = {
        "x86_64": "x86_64",
        # "aarch64": "aarch64",  # unshare barfs out on these. I don't
        # "armv6l": "arm/v6",    # understand why. Void on non-x86_64 seems
        # "armv7l": "arm/v7",    # unpopular anyway.
    }

    @_misc.classproperty
    def image(self, _):
        architecture = "x86_64" if self is None else self.architecture
        return f"ghcr.io/void-linux/void-linux:latest-mini-{architecture}-musl"

    @classmethod
    @lru_cache()
    def _package_manager_queries(cls):
        with cls.mirror:
            container = _docker.run(cls.image, f"""
                {cls.mirror.install}
                xbps-install -ySu xbps
                xbps-query -Rs '' > /all
                xbps-query -Rx base-chroot > /base
                xbps-query -R python3 > /python-info
            """, tty=True)
        _read = lambda path: container.file(path).decode()
        cls._available_packages = re.findall(r"\[-\] ([^ ]+)-[^ ]", _read("/all"))
        cls._build_base_packages = re.findall(r"^([^>]+)", _read("base"))
        cls._python_version = re.search("pkgver: python3-([^_]+)", _read("/python-info"))[1]

    @property
    def build_dependencies(self):
        out = super().build_dependencies
        out.remove(self.python_package("pip"))
        # Build dependencies aren't allowed any version constraints.
        out = [re.split(" *[<>~=]", i)[0] for i in out]
        return out

    @classmethod
    def fix_package_name(cls, name):
        return name

    @classmethod
    def python_package_convention(cls, pypi_name):
        wheel_packaged_name = re.sub("-+", "-", pypi_name.replace("_", "-"))
        return "python3-" + wheel_packaged_name

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
            RUN mkdir -p /io/srcpkgs/{self.package_name} /io/hostdir/binpkgs /io/hostdir/sources && chown -R user /io
            RUN xbps-install -ySu xbps git bash util-linux {shlex.join(dependencies)}

            FROM base AS test
            RUN xbps-install -ySu xbps {shlex.join(self.test_dependencies)}
        """)

    def template(self):
        out = f"# Template file for '{self.package_name}'\n"
        quote = lambda x: f'"{x}"'
        out += _misc.variables(
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
        if self.project.setuptools_scm:
            out += self._formatter("""
                export SETUPTOOLS_SCM_PRETEND_VERSION="${version}"
            """)
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
            if any(source.endswith(".svg") for (source, _) in self.icons):
                out += self._formatter("vmkdir usr/share/icons/hicolor/scalable/apps")
                for (source, dest) in self.icons:
                    if source.endswith(".svg"):  # pragma: no branch
                        out += self._formatter(f'vcopy "{source}" usr/share/icons/hicolor/scalable/apps/{dest}.svg')
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
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.project.tar())

    def generate(self):
        with contextlib.suppress(FileNotFoundError):
            shutil.rmtree(self.distro_root / "dist")
        self.distro_root.mkdir(exist_ok=True, parents=True)
        _misc.unix_write(self.distro_root / "Dockerfile", self.dockerfile())
        self.project.write_desktop_files()
        self.distro_root.chmod(0o777)
        self.project.write_gitignore()
        package_root = self.distro_root / "srcpkgs" / self.package_name
        package_root.mkdir(parents=True, exist_ok=True)
        _misc.unix_write(package_root / "template", self.template())

        (self.distro_root / "dist").mkdir(exist_ok=True)
        self.inject_source()

    def build(self):
        # To make things awkward, the void-packages repo in which everything
        # must be built contains filenames with ':' in them meaning that git
        # checkout/clone will fail on Windows where ':' is an illegal character.
        # To work around this, we need to do some elaborate mounting so that the
        # offending file paths exist in the docker container only:
        #  - Fetch (but do not checkout to) the git commit we need outside the container
        #  - Mount the .git directory into the docker container
        #  - Mount the template file, source tarball and build output directories
        #    to somewhere on the host
        #  - Checkout the working tree inside the container
        #  - Run the build
        volumes = [
            (self.void_packages_repo() / ".git", "/io/.git"),
            (self.distro_root / "srcpkgs" / self.package_name, f"/io/srcpkgs/{self.package_name}"),
            (self.distro_root / "dist", "/io/hostdir/binpkgs"),
            (self.distro_root / "hostdir/sources", "/io/hostdir/sources"),
        ]
        mirror_url = "http://0.0.0.0:8902" if platform.system() == "Linux" else "http://host.docker.internal:8902"
        with self.mirror:
            _docker.run(self.build_builder_image(), f"""
                git config --global --add safe.directory /io
                git config core.symlinks true
                git checkout {self._void_packages_head()} -- .
                sed -r -i 's|https://repo-default.voidlinux.org|{mirror_url}|g' etc/xbps.d/repos-*
                ./xbps-src -1 binary-bootstrap
                ./xbps-src -1 pkg {self.package_name}
            """, "--privileged", root=False, tty=True, post_mortem=True,
                        volumes=volumes, architecture=self.docker_architecture)
        name = f"{self.package_name}-{self.project.version}_1.{self.architecture}-musl.xbps"
        return {"main": self.distro_root / "dist" / name}

    def test(self, package):
        base = self.build_test_image()
        volumes = [(package.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        with self.mirror:
            return _docker.run(base, f"""
                sudo xbps-install -ySu -R /pkg/ xbps {self.package_name}
                {self.project.test_command}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                               architecture=self.docker_architecture)

    @lru_cache()
    def _void_packages_head(self):
        """Fetch the commit SHA1 corresponding to the latest completed build
        from https://build.voidlinux.org/builders/aarch64-musl_builder
        (replacing aarch64 with the current architecture)."""
        url = f"https://build.voidlinux.org/json/builders/{self.architecture}-musl_builder/builds?"
        for j in range(-1, -10, -3):  # pragma: no branch
            _url = url + "&".join(f"select={i}" for i in range(j, j - 3, -1))
            with urlopen(_url) as response:
                builds = json.loads(response.read())
            for j in map(str, range(j, j - 3, -1)):  # pragma: no branch
                if not builds[j].get("currentStep"):  # pragma: no branch
                    return builds[j]["sourceStamps"][0]["revision"]
        raise StopIteration  # pragma: no cover

    def void_packages_repo(self):
        """Clone/cache Void Linux's package build recipes repo."""
        # Void Linux's package building tools are unhelpfully part of the same
        # repo that houses the build scripts for every package on their
        # repositories so to build anything, we need to clone everything.
        # Currently, a shallow clone is about 12MB whereas a conventional clone
        # is 558MB.
        from subprocess import run, PIPE, STDOUT
        cache = cache_root / "void-packages"
        commit = self._void_packages_head()
        if not (cache / ".git").is_dir():  # pragma: no cover
            run(["git", "init", "-q", str(cache), "--initial-branch=master"],
                stderr=PIPE, check=True)
        p = run(["git", "-C", str(cache), "log", commit],
                stdout=PIPE, stderr=STDOUT)
        if p.returncode:  # pragma: no cover
            command = ["git", "-C", str(cache), "fetch", "--depth=1", "--progress",
                       "https://github.com/void-linux/void-packages", commit]
            run(command, stdout=None if _docker._verbosity() >= 2 else PIPE, check=True)

        return cache
