A nightmare package designed to test all the unusual, non default behaviours.

* Contains special characters wherever possible to test name normalisation and
  special character/unicode handling. Note that non-ASCII characters are not
  allowed in filenames by Arch so this is deliberately left out.

* Utilizes all possible sources of dependencies to test that they all get
  combined together correctly.

* Uses a nonstandard name for its tests directory.

* Treats its test suite like a package rather than a collection of modules
  (``from the_test_suite.constants import`` rather than ``from constants
  import``).

* Uses a custom test command to work around it's otherwise deliberately broken
  test suite.

* Uses setuptools-scm.

* Uses the key ``Homepage`` instead of ``homepage`` in the ``pyproject.toml``.

To build this package requires providing the version for setuptools-scm::

    SETUPTOOLS_SCM_PRETEND_VERSION=1.2.3 polycotylus alpine
