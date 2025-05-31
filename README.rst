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

Polycotylus converts Python packages into native Linux distribution packages
such as RPMs, DEBs or APKs.

Polycotylus builds on each target Linux distribution, dodging the usual Linux
nightmare that is ABI compatibility, using each distribution's native packaging
system. It uses Docker to virtualize each Linux distribution and Qemu to
virtualize almost any architecture meaning that you can build for any supported
distribution or architecture from a single machine. You can even build on
Windows or macOS. You can build apps for Linux phones: running ``polycotylus
manjaro --architecture aarch64`` will build an app installable on a phone
running Manjaro or ``polycotylus alpine --architecture aarch64`` will build a
`postmarketOS <https://postmarketos.org/>`_ compatible app.

Unlike PyInstaller, Flatpaks or Snaps, polycotylus does not bundle dependencies
into one fat package – instead, dependencies (including Python itself) are
declared as such in the package's metadata where the end user's system package
manager will see and act upon them. This makes the packages tiny, updates
modular and propagation of security patches for vulnerabilities in your
dependencies no longer your problem. Complex system dependencies such as
GStreamer or GTK can be declared in addition to PyPI packages turning them from
packaging nightmares into *just another dependency*. This approach also solves
the standard UNIX question of *should I include libXYZ in my package* to which
the answers *yes* and *no* are often simultaneously wrong.

Polycotylus doesn't just dump code into an archive and hope for the best – it
verifies it as well. Packages are installed into a clean, minimal Docker
container in which it then runs your test suite. It should be almost impossible
to forget a dependency or miss a data file without polycotylus letting you know.

For GUI applications, using a system package manager also allows you to add
*desktop integration*. You can register your application so that launch menus
(e.g. Gnome's App tiles) and file browsers know that your application exists,
have icons and descriptions, and are aware of their supported file types.


Supported distributions
.......................

Polycotylus is limited by a hard constraint in that it can not support any
target Linux distribution that does not provide ``setuptools>=61.0`` in its
official package repositories. This unfortunately rules out almost all of the
*stable*/long term support distributions (which also happen to be the most
popular) currently including all stable branches of Debian, Ubuntu <23.04, SLES,
OpenSUSE Leap and all of the RedHat/CentOS-like distributions par Fedora ≥37.

=============  ===========================================
Distributions  Supported versions
=============  ===========================================
Alpine_        3.17-3.22, edge
Arch_          rolling
Debian_        13 (prerelease)
Fedora_        37-42, 43 (rawhide)
Manjaro_       rolling
O̶p̶e̶n̶S̶U̶S̶E       Redacted
Ubuntu_        24.04-25.10
Void_          rolling
=============  ===========================================

.. _Alpine: https://alpinelinux.org/
.. _Arch: https://archlinux.org/
.. _Debian: https://www.debian.org/
.. _Fedora: https://fedoraproject.org/
.. _Manjaro: https://manjaro.org/
.. _Ubuntu: https://ubuntu.com/
.. _Void: https://voidlinux.org/


Development status
..................

This project is missing some key functionality that I'd consider it needs before
going on PyPI. To use this project as it is right now, install ``polycotylus``
from version control (instructions below). It does have (what I like to think of
as comprehensive) documentation but it needs to be built from source too:

.. code-block:: bash

    git clone git@github.com:bwoodsend/polycotylus
    cd polycotylus
    # Maybe create and activate a virtual environment
    pip install -e .
    pip install -r docs/requirements.txt
    cd docs
    make html
    xdg-open build/html/index.html

In terms of feature completeness:

* The biggest gaping feature gap is polycotylus's requirement that all
  dependencies are already available on each target distribution's repositories.
  If your application is made up of multiple custom packages or depends on an
  unavailable 3rd party package then polycotylus is useless to you. The plan is
  to facilitate making personal package repositories, where builds for packages
  can depend on other packages in the personal repository. Or possibly it's just
  to create a ``polycotylus --inlcude-project=../other-project`` flag – I'm not
  sure I like either option...

Other, less significant but more achievable things I'd like to do:

* Custom MIME Type support (i.e. declaring a new made-up file suffix and its
  association with an application).

* See if I can get hardware related functionality (audio, USB) to work with
  Docker.

That said, if you don't need any of the above then polycotylus should work for
you.
