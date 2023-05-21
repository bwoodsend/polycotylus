from ._exceptions import PolycotylusUsageError
from ._project import Project
from ._alpine import Alpine
from ._arch import Arch
from ._manjaro import Manjaro
from ._fedora import Fedora
from ._void import Void
from ._opensuse import OpenSUSE

distributions = {i.name: i for i in (Alpine, Arch, Fedora, Manjaro, Void, OpenSUSE)}
