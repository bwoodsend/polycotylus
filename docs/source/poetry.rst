.. _poetry_support:

=====================
Poetry based projects
=====================

Poetry_ is different from other Python packaging tools such as setuptools_ in
that its configuration does not follow :pep:`621`. If `polycotylus` sees a
`tool.poetry <https://python-poetry.org/docs/pyproject/>`_ section in your
``pyproject.toml`` then `polycotylus` will read package metadata from there
instead of the usual ``project`` section.


Dependency constraints
......................

Poetry very aggressively (and very disruptively) steers you down the path of
putting arbitrary lower and upper version constraints in the ``pyproject.toml``.
But distribution package managers :ref:`don't allow version constraints
<dependency_locking>`!

If you truly need tight control over your dependency versions then your code is
unsuitable for Linux packaging (a static bundle using PyInstaller or AppImage
would be the best you can do). To be compatible with Linux packaging, remove
upper bound constraints and widen lower bound constraints as much as possible
without your package breaking.

Since `polycotylus` can't do anything meaningful with them, it currently assumes
that all your dependency constraints are not real requirements (found by testing
or looking at changelogs) and ignores them where it can. This is not possible on
Fedora. If you get an error like the one below, it means that your version
constraints are too fussy – you will need to relax them or you won't be able to
build for that Fedora release. ::

    error: Failed build dependencies:
      (python3dist(filelock) < 4~~ with python3dist(filelock) >= 3) is needed by python3-poetry-based-0.1.0-1.fc38.noarch
    Wrote: /io/python3-poetry-based-0.1.0-1.fc38.buildreqs.nosrc.rpm
    Could not execute compile: Failed to execute command.
