===================
Building for Ubuntu
===================

Basic usage::

    polycotylus ubuntu

* Supported architectures: ``amd64 arm64 armhf ppc64el s390x``

* Ubuntu packages are compatible with `Linux Mint <https://linuxmint.com/>`_ and
  will be compatible with the following distributions **only** when they migrate
  to a Ubuntu >= 23.04 base: `Pop!_OS <https://pop.system76.com/>`_, `Zorin OS
  <https://zorin.com/os/>`_, `KDE Neon <https://neon.kde.org/>`_

* Ubuntu packages are not compatible with Debian or any of its other
  derivatives.

The default target Ubuntu version is the latest long term support release.
Other versions can be targeted using:

* ``polycotylus ubuntu:24.04`` for Noble Numbat (long term support, default) or Linux Mint 22
* ``polycotylus ubuntu:24.10`` for Oracular Oriole (interim release)
* ``polycotylus ubuntu:25.04`` for Plucky Puffin (interim release)
* ``polycotylus ubuntu:25.10`` for Questing Quokka (interim release)

No earlier versions of Ubuntu are supported.

..
    For Ubuntu code names:

    * https://cdimage.ubuntu.com/daily-live/current/

    See the following for checking the Ubuntu base versions of derivative
    distributions:

    * https://linuxmint.com/download_all.php
    * https://zorin.com/os/details/
    * https://pop.system76.com/ (Try to download. It uses the same version numbers as Ubuntu)
    * https://neon.kde.org/faq#what-is-neon


Caveats
.......

* An extra top level ``debian`` directory is added to a temporary copy of your
  project before building it. If you are using setuptools without a ``src``
  layout and have not already set setuptools`s ``packages.find`` option then
  setuptools will refuse to build with an error like the following. ::

    I: pybuild base:240: python3.11 -m build --skip-dependency-check --no-isolation --wheel --outdir /io/build/.pybuild/cpython3_3.11_your_project
    * Building wheel...
    error: Multiple top-level packages discovered in a flat-layout: ['debian', 'your_top_level_package'].

    To avoid accidental inclusion of unwanted files or directories,
    setuptools will not proceed with this build.

    If you are trying to create a single distribution with multiple packages
    on purpose, you should not rely on automatic discovery.
    Instead, consider the following options:

    1. set up custom discovery (`find` directive with `include` or `exclude`)
    2. use a `src-layout`
    3. explicitly set `py_modules` or `packages` with a list of names

    To find more information, look for "package discovery" on setuptools docs.

  Debian's ``python3-setuptools`` package contains a special hack to prevent
  this but Ubuntu's does not. To make your project compatible with Ubuntu's
  packaging system, add the following to your ``pyproject.toml``:

  .. code-block:: toml

    [tool.setuptools.packages.find]
    include = ["your_top_level_package"]
