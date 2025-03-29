=====================
Package Prerequisites
=====================

`polycotylus` is picky about what it builds. It's requirements are listed below.
There are builtin checks for most of these so feel free to skip/skim-read all
but the first two.

#.  Your source code must be in a git repository.

#.  Your project should be a ``pip install``-able Python distribution as if it were
    going to be uploaded to PyPI -- **not** just an assortment of ``.py`` files
    and a ``requirements.txt``! If you're new to creating such packages then see
    the `Python packaging tutorial
    <https://packaging.python.org/en/latest/tutorials/packaging-projects/>`_.

#.  All your dependencies, including build and test dependencies must already be
    available on each Linux distribution's package repositories. Few Linux
    distributions support either vendoring unavailable dependencies or mixing
    system package managers with pip and those that do do it very badly hence
    `polycotylus` does not support it.

#.  Core metadata is stored using the :pep:`621` `pyproject.toml
    <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/>`_
    rather than the legacy ``setup.py`` or ``setup.cfg`` files. Specifically,
    `polycotylus` expects to find:

    - `name
      <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#name>`_

    - `version
      <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#version>`_
      (or a ``[tool.setuptools_scm]`` section for :ref:`setuptools_scm based
      projects <setuptools_scm_support>`)

    - `description
      <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#description>`_
      (a short one-line variant)

    - `dependencies
      <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#dependencies-optional-dependencies>`_
      (if you have any)

    - `urls
      <https://packaging.python.org/en/latest/specifications/declaring-project-metadata/#urls>`_

    You can still use a ``setup.py`` in your project but these specific fields
    must be migrated. A special exemption is made for :ref:`poetry
    <poetry_support>`.

#.  Your package should have a fully autonomous test suite.

#.  The package must not write into its own installation directory at runtime.
    The installation directory will be owned by root and your application
    therefore will get a permission denied error if it tries to put settings,
    caches, logs, implicit working state dumps, dynamically generated resources
    or any other mutable object in there.

    .. code-block:: python

      from pathlib import Path
      # This bad - it will lead to permission errors!
      settings = Path(__file__).with_name("settings.json")
      # This is better.
      settings = Path.home() / ".config" / "my-application" / "settings.json"
      # This is best since it will respect $XDG_CONFIG_HOME.
      settings = Path(platformdirs.user_config_dir("my-application"), "settings.json")


Doing a trial run
.................

When anything goes wrong in `polycotylus`, you'll be deep inside a Docker
container where you'll have limited ability to debug and any line of code you
change will require waiting on a rebuild to propagate. If you want flush out non
`polycotylus` related packaging errors (usually data file collection related)
outside of `polycotylus` then you can do so with just a clean virtual
environment (e.g. using `venv`). Polycotylus's internal workflow essentially
boils down to the generic steps below. If you can make it through them without
trouble then `polycotylus` should be a lot easier.
::

    curl -L https://github.com/your/project/archive/refs/tags/version.tar.gz | tar xz
    cd project-version
    pip install .
    pip install your test requirements
    rm -r src
    pytest
