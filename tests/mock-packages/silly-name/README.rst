A package which:

* Contains special characters wherever possible to test name normalisation and
  special character/unicode handling. Note that non-ASCII characters are not
  allowed in filenames by Arch so this is deliberately left out.

* Utilizes all possible sources of dependencies to test that they all get
  combined together correctly.

* Uses a nonstandard name for its tests directory.

* Treats its test suite like a package rather than a collection of modules.

* Uses a custom test command to work around it's otherwise deliberately broken
  test suite.
