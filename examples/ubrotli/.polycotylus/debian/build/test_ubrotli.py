import base64

import pytest

import ubrotli


def test_basic():
    buffer = b"hello" * 10 + b"\x00" * 100
    compressed = ubrotli.compress(buffer)
    assert len(compressed) < len(buffer)
    decompressed = ubrotli.decompress(compressed)
    assert decompressed == buffer


def test_high_entropy_compression():
    buffer = base64.b85decode(
        "ssK7OsCZ?vu848I48dz)+PiXS2=M|)8LSZ$wocMStBAk}hO4C{u*sqO?Hy2GKi%`O)pY")
    compressed = ubrotli.compress(buffer)
    assert len(compressed) > len(buffer)
    decompressed = ubrotli.decompress(compressed)
    assert decompressed == buffer


def test_low_entropy_decompression():
    buffer = b"0" * 10_000
    compressed = ubrotli.compress(buffer)
    assert ubrotli.decompress(compressed) == buffer


def test_decompress_invalid():
    buffer = b"hello" * 100
    compressed = ubrotli.compress(buffer)
    with pytest.raises(ValueError):
        ubrotli.decompress(compressed[:-1])


def test_with_kwargs():
    buffer = b"hello" * 100
    best = ubrotli.compress(buffer, quality=ubrotli.MAX_QUALITY)
    worst = ubrotli.compress(buffer, quality=ubrotli.MIN_QUALITY)
    assert len(best) < len(worst) < len(buffer)
    ubrotli.compress(buffer, mode=ubrotli.MODE_TEXT)
