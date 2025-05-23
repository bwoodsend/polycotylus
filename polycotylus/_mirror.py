import os
import platform
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
import shutil
import re
import threading
import time
from functools import wraps
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import email.utils
import contextlib
import collections
import json

from polycotylus import _docker
from polycotylus._docker import cache_root


class CachedMirror:
    """A mirror of a Linux distribution's package repository which caches
    downloads persistently.
    """

    def __init__(self, base_url, base_dir, index_patterns, ignore_patterns,
                 port, install_command, last_sync_time, package_version_pattern="(.+)()()",
                 handler=None):
        """
        Args:
            base_url:
                The URL of the root of the repository index. This can usually be
                found in an /etc/{package manager}/mirrors or similar file.
            base_dir:
                A persistent directory to store cached files in.
            index_patterns:
                A list of globs which indicate repository index files.
            ignore_patterns:
                A list of globs which indicate files which should always return
                404 errors. This can usually be left empty.
            port:
                An integer port number. Any number not already used will do.
            install_command:
                A shell command which replaces the distribution's list of
                mirrors with this mirror.
            last_sync_time:
                A sequence of functions, each taking a RequestHandler()
                instance as an argument and returning an integer timestamp
                corresponding to the time the requested file was last updated.
            package_version_pattern:
                A regex to detect the version component of a package's filename.
            handler:
                A subclass of RequestHandler() which handles a single request.

        """
        self._base_url = base_url
        self.base_dir = Path(base_dir)
        self.index_patterns = index_patterns
        self.ignore_patterns = ignore_patterns
        self.port = port
        self.handler = handler or RequestHandler
        if platform.system() in ("Darwin", "Windows"):  # pragma: no cover
            # Docker's --network=host option doesn't work on macOS or Windows.
            # https://github.com/docker/for-mac/issues/1031
            install_command = install_command.replace("localhost", "host.docker.internal")
        self.install_command = install_command
        self._lock = threading.Lock()
        self._listeners = 0
        self.last_sync_time = last_sync_time
        self.package_version_pattern = package_version_pattern
        self._in_progress = {}
        self.verbose = False

    def with_(self, **kwargs):
        parameters = dict(
            base_url=self.base_url, base_dir=self.base_dir,
            index_patterns=self.index_patterns,
            ignore_patterns=self.ignore_patterns, port=self.port,
            install_command=self.install_command, last_sync_time=self.last_sync_time,
            package_version_pattern=self.package_version_pattern,
            handler=self.handler,
        )
        parameters.update(kwargs)
        return type(self)(**parameters)

    @property
    def base_url(self):
        if callable(self._base_url):
            self._base_url = self._base_url()
        return self._base_url.strip("/")

    def local_path(self, server_path):
        # Some packages may contain colons (:) in their filenames. The colon is
        # a prohibited character on Windows. Replace it with a nearly identical
        # unicode equivalent.
        server_path = server_path.lstrip("/").replace(":", "\uA789")
        return self.base_dir / server_path

    def serve(self):
        """Enable this mirror and block until killed (via Ctrl+C)."""
        with self:
            print(f"http://localhost:{self.port}", "=>", self.base_url)
            print(f"Install via:\n{self.install_command}")
            self.verbose = True
            with contextlib.suppress(KeyboardInterrupt):
                while True:
                    time.sleep(1)
            self.verbose = False

    def __enter__(self):
        with self._lock:
            # If multiple enters, avoid port competition by ensuring that there
            # is only one server. Keep a counter of how many
            # __enter__()/__exit__() there have been.
            if self._listeners:
                self._listeners += 1
                return
        self.base_url
        self.base_dir.mkdir(parents=True, exist_ok=True)
        handler = type("Handler", (self.handler,), {"parent": self})
        try:
            self._httpd = ThreadingHTTPServer(("", self.port), handler)
        except OSError as ex:
            if ex.errno not in {98, 48}:  # pragma: no cover
                raise
            from polycotylus._exceptions import PolycotylusUsageError, _unravel
            raise PolycotylusUsageError(_unravel("""
                Polycotylus does not support concurrent usage for the same Linux
                distribution.
            """)) from None
        self._prune()
        try:
            partial_downloads = json.loads((self.base_dir / "partial-downloads.json").read_bytes())
        except FileNotFoundError:
            pass
        else:
            for file in partial_downloads:
                with contextlib.suppress(FileNotFoundError):
                    self.local_path(file).unlink()
            (self.base_dir / "partial-downloads.json").unlink()

        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._premature_abort = False
        thread.start()
        self._thread = thread
        self._listeners = 1

    def __exit__(self, exc_type, exc_value, traceback):
        with self._lock:
            self._listeners -= 1
            if self._listeners:
                return

        if isinstance(exc_value, KeyboardInterrupt):
            with self._lock:
                self._premature_abort = True
                for path in self._in_progress:
                    if response := getattr(self._in_progress[path], "_upstream", None):  # pragma: no branch
                        response.close()

        # Wait until all running downloads are complete to avoid competing over
        # ports if this mirror is re-enabled soon after.
        while self._in_progress:  # pragma: no cover
            time.sleep(.1)
        self._httpd.shutdown()
        self._httpd.socket.close()
        del self._httpd

    def decorate(self, f):
        """@decorate a function requiring the mirror set up so that this mirror
        is started/stopped whenever the function is called/exits."""

        @wraps(f)
        def wrapped(*args, **kwargs):
            with self:
                return f(*args, **kwargs)

        return wrapped

    def _prune(self, root=None):
        """Delete all but the latest version of each cached package."""
        root = root or str(self.base_dir)
        caches = collections.defaultdict(list)
        file_re = re.compile(self.package_version_pattern)
        version_re = re.compile(r"(\d+)|(\D+)")

        for entry in os.scandir(root):
            if entry.is_dir():
                self._prune(entry.path)
            elif match := file_re.fullmatch(entry.name):
                caches[(match[1], match[3])].append((entry.name, match[2]))
        for (key, file_versions) in caches.items():
            if len(file_versions) > 1:
                file_versions.sort(key=lambda x: tuple(j or int(i)
                                                       for (i, j) in version_re.findall(x[1])))
                for (name, version) in file_versions[:-1]:
                    os.remove(os.path.join(root, name))


