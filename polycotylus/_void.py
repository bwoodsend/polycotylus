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
from pathlib import Path, PurePosixPath

from polycotylus import _misc, _docker, _exceptions
from polycotylus._mirror import cache_root
from polycotylus._base import BaseDistribution, _deduplicate


class Void(BaseDistribution):
    name = "void"
    python_extras = {
        "tkinter": ["python3-tkinter"],
    }
    _packages = {
        "python": "python3",
        "image-conversion": ["ImageMagick"],
        "svg-conversion": ["ImageMagick", "librsvg"],
        "xvfb-run": "xvfb-run util-linux",
        "font": "dejavu-fonts-ttf",
    }
    _formatter = _misc.Formatter()
    supported_architectures = {
        "x86_64": "x86_64",
        "aarch64": "aarch64",
        "armv6l": "arm",
        "armv7l": "arm",
    }
    libc = "glibc"
    libc_tag = ""
    signature_property = "private_key"

    @_misc.classproperty
    def base_image(self, cls):
        architecture = cls.preferred_architecture if self is None else self.architecture
        return f"ghcr.io/void-linux/void-linux:latest-mini-{architecture}{cls.libc_tag}"

    @_misc.classproperty
    def tag(_, cls):
        return cls.libc

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
            container = _docker.run(cls.base_image, f"""
                {cls.mirror.install_command}
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
            RUN {self.mirror.install_command}
            RUN rm -f /etc/xbps.d/noextract.conf
            RUN xbps-install -ySu xbps bash shadow sudo
            CMD ["/bin/bash"]
            {self._install_user()}
            RUN mkdir /io && chown user /io
            WORKDIR /io

            FROM base AS build
            ARG base_packages
            RUN mkdir -p /io/srcpkgs/{self.package_name} /io/hostdir/binpkgs /io/hostdir/sources && chown -R user /io
            ENV GIT_DISCOVERY_ACROSS_FILESYSTEM=1
            ENV SOURCE_EPOCH=0
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
        if self.private_key:
            volumes.append((str(self.private_key), f"/key/{self.private_key.name}"))

        mirror_url = "http://localhost:8902" if platform.system() == "Linux" else "http://host.docker.internal:8902"
        script = self._formatter(f"""
            git config --global --add safe.directory /io
            git config core.symlinks true
            git checkout {self._void_packages_head()} -- .
            sed -r -i 's|https://repo-default.voidlinux.org|{mirror_url}|g' etc/xbps.d/repos-*
            echo 'XBPS_CHROOT_CMD=ethereal\\nXBPS_ALLOW_CHROOT_BREAKOUT=yes' > etc/conf
            ln -s / masterdir
            ./xbps-src -1 pkg {self.package_name}
        """)
        if self.private_key:
            script += self._formatter(f"""
                xbps-rindex --sign --signedby "{self.project.maintainer}" --privkey /key/{self.private_key.name} $PWD/hostdir/binpkgs
                xbps-rindex --sign-pkg --privkey /key/{self.private_key.name} $PWD/hostdir/binpkgs/*.xbps
            """)
        with self.mirror:
            container = _docker.run(self.build_builder_image(), script, "--privileged",
                                    tty=True, post_mortem=True, volumes=volumes,
                                    architecture=self.docker_architecture,
                                    interactive=bool(self.private_key))
        name = f"{self.package_name}-{self.project.version}_1.{self.architecture}{self.libc_tag}.xbps"
        (self.distro_root / self.libc / name).write_bytes(container.file(f"/io/hostdir/binpkgs/{name}"))
        repodata = f"{self.architecture}{self.libc_tag}-repodata"
        (self.distro_root / self.libc / repodata).write_bytes(container.file(f"/io/hostdir/binpkgs/{repodata}"))
        artifact = self._make_artifact(self.distro_root / self.libc / name, "main", None)
        if self.private_key:
            signature = self.distro_root / self.libc / (name + ".sig2")
            signature.write_bytes(container.file(f"/io/hostdir/binpkgs/{signature.name}"))
            artifact.signature_path = signature
        return {"main": artifact}

    def test(self, package):
        base = self.build_test_image()
        volumes = [(package.path.parent, "/pkg")]
        for path in self.project.test_files:
            volumes.append((self.project.root / path, f"/io/{path}"))
        with self.mirror:
            container = _docker.run(base, f"""
                {"yes | " if self.private_key else ""} sudo xbps-install -ySu -R /pkg/ xbps {self.package_name}
                {self.project.test_command.evaluate()}
            """, volumes=volumes, tty=True, root=False, post_mortem=True,
                architecture=self.docker_architecture)
        if self.private_key:
            with container["/var/db/xbps/keys/"] as tar:
                files = [i for i in tar.getmembers() if i.name.endswith(".plist")]
                assert len(files) == 3, repr(files)
                path = max(files, key=lambda x: x.mtime)
                name = PurePosixPath(path.name).name
                with tar.extractfile(path) as f:
                    contents = f.read()
            (self.distro_root / name).write_bytes(contents)
        return container

    @lru_cache()
    def _void_packages_head(self):
        """Fetch the commit SHA1 corresponding to the latest completed build
        from https://build.voidlinux.org/builders/aarch64-musl_builder
        (replacing aarch64 with the current architecture and deleting -musl if
        building for glibc)."""
        url = f"https://build.voidlinux.org/api/v2/builders/{self.architecture}{self.libc_tag}/builds"
        with urlopen(url) as response:
            builds = json.loads(response.read())["builds"]
        build_id = max(
            (x for x in builds if x["complete"] and x["state_string"] == "build successful"),
            key=lambda x: x["started_at"])["buildid"]

        with urlopen(f"https://build.voidlinux.org/api/v2/builds/{build_id}/properties") as response:
            build = json.loads(response.read())
        revision = build["properties"][0]["revision"][0]
        assert re.fullmatch("[a-f0-9]{40}", revision)
        return revision

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

    @property
    def private_key(self):
        return self._private_key

    @private_key.setter
    def private_key(self, path):
        if path is None:
            self._private_key = None
            return
        private_key = Path(path)
        try:
            with open(private_key, "rb") as f:
                header = f.readline()
                if not re.match(b"-----BEGIN( RSA)?( ENCRYPTED)? PRIVATE KEY-----", header):
                    raise _exceptions.PolycotylusUsageError(_exceptions._unravel(f"""
                        Invalid Void signing private key file "{private_key}".
                        Create a signing certificate using one of:

                            openssl genrsa -out privkey.pem 4096        # passwordless
                            openssl genrsa -des3 -out privkey.pem 4096  # password required
                    """))
        except OSError as ex:
            raise _exceptions.PolycotylusUsageError(
                f'Getting an {type(ex).__name__}() whilst accessing private key file "{private_key}"')
        self._private_key = private_key


class VoidMusl(Void):
    libc = "musl"
    libc_tag = "-musl"


VoidGlibc = Void
