============
Installation
============

1.  `polycotylus` is currently not yet on PyPI. To install directly from git use one
    of the following::

        pip install 'polycotylus @ git+ssh://git@github.com/bwoodsend/polycotylus.git@main'
        pip install 'polycotylus @ git+https://github.com/bwoodsend/polycotylus.git@main'

    In both commands, ``main`` can be replaced by a specific commit hash to get
    a fixed version of `polycotylus`.

2.  `polycotylus` requires Docker_ (or Podman_ but read :ref:`building with
    Podman <podman_quirks>` before considering using Podman).

    * For Linux users, install Docker using your system package manager.  Docker
      must be `configured to run without sudo
      <https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user>`_.
      Docker's `rootless mode
      <https://docs.docker.com/engine/security/rootless/>`_ is currently
      unsupported.
    * For Windows and macOS users, consult the :ref:`Windows <windows_quirks>`
      and :ref:`macOS <macos_quirks>` guides respectively.

    Check your installation by running::

        > docker run alpine echo hello
        hello

3.  (Optional) If you use fish_ instead of bash, you can install completions for
    the newly install ``polycotylus`` command using::

        mkdir -p ~/.config/fish/completions/
        polycotylus --completion fish > ~/.config/fish/completions/polycotylus.fish

    Pull requests implementing completions for other shells are welcome
    although, being a fish_ tribalist, I have no intention of writing them
    myself.
