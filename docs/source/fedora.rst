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

* ``debugsource``: Contains the source code for any compiled binaries. Again
  created only if your project contains compiled code.

Distribute the debug packages if you expect your users to need to use a C
debugger on your code.


Target Fedora version
.....................

Fedora comes in discrete releases. `polycotylus` supports building for ``v37``
or newer using the commands below respectively. ::

    polycotylus fedora:37
    polycotylus fedora:38
    polycotylus fedora:39
    polycotylus fedora:40
    polycotylus fedora:41  # default
    polycotylus fedora:42  # raw hide

Installing a package built for a different release of Fedora will usually mean
that the build and runtime minor versions of Python do not match and by
implication neither will their paths to ``site-packages``. Support for ``v36``
or lower is impossible due to its not providing a recent enough version of
setuptools.


.. _fedora_caveats:

Caveats
.......

Fedora's repository indexes are enormous and are not efficiently stored. Fedora
compensates by using ``zchunk`` (a fancy delta/compression tool) when
downloading its indexes so that, whilst the first update takes hundreds of
megabytes, subsequent updates are just diffs and therefore require only a few
megabytes. The complexity of ``zchunk`` causes havoc to `polycotylus`:

* `polycotylus`\ 's usual behaviour of intercepting package downloads and
  caching them cannot handle ``zchunk``. Instead, ``dnf``\ 's cache directories
  are mounted directly on the host's file system. This in turn means that:

  - Since package managers run as root, the cache directory on the host ends up
    also owned by root.

  - Building on Windows doesn't work due to the NTFS file system not supporting
    the UNIX permissions and user/groups that ``dnf`` relies on.

* ``zchunk`` performs so badly under ``qemu`` architecture emulation that even a
  minimal package takes around 20 minutes to build. Building for non-native
  architectures is not recommended nor tested.


.. _fedora_signing:

Package Signing
...............

Fedora packages are optionally signed using an embedded GnuPG_ signature. See
the generic :ref:`gpg_signing` guide for the signing itself.

**To consume** your signed package, downstream users should install your public
key into their ``rpm`` key stores (although ``rpm`` strangely does nothing to
prevent you from installing packages with untrusted signatures).

Export your public key::

    gpg --armor --export 3CB69E1833270B714034B7558CA85BF8D96DB4E9 > 3CB69E1833270B714034B7558CA85BF8D96DB4E9.asc

Then put the ``.asc`` file somewhere downloadable on your website. Users can
then import the key using::

    curl -O https://your.website/downloads/3CB69E1833270B714034B7558CA85BF8D96DB4E9.asc
    sudo rpm --import 3CB69E1833270B714034B7558CA85BF8D96DB4E9.asc

They should now be able to verify your package using::

    rpm -K your-package-0.1.0-1.fc39.noarch.rpm

Note that DNF will not block installation if the key is not imported. The only
indicator that something is wrong would be the message ``digests SIGNATURES NOT
OK`` from ``rpm -K``.
