.. _gpg_signing:

=============
GnuPG Signing
=============

Some distributions, namely Arch, Fedora and Manjaro, optionally use GnuPG_ to
sign their packages. Other distributions either use their own wrappers around
OpenSSL, for which the signing process is documented under :ref:`each
distribution's quirks page <building for>`, or don't meaningfully support
signing.

.. note::

    Before embarking on signing, bear in mind that, without a web of trust based
    or in-person public key verification, a signature is more or less a
    meaningless exercise, providing less security than HTTPS.

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

**To consume** your signed package, downstream users will need to install your
public key into their package manager's key stores. The process is different on
each distribution – consult :ref:`each distribution's quirks page <building
for>`.
