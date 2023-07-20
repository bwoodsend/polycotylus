.. _podman_quirks:

====================
Building with Podman
====================

`polycotylus` supports using Podman_ in place of Docker_ on Linux. This support
is begrudging and expensive – Podman's rootless support gets very ugly when
given build tools requiring multi-user setups. Please don't use Podman with
`polycotylus` if given the choice. Support is intended only for RedHat/RPM based
Linux distributions where Podman is favoured so strongly that Docker is removed
from the official package repositories.

To switch between Docker_ and Podman_, use the following commands::

    # Instruct polycotylus to use podman as its docker implementation
    polycotylus --configure docker=podman

    # Instruct polycotylus to use a specific podman location
    polycotylus --configure docker=/usr/bin/podman

    # Restore the default of using docker
    polycotylus --configure docker=


.. _podman_caveats:

Caveats
.......

* On most host setups, using Qemu architecture emulation leads to an issue with
  sudo. ::

      sudo: effective uid is not 0, is /usr/bin/sudo on a file system with the 'nosuid' option set or an NFS file system without root privileges?

  If anyone thinks they know how to fix this, please post the answer on `this
  StackOverflow question <https://stackoverflow.com/q/75954301/>`_.

* Building for OpenSUSE doesn't work.

* On Debian/Ubuntu, the latest version of Podman_ available is too old for
  `polycotylus`. Use the `Podman PPA
  <https://podman.io/docs/installation#debian>`_ to get a usable version.

* Build times are roughly double what they are with Docker_.
