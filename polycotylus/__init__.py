def machine():
    """The current architecture normalized to Linux's naming convention."""
    import platform
    native = platform.machine()
    return {"AMD64": "x86_64"}.get(native, native)


from ._exceptions import PolycotylusUsageError
from ._project import Project
from ._alpine import Alpine, Alpine317, Alpine318
from ._arch import Arch
from ._manjaro import Manjaro
from ._fedora import Fedora, Fedora37, Fedora38
from ._void import Void, VoidGlibc, VoidMusl
from ._opensuse import OpenSUSE

distributions = {i.name: i for i in (Alpine, Arch, Fedora, Manjaro, Void, OpenSUSE)}
distributions["alpine:3.17"] = Alpine317
distributions["alpine:3.18"] = Alpine318
distributions["fedora:37"] = Fedora37
distributions["fedora:38"] = Fedora38
distributions["void:glibc"] = VoidGlibc
distributions["void:musl"] = VoidMusl
