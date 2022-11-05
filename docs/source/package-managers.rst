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
