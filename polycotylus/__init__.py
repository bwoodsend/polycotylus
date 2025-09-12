def machine():
    """The current architecture normalized to Linux's naming convention."""
    import platform
    native = platform.machine()
    return {"AMD64": "x86_64", "arm64": "aarch64"}.get(native, native)


from ._exceptions import PolycotylusUsageError
from ._project import Project
from ._alpine import Alpine, Alpine317, Alpine318, Alpine319, Alpine320, Alpine321, Alpine322, AlpineEdge
from ._arch import Arch
from ._manjaro import Manjaro
from ._fedora import Fedora, Fedora37, Fedora38, Fedora39, Fedora40, Fedora41, Fedora42, Fedora43, Fedora44
from ._void import Void, VoidGlibc, VoidMusl
from ._debian import Debian, Debian13, Debian14
from ._ubuntu import Ubuntu, Ubuntu2404, Ubuntu2504, Ubuntu2510

distributions = {i.name: i for i in (Alpine, Arch, Debian, Fedora, Manjaro, Ubuntu, Void)}
distribution_tags = {i: [] for i in distributions}

distributions["alpine:3.17"] = Alpine317
distributions["alpine:3.18"] = Alpine318
distributions["alpine:3.19"] = Alpine319
distributions["alpine:3.20"] = Alpine320
distributions["alpine:3.21"] = Alpine321
distributions["alpine:3.22"] = Alpine322
distributions["alpine:edge"] = AlpineEdge
distributions["debian:13"] = Debian13
distributions["debian:14"] = Debian14
distributions["fedora:37"] = Fedora37
distributions["fedora:38"] = Fedora38
distributions["fedora:39"] = Fedora39
distributions["fedora:40"] = Fedora40
distributions["fedora:41"] = Fedora41
distributions["fedora:42"] = Fedora42
distributions["fedora:43"] = Fedora43
distributions["fedora:44"] = Fedora44
distributions["ubuntu:24.04"] = Ubuntu2404
distributions["ubuntu:25.04"] = Ubuntu2504
distributions["ubuntu:25.10"] = Ubuntu2510
distributions["void:glibc"] = VoidGlibc
distributions["void:musl"] = VoidMusl

[distribution_tags[i].append(j) for (i, j) in (i.split(":") for i in distributions if ":" in i)]
