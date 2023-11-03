import contextlib

from polycotylus._project import Project
from polycotylus._manjaro import Manjaro
from polycotylus import _docker
from polycotylus._mirror import cache_root, _manjaro_preferred_mirror, RequestHandler
import shared


class TestCommon(shared.Base):
    cls = Manjaro
    package_install = "pacman -Sy --needed --noconfirm glibc"


def test_mirror_detection(monkeypatch):
    with contextlib.suppress(FileNotFoundError):
        (cache_root / "manjaro-mirror").unlink()
    requests = []
    original_do_GET = RequestHandler.do_GET
    monkeypatch.setattr(RequestHandler, "do_GET",
                        lambda self: requests.append(self.path) or original_do_GET(self))
    with Manjaro.mirror:
        for architecture in ["x86_64", "aarch64"]:
            _docker.run("manjarolinux/base", f"""
                {Manjaro.mirror.install_command}
                pacman -Sy
            """, architecture=architecture, tty=True)
    assert requests, "Mirror is being ignored"
    assert _manjaro_preferred_mirror() == _manjaro_preferred_mirror()


test_multiarch = shared.qemu(Manjaro)


def test_dumb_text_viewer_signing(monkeypatch):
    monkeypatch.setenv("GNUPGHOME", str(shared.gpg_home))
    self = Manjaro(Project.from_root(shared.dumb_text_viewer), None, "ED7C694736BC74B3")
    self.generate()
    packages = self.build()
    self.test(packages["main"])
    self.update_artifacts_json(packages)

    # Test that GnuPG is running under C.UTF8 locale instead of C
    container = _docker.run(self.build_builder_image(), ["gpg", "--list-secret-keys"],
                            volumes=[(shared.gpg_home, "/root/.gnupg")])
    assert "🎩" in container.output


def test_fussy_arch():
    self = Manjaro(Project.from_root(shared.fussy_arch))
    assert "\narch=(aarch64)\n" in self.pkgbuild()
