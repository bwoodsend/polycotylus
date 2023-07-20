.. _macos_quirks:

===================
Building from macOS
===================

`polycotylus` supports building from (but not for!) macOS on both Intel and M1
based CPUs with Docker provided by either OrbStack_ or `Docker Desktop for
macOS`_. See :ref:`OrbStack versus Docker Desktop <orbstack_versus_docker>` for
a comparison.

If you're on macOS M1, be aware that `polycotylus` defaults to building for your
current architecture where possible then falls back to emulating ``x86_64`` when
not so ``polycotylus alpine`` will build for ``aarch64`` but ``polycotylus
arch`` will build for ``x86_64`` because Arch Linux does not support
``aarch64``.


.. _orbstack_versus_docker:

OrbStack versus Docker Desktop
..............................

OrbStack_ is lighter and faster, especially when emulating ``x86_64`` from an M1
machine, but supports only native or Rosetta emulatable architectures (i.e.
``x86 x86_64`` on Intel CPU, ``aarch64 armv7 x86 x86_64`` on an M1 CPU). See the
table of `polycotylus` build times below for a rough idea of how much faster.

====================== ======== ======
Mode                   OrbStack Docker
====================== ======== ======
Native, no cache       12.44    18.60
Native, cached         6.30     8.62
Qemu/Rosetta, no cache 23.96    46.13
Qemu/Rosetta, cached   8.68     20.69
====================== ======== ======

All times are in seconds and exclude network time. A *no cache* build is one ran
after clearing Docker's build cache (``docker system prune -f``).
