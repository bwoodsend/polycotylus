.. _fedora_quirks:

===================
Building for Fedora
===================

Basic usage::

    polycotylus fedora

Supported architectures: ``aarch64 x86_64`` (but see final caveat below!)

Fedora will build up to three packages for one build:

* ``main``: Contains Python code and `stripped
  <https://en.wikipedia.org/wiki/Strip_%28Unix%29>`_ binaries. Created
  unconditionally.

* ``debuginfo``: Contains the debugging symbols stripped from compiled binaries.
  Created only if your project contains compiled code.

* ``debugsource``: Contains the source code for any compiled binaries. Created
  only if your project contains compiled code.

It's up to you whether or not you expect to need the debug packages.


Target Fedora version
.....................

Fedora comes in discrete releases. `polycotylus` supports building for ``v37``
and ``v38`` using the commands below respectively. ::

    polycotylus fedora:37
    polycotylus fedora:38

Installing a package built for a different release of Fedora will mean that the
build and runtime minor versions of Python do not match and by implication
neither will their paths to ``site-packages``. Support for ``v36`` or lower is
impossible due to its not providing a recent enough version of setuptools.


.. _fedora_caveats:

Caveats
.......

Fedora's repository indexes are huge and are inefficiently stored. To
compensate, Fedora uses ``zchunk`` (a fancy delta/compression tool) when
downloading its indexes so that, whilst the first update takes hundreds of
megabytes, subsequent updates require only a few megabytes. The complexity of
``zchunk`` causes several issues:

* `polycotylus`\ 's usual behaviour of intercepting package downloads and
  caching them cannot handle ``zchunk``. As a compromise, ``dnf``\ 's cache
  directories are mounted directly on the host's file system. This in turn means
  that:

  - Package managers run as root so the host cache directory's contents end up
    owned by root.

  - Building on Windows doesn't work due to the NTFS file system not supporting
    UNIX permissions and user/groups that ``dnf`` relies on.

* ``zchunk`` performs so badly under ``qemu`` architecture emulation that even a
  minimal package takes around 20 minutes to build. Building for non-native
  architectures is not recommended nor tested.
