.. _package_manager_cheat_sheet:

===========================
Package manager cheat sheet
===========================

In `polycotylus`, you will frequently find yourself asking the same two
questions on each Linux distribution:

1.  How do I install this local package I just built?
2.  What package provides this file/command/``libXYZ.so`` library?

This reference should answer those questions.


.. highlight:: bash

.. tab:: Alpine

    ::

        # Install packages:
        apk add py3-wheel py3-pip

        # Uninstall packages:
        apk del py3-wheel py3-pip

        # Search packages by name+description:
        apk search substring

        # Search by file:
        apk info --who-owns /usr/bin/python  # Requires that the package is already installed
        apk-file libgmp.so  # Requires apk add apk-file. Note formatting may be garbled 🙄

        # List all available packages:
        apk search -q

        # List all installed packages:
        apk info

        # Show a package's metadata:
        apk info python3

        # List a package's files:
        apk info -L python3


.. tab:: Arch/Manjaro

    ::

        # Install packages:
        pacman -S python-wheel python-pip

        # Uninstall packages:
        pacman -R python-wheel python-pip

        # Search packages by name+description:
        pacman -Ss substring

        # Search by file:
        pacman -Fyq /usr/bin/python

        # List all available packages:
        pacman -Ss

        # List all installed packages:
        pacman -Q

        # Show a package's metadata:
        pacman -Si python

        # List a package's files:
        pacman -Qlq python


.. tab:: Debian/Ubuntu

    ::

        # Install packages:
        apt-get update; apt-get install -y python3-wheel python3-pip

        # Uninstall packages:
        apt-get remove -y python3-wheel python3-pip

        # Search packages by name+description (extremely low signal to noise
        # ratio, recommend search by file or grep apt list instead):
        apt search substring

        # Search by file (requires apt-get install -y apt-file; apt-file update):
        apt-file search /usr/bin/python3

        # List all available packages:
        apt list

        # List all installed packages:
        apt list --installed

        # Show a package's metadata:
        apt show python3

        # List a package's files:
        apt-file list python3


.. tab:: Fedora

    ::

        # Install packages:
        dnf install -y python3-numpy python3-pip

        # Uninstall packages:
        dnf remove -y python3-numpy python3-pip

        # Search packages by name+description:
        dnf search substring

        # Search by file:
        dnf whatprovides /usr/bin/python
        dnf whatprovides '*/libgmp.so'

        # List all available packages:
        dnf list

        # List all installed packages:
        dnf list --installed

        # Show a package's metadata:
        dnf info python3

        # List a package's files:
        dnf repoquery -l python3


.. tab:: Void

    ::

        # Install packages:
        xbps-install -ySu python3-numpy python3-pip

        # Uninstall packages:
        xbps-remove -y python3-numpy python3-pip

        # Search packages by name+description:
        xbps-query -Rs substring

        # Search by file (requires first running ``xbps-install xtools; xlocate -S``):
        xlocate libgmp.so

        # List all available packages:
        xbps-query -Rs ''

        # List all installed packages:
        xbps-query -l

        # Show a package's metadata:
        xbps-query -R python3

        # List a package's files:
        xbps-query -Rf python3


Working with local packages
...........................

.. tab:: Alpine

    Alpine packages are gzipped tarballs (albeit with some nonstandard headers
    used for signing). For the most part, you can interact with them using the
    standard ``tar`` command.

    ::

        # Install local package
        apk add package-1.2.3-r1.apk

        # List package's contents
        tar tf package-1.2.3-r1.apk

        # Extract package's contents
        tar xf package-1.2.3-r1.apk

        # Read package's metadata
        tar xOf package-1.2.3-r1.apk .PKGINFO


.. tab:: Arch/Manjaro

    Arch packages are tarballs with `Zstandard
    <https://facebook.github.io/zstd/>`_ compression. For the most part, you can
    interact with them using the standard ``tar`` command provided that you have
    the ``zstd`` command also installed.

    ::

        # Install local package
        pacman -U --noconfirm package-1.2.3-1-any.pkg.tar.zst

        # List package's contents
        tar tf package-1.2.3-1-any.pkg.tar.zst

        # Extract package's contents
        tar xf package-1.2.3-1-any.pkg.tar.zst

        # Read package's metadata
        tar xOf package-1.2.3-1-any.pkg.tar.zst .PKGINFO


.. tab:: Debian

    ``deb`` packages are a nested archive – the top level is an `Ar archive
    <https://en.wikipedia.org/wiki/Ar_(Unix)>`_\ , inside is a
    ``control.tar.xz`` and a ``data.tar.xz`` containing the package metadata and
    payload respectively.

    ::

        # Install local package
        apt-get install -y package_1.2.3-1_all.deb

        # List package's contents
        ar pf package_1.2.3-1_all.deb data.tar.xz | tar tJ

        # Extract package's contents
        ar pf package_1.2.3-1_all.deb data.tar.xz | tar xJ

        # Read package's metadata
        ar pf package_1.2.3-1_all.deb control.tar.xz | tar xJO ./control


.. tab:: Fedora

    Fedora RPMs are a custom file format consisting of an embedded cpio archive
    (containing the files) plus some added metadata. The embedded cpio can be
    accessed via ``bsdcpio``. The metadata is untouchable without the distro
    specific ``rpm`` command.

    ::

        # Install local package
        dnf install -y package-1.2.3-1.fc38.noarch.rpm

        # List package's contents
        bsdcpio -itF package-1.2.3-1.fc38.noarch.rpm

        # Extract package's contents
        bsdcpio -idF package-1.2.3-1.fc38.noarch.rpm

        # Read package's metadata. Not possible with cross distribution tools.
        rpm --query --info package-1.2.3-1.fc38.noarch.rpm
        rpm --query --requires package-1.2.3-1.fc38.noarch.rpm


.. tab:: Ubuntu

    Ubuntu ``deb`` packages are the same as Debian packages except that the
    inner archives use Zstandard compression instead of LZMA.

    ::

        # Install local package
        apt-get install -y package_1.2.3-1_all.deb

        # List package's contents
        ar pf package_1.2.3-1_all.deb data.tar.zst | tar t --zstd

        # Extract package's contents
        ar pf package_1.2.3-1_all.deb data.tar.zst | tar x --zstd

        # Read package's metadata
        ar pf package_1.2.3-1_all.deb control.tar.zst | tar xO --zstd ./control


.. tab:: Void

    Void packages are tarballs with `Zstandard
    <https://facebook.github.io/zstd/>`_ compression. For the most part, you can
    interact with them using the standard ``tar`` command provided that you have
    the ``zstd`` command also installed. Installing a local package is slightly
    more painful than it is on other distributions because ``xbps`` does not
    support installing packages outside of repositories. You need to generate a
    local repository (which `polycotylus` does for you if you preserve the
    ``*-repodata`` file).

    ::

        # Install local package:
        # - Assuming the package and *-repodata file are in the current working directory)
        xbps-install --repository "$PWD" package
        # - Or without the *-repodata file
        xbps-rindex -a *.xbps
        xbps-install --repository "$PWD" package

        # List package's contents
        tar tf package-1.2.3_1.x86_64.xbps

        # Extract package's contents
        tar xf package-1.2.3_1.x86_64.xbps

        # Read package's metadata
        tar xOf package-1.2.3_1.x86_64.xbps ./props.plist
