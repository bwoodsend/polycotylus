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

Poetry very aggressively (and in my opinion, very foolishly) steers you down the
path of putting arbitrary lower and upper version constraints in the
``pyproject.toml``. But :ref:`version constraints are not allowed
<dependency_locking>`!

`polycotylus` assumes (currently unconfigurably) that all your dependency
constraints are not real requirements found by testing or looking at changelogs
and ignores them where it can. This is not possible on Fedora. If you get an
error like the one below, it means that your version constraints are too fussy –
you will need to relax them or you won't be able to build for that Fedora
release. ::

    error: Failed build dependencies:
      (python3dist(filelock) < 4~~ with python3dist(filelock) >= 3) is needed by python3-poetry-based-0.1.0-1.fc38.noarch
    Wrote: /io/python3-poetry-based-0.1.0-1.fc38.buildreqs.nosrc.rpm
    Could not execute compile: Failed to execute command.
