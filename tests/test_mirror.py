import gzip
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import threading
import signal
import os

from docker import from_env
import pytest

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
        _alpine_sync_time,
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
        time.sleep(.2)
        try:
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
        cache = tmp_path / "MIRRORS.txt"
        assert not cache.exists()

        with urlopen(url) as response:
            assert response.read()
        with urlopen(Request(url, method="HEAD")) as response:
            assert not response.read()

        with pytest.raises(URLError):
            urlopen(Request(url + "cake", method="HEAD")).close()


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
    docker = from_env()
    self = _alpine_mirror(tmp_path)

    for i in range(3):
        with self:
            docker.containers.run(
                "alpine", ["ash", "-c", f"{self.install} && apk add libbz2"],
                network_mode="host", remove=True)
