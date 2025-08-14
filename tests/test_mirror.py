import gzip
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import threading
import shutil
import signal
import os
from pathlib import Path
import sys
import subprocess
import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http import HTTPStatus
import json
import textwrap

import pytest

from polycotylus import _docker, _exceptions
from polycotylus._mirror import mirrors, CachedMirror, _alpine_sync_time


def _alpine_mirror(tmp_path):
    _alpine = mirrors["alpine"]
    return CachedMirror(
        _alpine.base_url,
        tmp_path,
        _alpine.index_patterns,
        ["*.penguin"],
        9989,
        _alpine.install_command.replace("8901", "9989"),
        (_alpine_sync_time,),
    )


@contextlib.contextmanager
def fake_upstream(do_GET):

    class RequestHandler(BaseHTTPRequestHandler):
        pass

    RequestHandler.do_GET = do_GET

    with ThreadingHTTPServer(("", 8899), RequestHandler) as httpd:
        try:
            thread = threading.Thread(target=httpd.serve_forever)
            thread.start()
            yield
        finally:
            httpd.shutdown()


def slow_connection(payload):
    """Mimic a slow (100kB/s) download rate."""

    def upstream_get(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        for i in range(0, len(payload), 100):
            self.wfile.write(payload[i: i + 100])
            time.sleep(0.001)

    return fake_upstream(upstream_get)


def test_basic(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://localhost:9989/MIRRORS.txt"

    with pytest.raises(URLError):
        urlopen(url).close()

    with self:
        with urlopen(url) as response:
            content = response.read()
        cache = tmp_path / "MIRRORS.txt"
        assert cache.read_bytes() == content
        mtime = cache.stat().st_mtime
        with self:
            with self:
                with urlopen(url) as response:
                    assert response.read() == content
    assert cache.stat().st_mtime == mtime

    contents = []

    def _test():
        try:
            assert any(hasattr(self, "_httpd") or time.sleep(0.1) for i in range(50))
            with urlopen(url) as response:
                contents.append(response.read())
        finally:
            signal.raise_signal(signal.SIGINT)

    thread = threading.Thread(target=_test)
    thread.start()
    self.serve()
    assert contents[0] == content

    with pytest.raises(URLError):
        urlopen(url).close()

    @self.decorate
    def _fetch(url):
        with urlopen(url) as response:
            return response.read()

    assert _fetch(url) == content


def test_index_caching(tmp_path, monkeypatch):
    self = _alpine_mirror(tmp_path)
    with self:
        non_index = "MIRRORS.txt"
        index = "edge/main/x86_64/APKINDEX.tar.gz"

        now = time.time()
        monkeypatch.setattr(time, "time", lambda: now)

        for file in (non_index, index):
            with urlopen("http://localhost:9989/" + file) as response:
                response.read()
            assert (tmp_path / file).exists()
            (tmp_path / file).write_bytes(b"dummy value")
            with urlopen("http://localhost:9989/" + file) as response:
                assert response.read() == b"dummy value"
            os.utime(tmp_path / file, (time.time() - 1_000_000,) * 2)

        with urlopen("http://localhost:9989/" + non_index) as response:
            assert response.read() == b"dummy value"
        with urlopen("http://localhost:9989/" + index) as response:
            assert response.read() != b"dummy value"


def test_head(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://localhost:9989/MIRRORS.txt"

    with self:
        with urlopen(Request(url, method="HEAD")) as response:
            assert not response.read()
            length = int(response.headers["Content-Length"])
            assert length
        cache = tmp_path / "MIRRORS.txt"
        assert not cache.exists()

        with urlopen(url) as response:
            assert response.read()
        assert cache.stat().st_size == length
        with urlopen(Request(url, method="HEAD")) as response:
            assert not response.read()
            assert int(response.headers["Content-Length"]) == length

        with pytest.raises(URLError):
            urlopen(Request(url + "cake", method="HEAD")).close()

        with urlopen(Request("http://localhost:9989", method="HEAD")) as response:
            assert not response.read()


@pytest.mark.parametrize("path", [
    "/cake/sausages", "/..", "//etc",
    "/edge/main/x86_64/aaudit-0.7.2-r3.apk.penguin"
])
def test_errors(tmp_path, path):
    self = _alpine_mirror(tmp_path)

    with self:
        with pytest.raises(HTTPError) as error:
            urlopen("http://localhost:9989" + path)
        assert error.value.code == 404


def test_index_page_handling(tmp_path):
    self = _alpine_mirror(tmp_path)
    with self:
        with urlopen("http://localhost:9989") as response:
            content = response.read()
        assert b"edge" in content
        assert b"latest-stable" in content
    assert tmp_path.is_dir()
    assert list(tmp_path.iterdir()) == []

    self._base_url = "https://geo.mirror.pkgbuild.com/"
    with self:
        with urlopen(Request("http://localhost:9989",
                             headers={"Accept-Encoding": "gzip"})) as response:
            if response.headers["Transfer-Encoding"] != "chunked":
                content = gzip.decompress(response.read())
                assert b"core" in content

    self._base_url = "http://localhost:8899"

    def respond_chunked(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Transfer-Encoding", "chunked")
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"6\r\nhello \r\n5\r\nworld\r\n0\r\n\r\n")

    def respond_compressed(self):
        payload = gzip.compress(b"hello world")
        self.send_response(HTTPStatus.OK)
        self.send_header("Transfer-Encoding", "gzip")
        self.send_header("Content-Length", "text/html")
        self.send_header("Content-Type", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    for upstream in (respond_chunked, respond_compressed):
        with fake_upstream(respond_chunked):
            with self:
                with urlopen(Request("http://localhost:9989",
                             headers={"Accept-Encoding": "gzip,deflate"})) as response:
                    assert response.read() == b"hello world"


def test_concurrent(tmp_path):
    url = "http://localhost:9989/foo.bar"
    self = CachedMirror(
        "http://localhost:8899", tmp_path, ["*.bar"], [], 9989, "", (_alpine_sync_time,))
    payload = os.urandom(300_000)

    with slow_connection(payload):
        with self:
            for i in range(3):
                with urlopen(url) as a:
                    part = a.read(100)
                    with urlopen(url) as b:
                        raw = b.read()
                        assert raw == payload
                    assert part + a.read() == payload


def test_kill_resume(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://localhost:9989/edge/main/x86_64/APKINDEX.tar.gz"
    with self:
        with urlopen(url) as response:
            chunk = response.read(3233)

    with self:
        with urlopen(Request(url,
                             headers={"Range": "bytes=3233-"})) as response:
            content = chunk + response.read()

    gzip.decompress(content)


def test_tar_integrity(tmp_path):
    self = _alpine_mirror(tmp_path)

    for i in range(3):
        with self:
            _docker.run("alpine", f"{self.install_command} && apk add libbz2")


@pytest.mark.filterwarnings("ignore", category=pytest.PytestUnhandledThreadExceptionWarning)
def test_abort_cleanup(tmp_path, monkeypatch):
    self = _alpine_mirror(tmp_path)
    self._base_url = "http://localhost:8899"

    def _bogus_copy(source, dest, length=None):
        dest.write(source.read(100))
        raise KeyboardInterrupt

    monkeypatch.setattr(shutil, "copyfileobj", _bogus_copy)

    url = "http://localhost:9989/edge/main/x86_64/APKINDEX.tar.gz"
    cache = tmp_path / "edge/main/x86_64/APKINDEX.tar.gz"
    payload = os.urandom(300_000)
    with slow_connection(payload):
        with self:
            urlopen(url).close()
            assert any(not cache.exists() or time.sleep(0.1) for _ in range(10))

            monkeypatch.undo()
            urlopen(url).close()
            assert any(cache.exists() or time.sleep(0.1) for _ in range(10))

            with urlopen(url) as response:
                assert response.read() == payload


def test_control_c(tmp_path):
    def upstream_get(self):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Length", 1_000_000)
        self.end_headers()
        with contextlib.suppress(ConnectionResetError):
            for i in range(10_000):
                self.wfile.write(os.urandom(100))
                time.sleep(0.001)
                if i == 1000:
                    os.kill(p.pid, 2)

    with fake_upstream(upstream_get):
        with subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
            import sys
            sys.path.insert(0, "{os.path.dirname(__file__)}")
            from test_mirror import *
            with CachedMirror("http://localhost:8899", Path("{tmp_path}"), [], [], 9989, "", ()):
                with urlopen("http://localhost:9989/foo") as response:
                    response.read()
        """)], stderr=subprocess.PIPE) as p:
            assert p.wait(5) == -2, p.stderr
    foo_cache = tmp_path / "foo"
    assert foo_cache.stat().st_size < 1_000_000
    assert json.loads((tmp_path / "partial-downloads.json").read_bytes()) == ["/foo"]

    with CachedMirror("http://localhost:8899", tmp_path, [], [], 9989, "", ()):
        assert not foo_cache.exists()


obsolete_caches = {
    "alpine": [
        "./v3.17/main/aarch64/curl-7.87.0-r1.apk",
        "./v3.17/main/aarch64/curl-7.87.0-r2.apk",
        "./v3.17/main/aarch64/gcc-12.2.1_git20220924-r3.apk",
        "./v3.17/main/x86_64/curl-7.87.0-r0.apk",
        "./v3.17/main/x86_64/curl-7.87.0-r1.apk",
        "./v3.17/main/x86_64/curl-7.87.0-r2.apk",
    ],
    "arch": [
        "./extra/os/x86_64/libtiff-4.4.0-4-x86_64.pkg.tar.zst",
        "./extra/os/x86_64/libtiff-4.4.0-4-x86_64.pkg.tar.zst.sig",
        "./extra/os/x86_64/libtiff-4.5.0-1-x86_64.pkg.tar.zst",
        "./extra/os/x86_64/libtiff-4.5.0-1-x86_64.pkg.tar.zst.sig",
        "./extra/os/x86_64/mesa-23.1.3-2-x86_64.pkg.tar.zst",
    ],
    "manjaro": [
        "./arm-stable/core/aarch64/archlinux-keyring-20230130-1-any.pkg.tar.xz",
        "./arm-stable/core/aarch64/archlinux-keyring-20230130-1-any.pkg.tar.xz.sig",
        "./stable/core/x86_64/archlinux-keyring-20221220-1-any.pkg.tar.zst",
        "./stable/core/x86_64/archlinux-keyring-20221220-1-any.pkg.tar.zst.sig",
        "./stable/extra/x86_64/librsvg-2\uA7892.55.1-1-x86_64.pkg.tar.zst",
        "./stable/extra/os/x86_64/mesa-23.1.3-2-x86_64.pkg.tar.zst",
    ],
    "void": [
        "./current/aarch64/musl-1.1.24_12.aarch64-musl.xbps",
        "./current/aarch64/musl-1.1.24_12.aarch64-musl.xbps.sig",
        "./current/aarch64/musl-1.1.24_13.aarch64-musl.xbps",
        "./current/aarch64/musl-1.1.24_13.aarch64-musl.xbps.sig",
        "./current/aarch64/musl-devel-1.1.24_12.aarch64-musl.xbps",
        "./current/aarch64/musl-devel-1.1.24_12.aarch64-musl.xbps.sig",
        "./current/aarch64/musl-devel-1.1.24_13.aarch64-musl.xbps",
        "./current/aarch64/musl-devel-1.1.24_13.aarch64-musl.xbps.sig",
        "./current/musl/musl-1.1.24_12.x86_64-musl.xbps",
        "./current/musl/musl-1.1.24_12.x86_64-musl.xbps.sig",
        "./current/musl/musl-1.1.24_13.x86_64-musl.xbps",
        "./current/musl/musl-1.1.24_13.x86_64-musl.xbps.sig",
        "./current/musl/musl-1.1.24_14.x86_64-musl.xbps",
        "./current/musl/musl-1.1.24_14.x86_64-musl.xbps.sig",
        "./current/musl/musl-devel-1.1.24_12.x86_64-musl.xbps",
        "./current/musl/musl-devel-1.1.24_12.x86_64-musl.xbps.sig",
        "./current/musl/musl-devel-1.1.24_13.x86_64-musl.xbps",
        "./current/musl/musl-devel-1.1.24_13.x86_64-musl.xbps.sig",
        "./current/musl/musl-devel-1.1.24_14.x86_64-musl.xbps",
        "./current/musl/musl-devel-1.1.24_14.x86_64-musl.xbps.sig",
    ],
    "debian13": [
        "./debian/pool/main/n/ncurses/libncursesw6_6.2%2b20201114-2_amd64.deb",
        "./debian/pool/main/p/python3-defaults/libpython3-stdlib_3.9.2-3_amd64.deb",
        "./debian/pool/main/p/python3-defaults/python3-minimal_3.9.2-3_amd64.deb",
        "./debian/pool/main/p/python3-defaults/python3_3.9.2-3_amd64.deb",
    ],
}


@pytest.mark.parametrize("distro", mirrors)
def test_prune(distro, monkeypatch):
    if distro.startswith("ubuntu"):
        return
    if distro.startswith("debian") and distro != "debian13":
        return
    mirror = mirrors[distro]
    monkeypatch.chdir(Path(__file__, "../mock-mirror-states", distro).resolve())
    monkeypatch.setattr(mirror, "base_dir", ".")
    to_delete = []
    monkeypatch.setattr(os, "remove", to_delete.append)
    mirror._prune()
    to_delete = [i.replace("\\", "/") for i in to_delete]
    assert sorted(to_delete) == sorted(obsolete_caches[distro])


def test_concurrent_usage():
    a, b, *_ = mirrors.values()
    with a:
        with b:
            urlopen(f"http://localhost:{b.port}").close()
            urlopen(f"http://localhost:{a.port}").close()
        urlopen(f"http://localhost:{a.port}").close()
    p = subprocess.Popen([sys.executable, "-m", "polycotylus._mirror", "alpine"])
    try:
        for i in range(50):
            try:
                urlopen("http://localhost:8901").close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            raise
        with pytest.raises(_exceptions.PolycotylusUsageError, match="concurrent usage"):
            with mirrors["alpine"]:
                pass
    finally:
        p.kill()
