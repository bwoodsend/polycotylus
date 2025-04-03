.. _macos_quirks:

===================
Building from macOS
===================

`polycotylus` supports building from (but not for!) macOS on both Intel and
``arm64`` based CPUs with Docker provided by either OrbStack_ or `Docker Desktop
for macOS`_. There is a :ref:`small comparison <orbstack_versus_docker>` of the
two at the bottom of this page.

If you're on macOS ``arm64``, be aware that `polycotylus` defaults to building
for your current architecture where possible then falls back to emulating
``x86_64`` when not. The most potentially surprising implication of this is that
``polycotylus alpine`` will build for ``aarch64`` since Alpine supports
``aarch64`` but Arch Linux does not so ``polycotylus arch`` will build for
``x86_64``.


.. _orbstack_versus_docker:

OrbStack versus Docker Desktop
..............................

OrbStack_ is considerably lighter and faster, especially when emulating
``x86_64`` from an ``arm64`` machine, but supports only native or Rosetta
emulatable architectures (i.e. ``x86 x86_64`` on Intel CPU, ``aarch64 armv7 x86
x86_64`` on an M1 CPU). See the table of `polycotylus` build times below for a
rough idea of how much faster.

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
