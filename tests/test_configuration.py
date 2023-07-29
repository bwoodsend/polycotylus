from textwrap import dedent
import subprocess
import sys

import pytest

import polycotylus.__main__


def test_docker_configure(tmp_path):
    user_config = tmp_path / "user-config"
    root_config = tmp_path / "root-config"
    common = dedent(f"""
        import appdirs
        appdirs.site_config_dir = lambda *_, **__: {repr(str(root_config))}
        appdirs.user_config_dir = lambda *_, **__: {repr(str(user_config))}
        import polycotylus.__main__
    """)

    def _exec(code):
        p = subprocess.run([sys.executable, "-"], input=common + dedent(code),
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.returncode == 0, p.stderr
        return p.stdout

    assert _exec("print(polycotylus._docker.docker)") == "docker\n"
    assert _exec("polycotylus.__main__.cli(['--configure'])") == "docker=\n"
    assert _exec("polycotylus.__main__.cli(['--configure', 'docker'])") == "\n"

    fake_docker = tmp_path / "fake docker"
    polycotylus._misc.unix_write(
        fake_docker, "#!/usr/bin/env sh\necho Docker version 12.34.5, build cb74dfcd85\n")
    fake_docker.chmod(0o755)
    assert _exec(f"polycotylus.__main__.cli(['--configure', 'docker={fake_docker}'])") == ""
    assert _exec("polycotylus.__main__.cli(['--configure'])") == f"docker={fake_docker}\n"
    assert _exec("print(polycotylus._docker.docker.version)") == "12.34.5\n"

    # If configured with an invalid Docker path, polycotylus's CLI should still
    # be functional enough to undo the configuration – only leading to an error
    # if a build is initiated.
    assert _exec("polycotylus.__main__.cli(['--configure', 'docker=bagpuss'])") == ""
    assert _exec("polycotylus.__main__.cli(['--configure', 'docker'])") == "bagpuss\n"

    assert _exec("polycotylus.__main__.cli(['--configure', 'docker='])") == ""
    assert _exec("print(polycotylus._docker.docker)") == "docker\n"

    with pytest.raises(SystemExit, match="Unknown .* option 'cake'"):
        polycotylus.__main__.cli(["--configure", "cake=socks"])
