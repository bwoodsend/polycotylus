=======================
Prerequisites checklist
=======================

#.  Your source code is stored in a git repository and, if this project is to be
    submitted to public repositories, is hosted by some service that allows you
    to download the repo at any given commit in ``.tar.gz`` format without
    credentials or SSH keys. GitHub, GitLab, Gerrit and Sourceforge are all such
    suitable hosts.

#.  Your project should be a ``pip install``-able Python distribution as if it were
    going to be uploaded to PyPI -- certainly not the usual assortment of
    ``.py`` files arranged in some imitation of a Java or C++ project layout
    with a ``requirements.txt`` that is so often misasumned to be proper Python
    packaging! See the `Python packaging tutorial
    <https://packaging.python.org/en/latest/tutorials/packaging-projects/>`_ for
    how this is done.

#.  All your dependencies, including build and test dependencies must already be
    available on each Linux distribution's package repositories. Very few Linux
    distributions support either vendoring unavailable dependencies or mixing
    system package managers with pip and none of them do it well so
    `polycotylus` does not allow them either.

#.  Core metadata is stored using the :pep:`621` `pyproject.toml
    <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/>`_
    rather than the legacy ``setup.py`` or ``setup.cfg`` files. `polycotylus`
    expects to find:

    - `name <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#name>`_
    - `version <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#version>`_
    - `description <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#description>`_ (a short one-line variant)
    - `dependencies <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#dependencies-optional-dependencies>`_
    - `urls <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#urls>`_

#.  Your package should have a fully autonomous test suite.

#.  The package must not write into its own installation directory at runtime.
    This is important because, since the installation directory will be owned by
    root, it won't be writable. This applies to settings, caches, logs, implicit
    working state dumps, dynamically generated resources or anything else that
    would violate the immutability of the package.  ::

      from pathlib import Path
      # This bad - it will lead to permission errors!
      settings = Path(__file__).with_name("settings.json")
      # This is better.
      settings = Path.home() / ".config" / "my-application" / "settings.json"
      # This is best since it will respect $XDG_CONFIG_HOME.
      settings = Path(appdirs.user_config_dir("my-application"), "settings.json")


When anything goes wrong in `polycotylus`, you'll by up to your neck in docker
containers where you'll have limited ability to debug and any adjustments you
make will require a rebuild to propagate. It's therefore encouraged that you
flush out non `polycotylus` related packaging errors (usually data file
collection related) outside of `polycotylus` by doing a one-off manual dummy run
through the flows in a clean virtual environment (e.g. using `venv`).
Polycotylus's internal workflow essentially boils down to the generic steps
below. If you can make it through them without it going pear-shaped then
`polycotylus` *should* behave itself too.
::

    curl -L https://github.com/your/project/archive/refs/tags/version.tar.gz | tar xz
    cd project-version
    pip install .
    pip install your test requirements
    rm -rf src
    pytest

If your project already has continuous integration (CI/CD) set up, then you can
skip the above since CI/CD will be doing it already.
