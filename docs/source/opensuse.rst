=====================
Building for OpenSUSE
=====================

Basic usage::

    polycotylus opensuse

Supported architectures: ``aarch64 x86_64`` (but cross architecture building is
not recommended or tested due to it taking an hour to build hello world!)

The packages `polycotylus` builds will run on Tumbleweed only. Adding support
for Leap will require that OpenSUSE follow through on `their proposal
<https://en.opensuse.org/openSUSE:Packaging_Python#Python_3_(Leap_Future)>`_ to
build packages for a recent (and non end of life!) version of Python and for
``python3-setuptools >= 61.0`` to reach Leap's repositories.


Target Python versions
......................

OpenSUSE Tumbleweed supports many minor versions of Python:

* One version of Python, roughly in the middle of the available non-EOL versions
  range, has all Python packages built for it.
* Two neighbouring versions (usually the one above and the one below) have
  libraries but not frontend tools built for them (although don't ask me what
  the purpose of a library is if it won't be serving a front end tool 🤔).
* Another two versions above or below (possibly including a beta release or end
  of life Python) are available but have no packages built for them – not even
  ``pip``!

If you have `frontend` mode on, `polycotylus` will build one package. Otherwise,
you'll get three.


.. _opensuse_caveats:

Caveats
.......

* Building for OpenSUSE is not supported with Podman_.
