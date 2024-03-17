=========================
Building for Debian Linux
=========================

Basic usage::

    polycotylus debian

* Supported architectures: ``amd64 arm64 armel armhf i386 mips64el ppc64el riscv64 s390x``

* Debian packages are compatible with `Kali Linux <https://www.kali.org/>`_ and
  will be compatible with the following distributions **only** when they migrate
  to a Debian >= 13 base: `Raspbian <https://www.raspbian.org/>`_ (use
  ``--architecture=armhf``), `deepin <https://www.deepin.org/>`_, `Cumulus Linux
  <https://docs.nvidia.com/networking-ethernet-software/cumulus-linux/>`_,
  `SteamOS <https://store.steampowered.com/steamos>`_

* Debian packages are similar to but incompatible with: `Parrot OS
  <https://parrotlinux.org/>`_, `Ubuntu <https://ubuntu.com>`_, `Devuan
  <https://www.devuan.org/>`_

As with Alpine, please don't blindly build for every architecture. ``mips``
devices are almost exclusively found in electric gates and Wi-Fi routers – not
something likely to want a desktop application. The architecture names that
Debian uses are somewhat nonstandard or are really brand names rather than
instruction sets. The following table maps Debian names to what each
architecture is traditionally called.

===========  ====================
Debian name  Instruction set name
===========  ====================
``amd64``    ``x86_64``
``arm64``    ``aarch64``
``armel``    ``armv5l``
``armhf``    ``armv7l``
``ppc64el``  ``ppc64le``
===========  ====================


Caveats
.......

* Due to Debian's extremely slow release cycle, only the testing branch of
  Debian (13 a.k.a. Trixie) or can be supported.
