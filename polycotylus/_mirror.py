import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
import shutil
import re
import threading
from functools import wraps
from fnmatch import fnmatch
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

import appdirs

cache_root = Path(appdirs.user_cache_dir("polycotylus"))


class CachedMirror:

    def __init__(self, base_url, base_dir, index_patterns, port):
        self.base_url = base_url.strip("/")
        self.base_dir = Path(base_dir)
        self.index_patterns = index_patterns
        self.port = port

    def serve(self):
        handler = type("Handler", (RequestHandler,), {"parent": self})

        httpd = ThreadingHTTPServer(("", self.port), handler)
        host, port = httpd.socket.getsockname()
        host = "localhost" if os.name == "nt" else host
        print("http://{}:{}".format(host, self.port))
        try:
            httpd.serve_forever()
        except:
            httpd.shutdown()

    def __enter__(self):
        handler = type("Handler", (RequestHandler,), {"parent": self})
        self._httpd = ThreadingHTTPServer(("", self.port), handler)
        thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        thread.start()
        self._thread = thread

    def __exit__(self, *_):
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
        path = self.cache
        if path.is_file():
            self.send_response(HTTPStatus.OK)
        elif path.is_dir():
            self.send_response(404)
        else:
            request = Request(self.parent.base_url + self.path, method="HEAD")
            try:
                with urlopen(request):
                    pass
            except HTTPError as ex:
                self.send_response(ex.code)
            else:
                self.send_response(HTTPStatus.OK)
        self.end_headers()

    @property
    def cache(self):
        return self.parent.base_dir / self.path.lstrip("/")

    def do_GET(self):
        self.do_HEAD()
        cache = self.cache
        if any(fnmatch(cache.name, i) for i in self.parent.index_patterns):
            with urlopen(self.parent.base_url + "/lastsync") as response:
                timestamp = int(response.read())
            try:
                if cache.stat().st_mtime < timestamp:
                    return self._download_send()
            except FileNotFoundError:
                return self._download_send()

        try:
            return self._cache_send()
        except FileNotFoundError:
            pass

        self._download_send()

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

    def _download_send(self):
        cache = self.cache
        cache.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(self.parent.base_url + self.path) as response:
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
                     ["*.db", "*.db.sig", "*.files", "*.files.sig"], 8900),
}

if __name__ == "__main__":
    mirrors[sys.argv[1]].serve()
