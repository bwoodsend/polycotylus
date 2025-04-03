============
Installation
============

1.  `polycotylus` is not yet on PyPI. To install directly from git use **one**
    of the following::

        pip install 'polycotylus @ git+ssh://git@github.com/bwoodsend/polycotylus.git@main'
        pip install 'polycotylus @ git+https://github.com/bwoodsend/polycotylus.git@main'

    In both commands, ``main`` can be replaced by a specific commit hash to get
    a fixed version of `polycotylus`.

2.  `polycotylus` requires Docker_ (or Podman_ but please read :ref:`building
    with Podman <podman_quirks>` before considering using Podman).

    * For Linux users, install Docker using your system package manager.  Docker
      must be `configured to run without sudo
      <https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user>`_.
      Docker's `rootless mode
      <https://docs.docker.com/engine/security/rootless/>`_ is currently
      unsupported.
    * For Windows and macOS users, consult the :ref:`Windows <windows_quirks>`
      and :ref:`macOS <macos_quirks>` guides respectively.

    Check your installation by running::

        > docker run --rm alpine echo hello
        hello

3.  (Optional) To be able to build for non-native architectures, you need
    qemu_'s ``/usr/bin/qemu-$architecture-static`` binaries installed.

    * On Linux, these are typically provided by a system package called
      ``qemu-user-static``,
    * On Windows/macOS, these come already set up with Docker Desktop.

    Check your installation by running::

        > docker run --rm --privileged multiarch/qemu-user-static --reset -p yes --credential yes
        > docker run --rm --platform=linux/ppc64le alpine uname -m
        ppc64le

4.  (Optional) If you use fish_ (the best shell ever!) instead of bash, you can
    install completions for the newly installed ``polycotylus`` command using::

        mkdir -p ~/.config/fish/completions/
        polycotylus --completion fish > ~/.config/fish/completions/polycotylus.fish

    (Pull requests implementing completions for other shells are welcome
    although, being a fish_ tribalist, I have no intention of writing them
    myself.)
