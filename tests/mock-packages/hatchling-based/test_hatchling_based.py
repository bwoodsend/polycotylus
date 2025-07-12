import importlib.metadata


def test_xxx():
    __import__("hatchling_based")


def test_version():
    assert importlib.metadata.version("hatchling_based") == "10.20"
