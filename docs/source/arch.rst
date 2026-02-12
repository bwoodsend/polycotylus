.. _arch_quirks:

=======================
Building for Arch Linux
=======================

Basic (and only) usage::

    polycotylus arch

* Supported architectures: ``x86_64``

* Arch packages are compatible with: `EndeavourOS <https://endeavouros.com/>`_,
  `Garuda Linux <https://garudalinux.org/>`_, `ArcoLinux
  <https://arcolinux.com/>`_, `BlackArch Linux <https://www.blackarch.org/>`_,
  `Archcraft <https://archcraft.io/>`_, `Athena OS <https://athenaos.org/>`_

* Arch packages are similar to but incompatible with: `Manjaro Linux
  <https://manjaro.org/>`_, `Artix Linux <https://artixlinux.org/>`_


Lifetime of a build
...................

Arch Linux is a rolling build meaning that new versions of packages containing
ABI incompatibilities (or any other incompatibilities arising from the build and
runtime environments being different) can be released at any time. One prominent
case of this is the annual increment of the Arch repositories' Python minor
version which causes the ``site-packages`` directory (e.g.
``/usr/lib/python3.11/site-packages/``) to move and your package to therefore no
longer be findable.  Pinning or downgrading dependencies is prohibited so once
this happens, all existing packages are useless. You'll need to rebuild and
release then encourage your users to run ``pacman -Syu`` (upgrade all packages)
before installing/upgrading your package in case they still have the previous
version of Python installed.


Package Signing
...............

Arch packages are optionally signed using a GnuPG_ detached signature. See the
generic :ref:`gpg_signing` guide for the signing itself.

**To consume** your signed package, downstream users will need to install your
public key into their ``pacman`` key stores. You can get your key to them in two
ways:

1. The recommended way is to upload it to Arch's preferred keyserver::

    gpg --armor --export 00553556BC1486300ACA4CC010FE6BB23466AC09
    # Copy/paste the output to http://keyserver.ubuntu.com/#submitKey

  Note that there will be around a one hour propagation delay before the next
  steps can work. Installers of your package should be instructed to import your
  key from the keyserver as follows::

    sudo pacman-key --init
    sudo pacman-key --recv-keys 00553556BC1486300ACA4CC010FE6BB23466AC09
    sudo pacman-key --lsign-key 00553556BC1486300ACA4CC010FE6BB23466AC09

2. Alternatively, you can boycott the keyserver and put the public key somewhere
   on your website. Run::

    gpg --armor --export 00553556BC1486300ACA4CC010FE6BB23466AC09 > 00553556BC1486300ACA4CC010FE6BB23466AC09.asc

  Then put the ``.asc`` file somewhere downloadable on your website, with
  instructions to your users to run::

    sudo pacman-key --init
    curl https://your.website/downloads/00553556BC1486300ACA4CC010FE6BB23466AC09.asc | sudo pacman-key --add -
    sudo pacman-key --lsign-key 00553556BC1486300ACA4CC010FE6BB23466AC09
