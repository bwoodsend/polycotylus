=======================
Welcome to polycotylus!
=======================

∘
`MIT license <https://github.com/bwoodsend/polycotylus/blob/master/LICENSE>`_
∘
P̶y̶P̶I
∘
D̶o̶c̶u̶m̶e̶n̶t̶a̶t̶i̶o̶n
∘
`Source code <https://github.com/bwoodsend/polycotylus>`_
∘
`Bug reports <https://github.com/bwoodsend/polycotylus/issues>`_
∘
`Support <https://github.com/bwoodsend/polycotylus/discussions>`_

Polycotylus converts Python packages into native Linux distribution packages
such as RPMs or APKs. It builds on each target Linux distribution (thus dodging
the usual Linux nightmare that is ABI compatibility) and uses each
distribution's packaging tool. In the process, it produces a build script which,
if your project is open source, can be submitted upstream so that your package
will become available on official package repositories (although please don't do
this yet – I want to get some form of review from the distribution maintainers
first).

Polycotylus uses Docker to virtualize each Linux distribution and Qemu to
virtualize almost any architecture meaning that you can build for any supported
distribution or architecture from a single machine. You can even build on
Windows or macOS thanks to Docker Desktop. You can also build apps for Linux
phones: running ``polycotylus manjaro --architecture aarch64`` will build an app
installable on a phone running Manjaro or ``polycotylus alpine --architecture
aarch64`` will build a `postmarketOS <https://postmarketos.org/>`_ compatible
app.

Unlike PyInstaller, Flatpaks or Snaps, polycotylus does not bundle dependencies
into your packages – rather dependencies (including Python itself) are declared
as such in the package's metadata where the end user's system package manager
will see and act upon them. This makes the packages tiny, updates modular and
propagation of security patches for vulnerabilities in your dependencies no
longer your problem. Complex system dependencies such as GStreamer or GTK can be
declared in addition to PyPI packages turning them from packaging nightmares
into *just another dependency*. This approach also solves the standard UNIX
question of *should I include libXYZ in my package* to which the answers *yes*
and *no* are often simultaneously wrong.

Polycotylus doesn't just dump your code into an archive and hope for the best –
it verifies it too! It installs your package into a clean, minimal Docker
container and runs your test suite in it. Unless your test suite is a no-op, it
should be almost impossible to forget a dependency or miss a data file without
finding out immediately.

For GUI applications, using a system package manager also allows you to add
desktop integration. This means registering your application so that launch
menus (e.g. Gnome's App tiles) know your application exists, adding icons,
descriptions, registering supported file types, etc.


Supported distributions
.......................

Polycotylus is limited by a hard constraint in that it can not support any
target Linux distribution that does not provide ``setuptools>=61.0`` in its
official package repositories. This unfortunately rules out all of the
*stable*/long term support distributions (which also happen to be the most
popular) currently including all stable branches of Debian, Ubuntu <23.04, SLES,
OpenSUSE Leap and all of the RedHat/CentOS-like distributions par Fedora ≥37.
This just leaves rolling build distributions and distributions with fast release
cycles and up to date package repositories.

=============  ============================================
Distributions  Supported versions
=============  ============================================
Alpine_        3.17-3.19, edge
Arch_          rolling
Debian_        13 (pre-release)
Fedora_        37-39, 40 (pre-release)
Manjaro_       rolling
OpenSUSE_      Tumbleweed only (rolling)
Ubuntu_        23.04, 23.10 (interim releases)
Void_          rolling
=============  ============================================

.. _Alpine: https://alpinelinux.org/
.. _Arch: https://archlinux.org/
.. _Debian: https://www.debian.org/
.. _Fedora: https://fedoraproject.org/
.. _Manjaro: https://manjaro.org/
.. _OpenSUSE: https://www.opensuse.org/
.. _Ubuntu: https://ubuntu.com/
.. _Void: https://voidlinux.org/


Development status
..................

This project is not considered production ready. It is not available on PyPI nor
is its documentation on readthedocs. To use this project as it is right now, you
will have to install ``polycotylus`` from version control and build the
documentation from source:

.. code-block:: bash

    git clone git@github.com:bwoodsend/polycotylus
    cd polycotylus
    pip install -e .
    pip install -r docs/requirements.txt
    cd docs
    make html
    xdg-open build/html/index.html
