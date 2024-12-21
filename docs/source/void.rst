=======================
Building for Void Linux
=======================

Basic usage::

    polycotylus void

Supported architectures: ``aarch64 armv6l armv7l x86_64``


libc implementation
...................

Void Linux comes in two flavours – one where all packages are linked against
glibc_ and the other linked against musl_. Build for each using::

    polycotylus void:glibc  # The default, equivalent to `polycotylus void`
    polycotylus void:musl


Package Signing
...............

Void Linux packages use a detached RSA signature. To generate an RSA key run either::

    openssl genrsa -des3 -out privkey.pem 4096

Or if you want builds to be automatable, generate a password-less key using::

    openssl genrsa -out privkey.pem 4096

Then to build a package with signing enabled, pass the path to the private key
to the ``--void-signing-certificate`` option::

    polycotylus void --void-signing-certificate privkey.pem

There are several files of interest produced:

.. code-block:: console

    $ tree .polycotylus/void
    .polycotylus/void
    ├── 64:0c:81:d1:54:d6:6d:88:b4:49:4a:4e:c6:0a:1c:26.plist  (1)
    ├── Dockerfile
    ├── hostdir
    │   └── sources
    │       └── dumb_text_viewer-0.1.0
    │           └── 0.1.0.tar.gz
    ├── musl
    │   ├── dumb_text_viewer-0.1.0_1.x86_64-musl.xbps          (2)
    │   ├── dumb_text_viewer-0.1.0_1.x86_64-musl.xbps.sig2     (3)
    │   └── x86_64-musl-repodata                               (4)
    └── srcpkgs
        └── dumb_text_viewer
            └── template

1. Your public key, in the format that XBPS uses
2. The package itself
3. The detached signature for the package
4. The repository index, containing an embedded signature


To consume a package
--------------------

The preferred way for a user to import your public key is just to install a
signed package, which will display the signing key's fingerprint and ask if the
user wants to import the key. That fingerprint is the basename of the
``.polycotylus/void/{md5sum}.plist`` file – put that fingerprint somewhere
downloaders of your package can find it and know that it belongs to you.

An automation friendly, albeit rarely used alternative is to copy the public key
into XBPS's key-store. Do this simply by having the user put the
``{md5sum}.plist`` file into their ``/var/db/xbps/keys/`` directory.
