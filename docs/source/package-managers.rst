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
        pacman -Sy python-wheel python-pip

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


.. tab:: Fedora

    ::

        # Install packages:
        yum install -y python3-numpy python3-pip

        # Uninstall packages:
        yum remove -y python3-numpy python3-pip

        # Search packages by name+description:
        yum search substring

        # Search by file:
        yum whatprovides /usr/bin/python
        yum whatprovides '*/libgmp.so'

        # List all available packages:
        yum list

        # List all installed packages:
        yum list --installed

        # Show a package's metadata:
        yum info python3

        # List a package's files:
        yum repoquery -l python3


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
