=========================
Building for Debian Linux
=========================

Basic usage::

    polycotylus debian

Supported architectures: ``amd64 arm64 armel armhf i386 mips64el ppc64el riscv64 s390x``

As with Alpine, don't just blindly build for every architecture. ``mips``
devices are almost exclusively found in electric gates and Wi-Fi routers – not
something for a desktop application. Debian uses some nonstandard/brand names
for its architectures. The following table maps Debian names to what each
architecture is normally called.

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
