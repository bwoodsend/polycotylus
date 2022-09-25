import gzip
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import threading
import shutil
import signal
import os
from pathlib import Path

import pytest

from polycotylus import _docker
from polycotylus._mirror import mirrors, CachedMirror, _alpine_sync_time


def _alpine_mirror(tmp_path):
    _alpine = mirrors["alpine"]
    return CachedMirror(
        _alpine.base_url,
        tmp_path,
        _alpine.index_patterns,
        ["*.penguin"],
        9989,
        _alpine.install.replace("8901", "9989"),
        (_alpine_sync_time,),
    )


def test_basic(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://0.0.0.0:9989/MIRRORS.txt"

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
            with urlopen("http://0.0.0.0:9989/" + file) as response:
                response.read()
            assert (tmp_path / file).exists()
            (tmp_path / file).write_bytes(b"dummy value")
            with urlopen("http://0.0.0.0:9989/" + file) as response:
                assert response.read() == b"dummy value"
            os.utime(tmp_path / file, (time.time() - 1_000_000,) * 2)

        with urlopen("http://0.0.0.0:9989/" + non_index) as response:
            assert response.read() == b"dummy value"
        with urlopen("http://0.0.0.0:9989/" + index) as response:
            assert response.read() != b"dummy value"


def test_head(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://0.0.0.0:9989/MIRRORS.txt"

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

        with urlopen(Request("http://0.0.0.0:9989", method="HEAD")) as response:
            if not response.headers["Transfer-Encoding"] == "chunked":
                assert int(response.headers["Content-Length"])
            assert not response.read()


@pytest.mark.parametrize("path", [
    "/cake/sausages", "/..", "//etc",
    "/edge/main/x86_64/aaudit-0.7.2-r3.apk.penguin"
])
def test_errors(tmp_path, path):
    self = _alpine_mirror(tmp_path)

    with self:
        with pytest.raises(HTTPError) as error:
            urlopen("http://0.0.0.0:9989" + path)
        assert error.value.code == 404


def test_index_page_handling(tmp_path):
    self = _alpine_mirror(tmp_path)
    with self:
        with urlopen("http://0.0.0.0:9989") as response:
            content = response.read()
        assert b"edge" in content
        assert b"latest-stable" in content
    assert tmp_path.is_dir()
    assert list(tmp_path.iterdir()) == []

    self._base_url = "https://geo.mirror.pkgbuild.com/"
    with self:
        with urlopen(Request("http://0.0.0.0:9989",
                             headers={"Accept-Encoding": "gzip"})) as response:
            if response.headers["Transfer-Encoding"] == "chunked":
                return
            content = gzip.decompress(response.read())
            assert b"core" in content


def test_concurrent(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://0.0.0.0:9989/edge/main/x86_64/APKINDEX.tar.gz"

    with self:
        for i in range(3):
            with urlopen(url) as a:
                part = a.read(100)
                with urlopen(url) as b:
                    raw = b.read()
                    gzip.decompress(raw)
                gzip.decompress(part + a.read())


def test_kill_resume(tmp_path):
    self = _alpine_mirror(tmp_path)
    url = "http://0.0.0.0:9989/edge/main/x86_64/APKINDEX.tar.gz"
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
            _docker.run("alpine", f"{self.install} && apk add libbz2")


@pytest.mark.filterwarnings("ignore", category=pytest.PytestUnhandledThreadExceptionWarning)
def test_abort_cleanup(tmp_path, monkeypatch):
    self = _alpine_mirror(tmp_path)

    def _bogus_copy(source, dest, length=None):
        dest.write(source.read(100))
        raise KeyboardInterrupt

    monkeypatch.setattr(shutil, "copyfileobj", _bogus_copy)

    url = "http://0.0.0.0:9989/edge/main/x86_64/APKINDEX.tar.gz"
    cache = tmp_path / "edge/main/x86_64/APKINDEX.tar.gz"
    with self:
        urlopen(url).close()
        assert any(not cache.exists() or time.sleep(0.1) for _ in range(10))

        monkeypatch.undo()
        urlopen(url).close()
        assert cache.exists()

        with urlopen(url) as response:
            gzip.decompress(response.read())


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
    ],
    "manjaro": [
        "./arm-stable/core/aarch64/archlinux-keyring-20230130-1-any.pkg.tar.xz",
        "./arm-stable/core/aarch64/archlinux-keyring-20230130-1-any.pkg.tar.xz.sig",
        "./stable/core/x86_64/archlinux-keyring-20221220-1-any.pkg.tar.zst",
        "./stable/core/x86_64/archlinux-keyring-20221220-1-any.pkg.tar.zst.sig",
        "./stable/extra/x86_64/librsvg-2:2.55.1-1-x86_64.pkg.tar.zst",
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
}


@pytest.mark.parametrize("distro", mirrors)
def test_prune(distro, monkeypatch):
    mirror = mirrors[distro]
    monkeypatch.chdir(Path(__file__, "../mock-mirror-states", distro).resolve())
    monkeypatch.setattr(mirror, "base_dir", ".")
    to_delete = []
    monkeypatch.setattr(os, "remove", to_delete.append)
    mirror._prune()
    assert sorted(to_delete) == sorted(obsolete_caches[distro])
