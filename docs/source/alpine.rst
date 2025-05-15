=========================
Building for Alpine Linux
=========================

Basic usage::

    polycotylus alpine

* Supported architectures: ``aarch64 armv7 ppc64le riscv64 x86 x86_64``
    - ``riscv64`` requires Alpine ``>=3.20``

* Alpine packages are compatible with: `postmarketOS
  <https://postmarketos.org/>`_

* Alpine packages are similar to but incompatible with: `Wolfi
  <https://github.com/wolfi-dev>`_

Resist the urge to build for all architectures just because you can – you're
unlikely to find a ``ppc64le`` device with a desktop on it or an ``armv7l``
device with enough processing power to run more than a light service or text
editor.

Alpine will produce up to three packages in one build:

* ``main``: Created unconditionally.

* ``doc``: Contains the license file(s). Created only if the license is
  considered *non-standard*.

* ``pyc``: Contains pre-compiled Python bytecode (a.k.a. the
  ``__pycache__/*.pyc`` files). Created for Alpine ``>=3.18`` if
  `contains_py_files` is true.

You are recommended to ship all three.


Target Alpine version
.....................

Alpine has a long term support release model. Releases are neither forwards nor
backwards compatible; i.e. to support each release, you need to build separate
packages for each one. `polycotylus` supports building for Alpine ``>=3.17``.
Specify the target version using one of the lines below. No version specifier
implies the latest released version. ::

    polycotylus alpine:3.17
    polycotylus alpine:3.18
    polycotylus alpine:3.19
    polycotylus alpine:3.20
    polycotylus alpine:3.21
    polycotylus alpine:3.22  # Default
    polycotylus alpine:edge  # Unstable branch


Package Signing
...............

Distributing Alpine packages requires signing. The signing itself is automatic
but end users will require the public key from the key pair used to do the
signing.

`polycotylus` generates a set of signing keys on the fly the first time you run
``polycotylus alpine``. These keys are stored in the (currently
non-configurable) location ``~/.abuild`` and persist between builds. Put the key
ending in ``.pub`` somewhere publicly downloadable and instruct users to run
the following **before** installing the package itself::

    sudo wget https://your-website.com/downloads/your-public-key.rsa.pub -P /etc/apk/keys/

If you're building packages on CI/CD rather than your personal machine then
import your keys into the build machine before running `polycotylus` – otherwise
each build will be signed with its own unique, random key. This can be done with
something like the following:

#.  Locally serialise the contents of your ``~/.abuild`` directory. ::

        cd ~
        tar cz .abuild/ | base64 -w0

#.  Copy/paste the output into your CI provider's secret storage.

#.  In your CI/CD jobs, pipe the secret into ``base64 -d | tar xz``.
    e.g. On GitHub Actions, you would use:

    .. code-block:: yaml

        - name: Install Alpine signing keys
          run: echo '${{ secrets.ALPINE_SIGNING_KEYS }}' | base64 -d | tar xz -C ~
