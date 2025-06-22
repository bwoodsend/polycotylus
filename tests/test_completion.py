import shutil
import subprocess
import shlex
from pathlib import Path

import pytest

from polycotylus.__main__ import cli
import shared


def test_fish(capsys, monkeypatch):
    with pytest.raises(SystemExit) as error:
        cli(["--completion=fish"])
    assert error.value.code == 0
    completions = capsys.readouterr().out

    if not shutil.which("fish"):
        pytest.skip("fish shell is not installed")

    assert completions

    def _exec(code):
        return subprocess.check_output(["fish"], text=True, input=completions + code)

    def _complete(command):
        return _exec(shlex.join(["complete", "--do-complete", command]))

    assert not _exec("")
    assert "alpine" in _complete("polycotylus ")
    assert "alpine" not in _complete("complete polycotylus arch ")

    assert "--architecture" in _complete("polycotylus -")
    assert "--architecture" in _complete("polycotylus manjaro -")
    assert "ppc64le" in _complete("polycotylus alpine --architecture=")
    assert "aarch64" in _complete("polycotylus manjaro --architecture=")
    assert "ppc64le" not in _complete("polycotylus manjaro --architecture=")
    assert "ppc64le" in _complete("polycotylus alpine:3.20 --architecture=")
    assert "mips64el" not in _complete("polycotylus alpine:3.20 --architecture=")
    assert "riscv64" in _complete("polycotylus alpine --architecture=")
    assert "riscv64" not in _complete("polycotylus alpine:3.19 --architecture=")
    assert "riscv64" in _complete("polycotylus alpine:3.20 --architecture=")

    assert "--void-signing-certificate" in _complete("polycotylus void -")
    assert "--void-signing-certificate" in _complete("polycotylus void:musl -")
    assert "--void-signing-certificate" in _complete("polycotylus -")
    certificate = str(Path(__file__, "../void-keys/unencrypted-ssl.pem").resolve())
    assert certificate in _complete(f"polycotylus void --void-signing-certificate '{certificate[:-5]}")

    assert "--void-signing-certificate" not in _complete("polycotylus arch -")
    assert "--gpg-signing-id" not in _complete("polycotylus void -")
    assert "--gpg-signing-id" in _complete("polycotylus arch -")

    if shutil.which("gpg"):
        monkeypatch.setenv("GNUPGHOME", str(shared.gpg_home))
        assert "ED7C694736BC74B3" in _complete("polycotylus arch --gpg-signing-id ")
