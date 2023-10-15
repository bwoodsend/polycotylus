.. _arch_quirks:

=======================
Building for Arch Linux
=======================

Basic (and only) usage::

    polycotylus arch

* Supported architectures: ``x86_64``

* Arch packages are compatible with: `EndeavourOS <https://endeavouros.com/>`_,
  `Garuda Linux <https://garudalinux.org/>`_, `ArcoLinux
  <https://arcolinux.com/>`_, `BlackArch Linux <https://www.blackarch.org/>`_,
  `Archcraft <https://archcraft.io/>`_, `Athena OS <https://athenaos.org/>`_

* Arch packages are similar to but incompatible with: `Manjaro Linux
  <https://manjaro.org/>`_, `Artix Linux <https://artixlinux.org/>`_


Lifetime of a build
...................

Arch Linux is a rolling build meaning that new versions of packages containing
ABI incompatibilities (or any other incompatibilities arising from the build and
runtime environments being different) can be released at any time and pinning or
downgrading dependencies is prohibited – you're only option is to rebuild and
re-release. One prominent case of this is the annual increment of the Arch
repositories' Python's minor version. When this happens, the ``site-packages``
directory (e.g. ``/usr/lib/python3.11/site-packages/``) moves so that your
package is no longer findable. Once this happens, your existing built packages
are effectively useless and you need to rebuild and release then encourage your
users to run ``pacman -Syu`` (upgrade all packages) before installing/upgrading
your package in case they still have the previous version of Python installed.