class RequestHandler(BaseHTTPRequestHandler):
    """Handle a single request from a package manager."""
    parent: CachedMirror
    _upstream = None

    @property
    def upstream_url(self):
        return self.parent.base_url + self.path

    @property
    def upstream(self):
        """An open response from the original repository archive."""
        if self._upstream:
            return self._upstream
        headers = {}
        for header in ("Accept-Encoding",):
            if header in self.headers:
                headers[header] = self.headers[header]
        self._upstream = urlopen(Request(self.upstream_url, headers=headers))
        return self._upstream

    @property
    def cache(self):
        """The file path where this request should be cached."""
        # Some packages may contain colons (:) in their filenames. The colon is
        # a prohibited character on Windows. Replace it with a nearly identical
        # unicode equivalent.
        return self.parent.local_path(self.path)

    def do_GET(self):
        if any(fnmatch(self.path, i) for i in self.parent.ignore_patterns):
            self.send_response(404)
            self.end_headers()
            return
        if ".." in self.path.split("/"):
            self.send_response(404)
            self.end_headers()
            return

        use_cache = True
        if not self.cache.is_file():
            use_cache = False
            try:
                # File is not cached. Check upstream.
                self.upstream
            except HTTPError as ex:
                # File doesn't exist upstream either. Forward the error.
                self.send_response(ex.code)
                self.end_headers()
                return
            # Don't cache FTP index pages (e.g. /some/directory/) since the
            # upstream server will redirect /some/directory/ to
            # /some/directory/index.html and that would create a local cache
            # file called $cache/some/directory where the directory
            # $cache/some/directory/ is supposed to be.
            if self.upstream.headers["Content-Type"] and \
                    "text/html" in self.upstream.headers["Content-Type"].split(";"):
                with self.upstream:
                    self.send_response(HTTPStatus.OK)
                    # Forward any header web browsers needs to interpret the
                    # potentially compressed HTML response.
                    for header in ["Content-Encoding", "Content-Type",
                                   "Content-Length"]:
                        if value := self.upstream.headers[header]:
                            self.send_header(header, value)
                    self.end_headers()
                    if self.command == "GET":
                        shutil.copyfileobj(self.upstream, self.wfile)
                return

        elif any(fnmatch(self.cache.name, i) for i in self.parent.index_patterns):
            # File is cached but is one which may be updated in-place upstream
            # without changing its name. Determine if it needs re-downloading,
            timestamp = self.cache.stat().st_mtime
            if any(last_update(self) < timestamp for last_update in self.parent.last_sync_time):
                use_cache = True
                os.utime(self.cache)
            else:
                self.cache.unlink()
                use_cache = False

        self.send_response(HTTPStatus.OK)
        with self.parent._lock:
            if self.command != "HEAD":
                if self.path not in self.parent._in_progress and not use_cache:
                    self._thread = threading.Thread(target=self._download)
                    self.parent._in_progress[self.path] = self
                    with open(self.parent.base_dir / "partial-downloads.json", "w") as f:
                        json.dump(sorted(self.parent._in_progress), f)
                    self._thread.start()

            if self.path in self.parent._in_progress \
                    or (self.command == "HEAD" and not use_cache):
                method = self._in_progress_send
                for header in ["Content-Length", "Transfer-Encoding"]:
                    if value := self.upstream.headers[header]:
                        self.send_header(header, value)
                self.end_headers()
                if self.command == "HEAD":
                    self._upstream and self._upstream.close()
                    return
            else:
                method = self._cache_send
                self._upstream and self._upstream.close()

        method()

    do_HEAD = do_GET

    def _cache_send(self):
        """Send a file from cache to the client."""
        cache = self.cache
        if range := re.match(r"bytes=(\d*)-(\d*)", self.headers["Range"] or ""):
            start = int(range[1] or 0)
            length = int(range[2] or self.cache.stat().st_size) - start
            self.send_header("Content-Length", str(length))
        else:
            length = None
            self.send_header("Content-Length", str(self.cache.stat().st_size))
        self.end_headers()
        self._upstream and self._upstream.close()
        if self.command == "HEAD":
            return

        with open(cache, "rb") as f:
            if range:
                f.seek(start)
            shutil.copyfileobj(f, self.wfile, length)

    def _download(self):
        cache = self.cache
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.upstream:
                with open(cache, "wb") as f:
                    shutil.copyfileobj(self.upstream, f)
        except:  # pragma: no cover
            with contextlib.suppress(FileNotFoundError):
                cache.unlink()
            raise
        finally:
            with self.parent._lock:
                del self.parent._in_progress[self.path]
                if not self.parent._premature_abort:
                    with open(self.parent.base_dir / "partial-downloads.json", "w") as f:
                        json.dump(sorted(self.parent._in_progress), f)

    def _in_progress_send(self):
        """Send a file from the cache whilst the cache is being written."""
        for header in ["Content-Length", "Transfer-Encoding"]:
            if value := self.upstream.headers[header]:
                self.send_header(header, value)
        while not self.cache.exists():
            time.sleep(0.1)
        with open(self.cache, "rb") as f:
            try:
                while self.path in self.parent._in_progress:
                    shutil.copyfileobj(f, self.wfile)
                    time.sleep(0.1)
                shutil.copyfileobj(f, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                return

    def log_message(self, format, *args):
        if self.parent.verbose:
            super().log_message(format, *args)


def _alpine_sync_time(self):
    # Alpine repositories are only updated at most, once per hour and always on
    # the hour (i.e. at xx:00:00).
    return time.time() // 3600 * 3600


def _use_last_modified_header(self: RequestHandler):
    latest = self.upstream.headers["Last-Modified"]
    latest = email.utils.parsedate_to_datetime(latest)
    return latest.timestamp()


def _manjaro_preferred_mirror():
    with contextlib.suppress(Exception):
        url = (cache_root / "manjaro-mirror").read_text("utf-8")
        urlopen(Request(url, method="HEAD")).close()
        return url

    container = _docker.run("manjarolinux/base", "pacman-mirrors --geoip",
                            tty=True)
    mirrorlist = container.file("/etc/pacman.d/mirrorlist").decode()
    mirrors = re.findall("^Server = (.*?)/(?:arm-)?stable", mirrorlist, flags=re.M)
    assert mirrors
    for url in mirrors:  # pragma: no branch
        with contextlib.suppress(HTTPError):
            urlopen(Request(url, method="HEAD")).close()
            (cache_root / "manjaro-mirror").write_text(url, "utf-8")
            return url


class UbuntuRequestHandler(RequestHandler):
    # Ubuntu's package repositories are split across multiple subnets. e.g.
    # http://archive.ubuntu.com/ubuntu/ vs http://ports.ubuntu.com/ubuntu-ports/
    # To avoid needing a separate mirror for each subdomain, redirect the Docker
    # containers to look at http://localhost:port/subnet/path then the mirror
    # reverses the change when fetching an upstream file.
    @property
    def upstream_url(self):
        root, subnet, *path = PurePosixPath(self.path).parts
        assert root == "/"
        return f"http://{subnet}.ubuntu.com/{PurePosixPath(*path)}"


mirrors = {}
mirrors["arch"] = CachedMirror(
    "https://geo.mirror.pkgbuild.com/",
    cache_root / "arch",
    ["*.db", "*.files"],
    ["*.db.sig", "*.files.sig"],
    8900,
    "echo 'Server = http://localhost:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist && sed -i s/NoProgressBar/Color/ /etc/pacman.conf",
    (_use_last_modified_header,),
    r"(.+-)(?:\d+꞉)?([^-]+-\d+)(-[^-]+)",
)
mirrors["alpine"] = CachedMirror(
    "https://dl-cdn.alpinelinux.org/alpine/",
    cache_root / "alpine",
    ["APKINDEX.tar.gz"],
    [],
    8901,
    r"sed -r -i 's ^.*/(v\d+\.\d+|edge)/ http://localhost:8901/\1/ g' /etc/apk/repositories",
    (_alpine_sync_time, _use_last_modified_header),
    r"(.+-)([^-]+-r\d+)(\.apk)",
)
mirrors["void"] = CachedMirror(
    "https://repo-default.voidlinux.org/",
    cache_root / "void",
    ["*-repodata"],
    [],
    8902,
    r"sed 's|https://repo-default.voidlinux.org|http://localhost:8902|g' /usr/share/xbps.d/00-repository-main.conf > /etc/xbps.d/00-repository-main.conf "
    r"&& sed -E 's|https://repo-default.voidlinux.org/(.*)|http://localhost:8902/\1/bootstrap|g' /usr/share/xbps.d/00-repository-main.conf > /etc/xbps.d/10-repository-bootstrap.conf",
    (_use_last_modified_header,),
    r"(.+-)([^_-]+_\d+)(\..+)",
)
mirrors["manjaro"] = mirrors["arch"].with_(
    base_url=_manjaro_preferred_mirror,
    base_dir=cache_root / "manjaro",
    port=8903,
    install_command="if grep -q /arm-stable/ /etc/pacman.d/mirrorlist ; then echo 'Server = http://localhost:8903/arm-stable/$repo/$arch' > /etc/pacman.d/mirrorlist; else echo 'Server = http://localhost:8903/stable/$repo/$arch' > /etc/pacman.d/mirrorlist; fi; sed -i 's/#Color/Color/' /etc/pacman.conf",
)
mirrors["debian13"] = CachedMirror(
    "http://deb.debian.org/",
    cache_root / "debian13",
    ["InRelease"],
    [],
    8905,
    r"sed -i 's|http://deb.debian.org/|http://localhost:8905/|g' /etc/apt/sources.list.d/debian.sources",
    (_use_last_modified_header,),
    r"(.+_)([^-]+-\d+)(.+)",
)
mirrors["ubuntu2304"] = mirrors["debian13"].with_(
    base_url="http://archive.ubuntu.com/ubuntu/",
    base_dir=cache_root / "ubuntu2304",
    port=8906,
    install_command=r"sed -i -E 's|http://(.*).ubuntu.com/|http://localhost:8906/\1/|g' /etc/apt/sources.list",
    handler=UbuntuRequestHandler,
)
mirrors["ubuntu2310"] = mirrors["ubuntu2304"].with_(
    base_dir=cache_root / "ubuntu2310",
)
mirrors["ubuntu2404"] = mirrors["ubuntu2304"].with_(
    base_dir=cache_root / "ubuntu2404",
    install_command=r"sed -i -E 's|http://(.*).ubuntu.com/|http://localhost:8906/\1/|g' /etc/apt/sources.list.d/ubuntu.sources",
)
mirrors["ubuntu2410"] = mirrors["ubuntu2404"].with_(
    base_dir=cache_root / "ubuntu2410",
)
mirrors["ubuntu2504"] = mirrors["ubuntu2404"].with_(
    base_dir=cache_root / "ubuntu2504",
)
mirrors["ubuntu2510"] = mirrors["ubuntu2404"].with_(
    base_dir=cache_root / "ubuntu2510",
)


if __name__ == "__main__":
    if len(sys.argv) > 2:
        import subprocess
        with mirrors[sys.argv[1]]:
            subprocess.run(sys.argv[2:])
    else:
        mirrors[sys.argv[1]].serve()
