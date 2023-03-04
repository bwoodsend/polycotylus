import shutil
import subprocess

import pytest

from polycotylus.__main__ import cli


def test_fish(capsys):
    with pytest.raises(SystemExit) as error:
        cli(["--completion=fish"])
    assert error.value.code == 0
    completions = capsys.readouterr().out

    if not shutil.which("fish"):
        pytest.skip("fish shell is not installed")

    assert completions
    def _exec(code):
        return subprocess.check_output(["fish"], text=True, input=completions + code)

    assert not _exec("")
    assert "alpine" in _exec("complete --do-complete 'polycotylus '")
    assert "alpine" not in _exec("complete --do-complete 'polycotylus arch '")

    assert "--architecture" in _exec("complete --do-complete 'polycotylus -'")
    assert "--architecture" in _exec("complete --do-complete 'polycotylus manjaro -'")
    assert "s390x" in _exec("complete --do-complete 'polycotylus alpine --architecture='")
    assert "aarch64" in _exec("complete --do-complete 'polycotylus manjaro --architecture='")
    assert "s390x" not in _exec("complete --do-complete 'polycotylus manjaro --architecture='")
