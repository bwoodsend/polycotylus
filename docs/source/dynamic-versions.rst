.. _dynamic_versions_support:

===============================
Projects using dynamic versions
===============================

`polycotylus` needs to be know your project's version. Unfortunately there are
an almost infinite number of ways to avoid writing the project version in the
nicely standardised and machine readable ``project.version`` ``pyproject.toml``
field.

If your project is one of those then use the `dynamic_version` field of the
`polycotylus.yaml` to tell `polycotylus` how to get the version. This field
takes the body of a parameter-less Python function whose return value is the
version.


Typical examples
----------------

Version is defined as a ``__version__`` attribute:

.. code:: yaml

    dynamic_version: |
      import re
      with open("bagpuss/__init__.py") as f:
          return re.search("__version__ = ['\"](.+)['\"]", f.read())[1]

Version is defined in a *version file*:

.. code:: yaml

    dynamic_version: |
      with open("bagpuss/VERSION") as f:
          return f.read().strip()

Project uses ``setuptools_scm`` or ``hatch-vcs`` (which uses ``setuptools_scm``
under the hood):

.. code:: yaml

    dynamic_version: |
      import setuptools_scm
      return setuptools_scm.get_version(".")

Project is written in rust:

.. code:: yaml

    dynamic_version: |
      import toml
      return toml.load("Cargo.toml")["package"]["version"]


Things to note
--------------

The current working directory can be assumed to be the parent of the
`polycotylus.yaml`.

Linux distributions only ubiquitously support simple numerical versions meaning
that `polycotylus` will strip any elaborate development suffixes (most notably
the versions that ``setuptools_scm`` generates). e.g. Instead of
``5.7.1.post2.dev11+g2fe4237.d20230818.zipadeedoo`` you will just get ``5.7.1``.

The code snippet is ran by the same Python environment as `polycotylus`.
Anything it imports needs to be installed into that environment. To that end,
importing your project is allowed but discouraged.
