import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
from http.client import HTTPResponse
import shutil
import re
import threading
import time
from functools import wraps
from fnmatch import fnmatch
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

import appdirs

cache_root = Path(appdirs.user_cache_dir("polycotylus"))


class CachedMirror:
    """A mirror of a Linux distribution's package repository which caches
    downloads persistently.
    """

    def __init__(self, base_url, base_dir, index_patterns, ignore_patterns,
                 port, install, last_sync_time):
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
            install:
                A shell command which replaces the distribution's list of
                mirrors with this mirror.
            last_sync_time:
                A function, taking this CachedMirror() instance as an argument,
                which returns an integer timestamp corresponding to the time
                the repository was last updated. This is typically stored in a
                plain text fail at ${base_url}/last-sync.

        """
        self.base_url = base_url.strip("/")
        self.base_dir = Path(base_dir)
        self.index_patterns = index_patterns
        self.ignore_patterns = ignore_patterns
        self.port = port
        self.install = install
        self._lock = threading.Lock()
        self._listeners = 0
        self.last_sync_time = lambda: last_sync_time(self)
        self._in_progress = set()

    def serve(self):
        """Enable this mirror and block until killed (via Ctrl+C)."""
        with self:
            host = "localhost" if os.name == "nt" else "0.0.0.0"
            print("http://{}:{}".format(host, self.port))
            print(f"Install via:\n{self.install}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    def __enter__(self):
        with self._lock:
            # If multiple enters, avoid port competition by ensuring that there
            # is only one server. Keep a counter of how many
            # __enter__()/__exit__() there have been.
            if self._listeners:
                self._listeners += 1
                return
        handler = type("Handler", (RequestHandler,), {"parent": self})
        self._httpd = ThreadingHTTPServer(("", self.port), handler)
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()
        self._thread = thread
        self._listeners = 1

    def __exit__(self, *_):
        with self._lock:
            self._listeners -= 1
            if self._listeners:
                return
        # Wait until all running downloads are complete to avoid competing over
        # ports if this mirror is re-enabled soon after.
        while self._in_progress:
            time.sleep(.1)
        self._httpd.shutdown()
        del self._httpd

    def decorate(self, f):
        """@decorate a function requiring the mirror set up so that this mirror
        is started/stopped whenever the function is called/exits."""

        @wraps(f)
        def wrapped(*args, **kwargs):
            with self:
                return f(*args, **kwargs)

        return wrapped


class RequestHandler(BaseHTTPRequestHandler):
    """Handle a single request from a package manager."""
    parent: CachedMirror

    def do_HEAD(self):
        response = self._head()
        if isinstance(response, HTTPResponse):
            response.close()
        self.end_headers()

    def _head(self):
        """Triage an incoming request for a file.

        Returns:
            Either:
            - An open connection to the upstream repository if the request makes
              sense and isn't already cached.
            - A path to the local cache if this file is cache-able and already
              downloaded.
            - None if there are any errors.

        """
        path = self.cache
        if any(fnmatch(self.path, i) for i in self.parent.ignore_patterns):
            self.send_response(404)
            return
        if ".." in self.path.split("/"):
            self.send_response(404)
            return
        # File is cached - send the cache.
        if self.path in self.parent._in_progress or path.is_file():
            while self.path in self.parent._in_progress:
                # If the file is being downloaded in another request then we
                # have to wait for it to finish before it's safe to read the
                # cache. Keep sending little "it's coming" messages so that the
                # client package manager doesn't time out.
                self.send_response(HTTPStatus.ACCEPTED)
                time.sleep(.1)
            self.send_response(HTTPStatus.OK)
            return path
        try:
            # File is not cached - attempt to download it.
            response = urlopen(self.parent.base_url + self.path)
            self.send_response(HTTPStatus.OK)
            return response
        except HTTPError as ex:
            self.send_response(ex.code)

    @property
    def cache(self):
        return self.parent.base_dir / self.path.lstrip("/")

    def do_GET(self):
        response = self._head()
        self.end_headers()
        if not response:
            return

        if isinstance(response, Path):
            cache = response
            if any(fnmatch(cache.name, i) for i in self.parent.index_patterns):
                timestamp = cache.stat().st_mtime
                if all(timestamp < i for i in self.parent.last_sync_time()):
                    response = urlopen(self.parent.base_url + self.path)
                else:
                    os.utime(cache)

        if isinstance(response, Path):
            self._cache_send()
        else:
            # Don't cache FTP index pages (e.g. /some/directory/) since the
            # upstream server will redirect /some/directory/ to
            # /some/directory/index.html and that would create a local cache
            # file called $cache/some/directory where the directory
            # $cache/some/directory/ is supposed to be.
            if response.headers["Content-Type"] == "text/html":
                shutil.copyfileobj(response, self.wfile)
                return
            self._download_send(response)

    def _cache_send(self):
        """Send a file from cache to the client."""
        cache = self.cache
        if range := re.match(r"bytes=(\d*)-(\d*)", self.headers["Range"] or ""):
            start = int(range[1] or 0)
            length = int(range[2]) - start if range[2] else None
        else:
            length = None
        with open(cache, "rb") as f:
            if range:
                f.seek(start)
            shutil.copyfileobj(f, self.wfile, length)

    def _download_send(self, response):
        """Send a file from the upstream package repository to the client
        package manager and to cache."""
        self.parent._in_progress.add(self.path)
        cache = self.cache
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            with response:
                with open(cache, "wb") as f:
                    buffer = bytearray(1 << 10)
                    while consumed := response.readinto(buffer):
                        f.write(buffer[:consumed])
                        try:
                            self.wfile.write(buffer[:consumed])
                        except (BrokenPipeError, ConnectionResetError):
                            # If the client package manager cancels half way
                            # through then continue the download to cache since
                            # the client will likely ask for the rest of the
                            # file soon after.
                            shutil.copyfileobj(response, f)
                            return
        except Exception as ex:  # pragma: no cover
            if isinstance(ex, HTTPError):
                self.send_response(ex.code)
            else:
                self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            if cache.exists():
                os.remove(cache)
            raise
        finally:
            self.parent._in_progress.remove(self.path)


def _arch_sync_time(self):
    with urlopen(self.base_url + "/lastsync") as _response:
        yield int(_response.read())


def _alpine_sync_time(self):
    # Alpine repositories are only updated at most, once per hour and always on
    # the hour (i.e. at xx:00:00).
    yield time.time() // 3600 * 3600
    with urlopen(self.base_url + "/last-updated") as _response:
        yield int(_response.read())


mirrors = {
    "arch":
        CachedMirror(
            "https://geo.mirror.pkgbuild.com/",
            cache_root / "arch",
            ["*.db", "*.files"],
            ["*.db.sig", "*.files.sig"],
            8900,
            "echo 'Server = http://0.0.0.0:8900/$repo/os/$arch' > /etc/pacman.d/mirrorlist",
            _arch_sync_time,
        ),
    "alpine":
        CachedMirror(
            "https://dl-cdn.alpinelinux.org/alpine/",
            cache_root / "alpine",
            ["APKINDEX.tar.gz"],
            [],
            8901,
            r"sed -r -i 's|^.*/v\d+\.\d+/|http://0.0.0.0:8901/edge/|g' /etc/apk/repositories",
            _alpine_sync_time,
        ),
}

if __name__ == "__main__":
    if len(sys.argv) > 2:
        import subprocess
        with mirrors[sys.argv[1]]:
            subprocess.run(sys.argv[2:])
    else:
        mirrors[sys.argv[1]].serve()
