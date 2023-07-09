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

from polycotylus import _misc, _docker
from polycotylus._mirror import cache_root
from polycotylus._base import BaseDistribution, _deduplicate


class Void(BaseDistribution):
    python_prefix = "/usr"
    name = "void"
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
        "aarch64": "aarch64",
        "armv6l": "arm",
        "armv7l": "arm",
    }
    libc = "glibc"
    libc_tag = ""

    @_misc.classproperty
    def image(self, cls):
        architecture = "x86_64" if self is None else self.architecture
        return f"ghcr.io/void-linux/void-linux:latest-mini-{architecture}{cls.libc_tag}"

    def _build_image(self, target):
        base_packages = [re.sub("^chroot-", "", i) for i in self.build_base_packages() if i != "base-files"]
        with self.mirror:
            return _docker.build(
                self.distro_root / "Dockerfile", self.project.root,
                f"--build-arg=tag=latest-mini-{self.architecture}{self.libc_tag}",
                f"--build-arg=base_packages={shlex.join(base_packages)}",
                target=target, architecture=self.docker_architecture)

    def build_builder_image(self):
        return self._build_image("build")

    def build_test_image(self):
        return self._build_image("test")

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
        cls._build_base_packages = re.findall(r"^([^>]+)", _read("base"), flags=re.M)
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
        dependencies = _deduplicate(
            self.dependencies + self.build_dependencies
            + self.test_dependencies)
        return self._formatter(f"""
            ARG tag
            FROM ghcr.io/void-linux/void-linux:${{tag}} AS base
            RUN {self.mirror.install}
            RUN rm -f /etc/xbps.d/noextract.conf
            RUN xbps-install -ySu xbps bash shadow sudo
            CMD ["/bin/bash"]
            {self._install_user()}
            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base as build
            ARG base_packages
            RUN mkdir -p /io/srcpkgs/{self.package_name} /io/hostdir/binpkgs /io/hostdir/sources && chown -R user /io
            ENV GIT_DISCOVERY_ACROSS_FILESYSTEM 1
            ENV SOURCE_EPOCH 0
            RUN xbps-install -ySu xbps git bash util-linux ${{base_packages}} {shlex.join(dependencies)}

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
        self.distro_root.mkdir(exist_ok=True, parents=True)
        _misc.unix_write(self.distro_root / "Dockerfile", self.dockerfile())
        self.project.write_desktop_files()
        self.distro_root.chmod(0o777)
        self.project.write_gitignore()
        package_root = self.distro_root / "srcpkgs" / self.package_name
        package_root.mkdir(parents=True, exist_ok=True)
        _misc.unix_write(package_root / "template", self.template())

        (self.distro_root / self.libc).mkdir(exist_ok=True)
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
            (self.distro_root / "hostdir/sources", "/io/hostdir/sources"),
        ]
        mirror_url = "http://0.0.0.0:8902" if platform.system() == "Linux" else "http://host.docker.internal:8902"
        with self.mirror:
            container = _docker.run(self.build_builder_image(), f"""
                git config --global --add safe.directory /io
                git config core.symlinks true
                git checkout {self._void_packages_head()} -- .
                sed -r -i 's|https://repo-default.voidlinux.org|{mirror_url}|g' etc/xbps.d/repos-*
                echo 'XBPS_CHROOT_CMD=ethereal\\nXBPS_ALLOW_CHROOT_BREAKOUT=yes' > etc/conf
                ln -s / masterdir
                ./xbps-src -1 pkg {self.package_name}
            """, "--privileged", tty=True, post_mortem=True, volumes=volumes,
                                    architecture=self.docker_architecture)
        name = f"{self.package_name}-{self.project.version}_1.{self.architecture}{self.libc_tag}.xbps"
        (self.distro_root / self.libc / name).write_bytes(container.file(f"/io/hostdir/binpkgs/{name}"))
        repodata = f"{self.architecture}{self.libc_tag}-repodata"
        (self.distro_root / self.libc / repodata).write_bytes(container.file(f"/io/hostdir/binpkgs/{repodata}"))
        return {"main": self.distro_root / self.libc / name}

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
        (replacing aarch64 with the current architecture and deleting -musl if
        building for glibc)."""
        url = f"https://build.voidlinux.org/json/builders/{self.architecture}{self.libc_tag}_builder/builds?"
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


class VoidMusl(Void):
    libc = "musl"
    libc_tag = "-musl"


VoidGlibc = Void
