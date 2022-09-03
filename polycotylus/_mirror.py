import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
from http.client import HTTPResponse
import shutil
import re
import threading
from functools import wraps
from fnmatch import fnmatch
from pathlib import Path
from urllib.request import urlopen
from urllib.error import HTTPError

import appdirs

cache_root = Path(appdirs.user_cache_dir("polycotylus"))


class CachedMirror:

    def __init__(self, base_url, base_dir, index_patterns, ignore_patterns,
                 port):
        self.base_url = base_url.strip("/")
        self.base_dir = Path(base_dir)
        self.index_patterns = index_patterns
        self.ignore_patterns = ignore_patterns
        self.port = port
        self._lock = threading.Lock()
        self._listeners = 0

    def serve(self):
        handler = type("Handler", (RequestHandler,), {"parent": self})

        httpd = ThreadingHTTPServer(("", self.port), handler)
        host, port = httpd.socket.getsockname()
        host = "localhost" if os.name == "nt" else host
        print("http://{}:{}".format(host, self.port))
        print(f"Install via:\n{self.install}")
        try:
            httpd.serve_forever()
        except:
            httpd.shutdown()

    def __enter__(self):
        with self._lock:
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
        self._httpd.shutdown()
        del self._httpd

    def decorate(self, f):

        @wraps(f)
        def wrapped(*args, **kwargs):
            with self:
                return f(*args, **kwargs)

        return wrapped


class RequestHandler(BaseHTTPRequestHandler):
    parent: CachedMirror

    def do_HEAD(self):
        response = self._head()
        if isinstance(response, HTTPResponse):
            response.close()
        self.end_headers()

    def _head(self):
        path = self.cache
        if any(fnmatch(self.path, i) for i in self.parent.ignore_patterns):
            self.send_response(404)
            return
        if path.is_file():
            self.send_response(HTTPStatus.OK)
            return path
        if path.is_dir():
            self.send_response(404)
            return
        try:
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
                with urlopen(self.parent.base_url + "/lastsync") as _response:
                    timestamp = int(_response.read())
                if cache.stat().st_mtime < timestamp:
                    response = urlopen(self.parent.base_url + self.path)

        if isinstance(response, Path):
            self._cache_send()
        else:
            self._download_send(response)

    def _cache_send(self):
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
                        except BrokenPipeError:
                            shutil.copyfileobj(response, f)
                            return
        except HTTPError as ex:
            self.send_response(ex.code)
        except:
            pass
        else:
            return
        if cache.exists():
            os.remove(cache)


mirrors = {
    "arch":
        CachedMirror("https://geo.mirror.pkgbuild.com/", cache_root / "arch",
                     ["*.db", "*.files"], ["*.db.sig", "*.files.sig"], 8900),
}

if __name__ == "__main__":
    mirrors[sys.argv[1]].serve()
