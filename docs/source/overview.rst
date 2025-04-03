=================
The build process
=================

The work that `polycotylus` does can be summarised as three steps. If you don't
want to read this whole page, the important takeaway is that these top level
steps are called *generate*, *build* and *test* and that steps *build* and
*test* each happen inside their own Docker containers.

1.  Generate:

    * A distribution specific build script (e.g. ``APKBUILD`` on Alpine,
      ``*.spec`` on Fedora) containing package metadata and build instructions

    * A Dockerfile defining the build and test environments

    * A source archive – ``.tar.gz`` containing all files in your local git
      repo, excluding ``.gitignore``-ed files and the ``.git`` directory

    * ``.desktop`` files (GUIs only)

2.  Build the package, using each distribution's package building system (e.g.
    `abuild <https://wiki.alpinelinux.org/wiki/Abuild_and_Helpers>`_ for Alpine,
    `fedpkg
    <https://docs.fedoraproject.org/en-US/package-maintainers/Package_Maintenance_Guide/>`_
    for Fedora). Under the hood, these tools will:

    * Run some variant of ``pip install --prefix="$build_root/usr" --no-deps
      --no-build-isolation .``

    * Compile Python bytecode

    * Convert/resize icons

    * Collect icons, ``.desktop`` and license files

    * Run your test suite – note that this is a fairly crude validation where
      the build root's ``site-packages`` is merely prepended to `PYTHONPATH` and
      ``$buildroot/bin`` is not in ``PATH``. It serves mostly just to flush out
      undeclared dependencies

    * Create the package itself

    * Maybe sign the package

    This step runs inside a *build* Docker container with
    :mod:`~dependencies.build`, :mod:`~dependencies.run` and
    :mod:`~dependencies.test` dependencies preinstalled.

3.  Test the package:

    * Install the package built in step 2

    * Run the test suite again. This is a highly realistic end to end test which
      aims to remove the need to do any more testing with the package before
      publishing it

    This step runs in a *test* Docker container with only
    :mod:`~dependencies.test` dependencies preinstalled. The process of
    installing your package will also install all its runtime dependencies.

Some key things to clarify:

* The *source archive* contains uncommitted changes in your local repository. It
  is equivalent to the archive that you would get if you ran ``git add .; git
  commit; git archive HEAD | gzip``.

* Your test suite runs twice.
