.. _gpg_signing:

=============
GnuPG Signing
=============

Some distributions (Arch, Fedora and Manjaro) optionally use GnuPG_ to sign
their packages. Other distributions either have their own ways of signing
(documented under :ref:`each distribution's quirks page <building for>`), or
don't meaningfully support per-package signing.

.. note::

    Here's the usual disclaimer about the inescapable bootstrap problem of end
    to end signing. If the publisher's identity (be that a public key, its
    fingerprint, an email address or even the new trendy sigstore stuff) can
    only be obtained from the same source as downloading the package, then it's
    proving nothing and is less secure than HTTPS.

To sign your packages:

* Generate an RSA signing key for yourself or your organisation using ``gpg
  --generate-key``.

* Run ``gpg --list-secret-keys`` to find the key key ID (a 40 character
  hexadecimal string) of the key you just generated.

* Pass that key ID to the ``--gpg-signing-id`` flag when building (replace
  ``arch`` with whatever distribution you're building for)::

    polycotylus arch --gpg-signing-id 3CB69E1833270B714034B7558CA85BF8D96DB4E9

If your GnuPG key has a password, you will be prompted to enter it during the
build. There is currently no automation friendly way to pass the password through
`polycotylus` to GnuPG_.

**To consume** your signed package, downstream users should install your public
key into their package manager's key stores. That process is different for each
distribution and is documented ender their :ref:`quirks pages <building for>`.
