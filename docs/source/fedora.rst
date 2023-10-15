.. _fedora_quirks:

===================
Building for Fedora
===================

Basic usage::

    polycotylus fedora

* Supported architectures: ``aarch64 x86_64`` (but see final caveat below!)

* Fedora packages are compatible with: `Nobara Linux
  <https://nobaraproject.org/>`_

* Fedora packages are similar to but incompatible with: `CentOS
  <https://www.centos.org/>`_, `RHEL
  <https://developers.redhat.com/products/rhel/overview>`_, `Rocky Linux
  <https://rockylinux.org/>`_

Fedora will build up to three packages for one build:

* ``main``: Contains Python code and `stripped
  <https://en.wikipedia.org/wiki/Strip_%28Unix%29>`_ binaries. Created
  unconditionally.

* ``debuginfo``: Contains the debugging symbols stripped from compiled binaries.
  Created only if your project contains compiled code.

* ``debugsource``: Contains the source code for any compiled binaries. Created
  only if your project contains compiled code.

Distribute the debug packages if you expect your users to need to use a C
debugger on your code.


Target Fedora version
.....................

Fedora comes in discrete releases. `polycotylus` supports building for ``v37``
or newer using the commands below respectively. ::

    polycotylus fedora:37
    polycotylus fedora:38
    polycotylus fedora:39  # pre-release
    polycotylus fedora:40  # rawhide

Installing a package built for a different release of Fedora will mean that the
build and runtime minor versions of Python do not match and by implication
neither will their paths to ``site-packages``. Support for ``v36`` or lower is
impossible due to its not providing a recent enough version of setuptools.


.. _fedora_caveats:

Caveats
.......

Fedora's repository indexes are huge and are inefficiently stored. Fedora
compensates by using ``zchunk`` (a fancy delta/compression tool) when
downloading its indexes so that, whilst the first update takes hundreds of
megabytes, subsequent updates require only a few megabytes. The complexity of
``zchunk`` causes havoc to `polycotylus`:

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
