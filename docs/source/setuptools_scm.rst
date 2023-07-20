.. _setuptools_scm_support:

=============================
Projects using setuptools_scm
=============================

`polycotylus` supports projects using `setuptools_scm
<https://github.com/pypa/setuptools_scm/>`_ to dynamically extract version
information from git tags.

Some things to be aware of:

* Only `setuptools_scm configuration via the pyproject.toml
  <https://github.com/pypa/setuptools_scm/#pyprojecttoml-usage>`_ is supported.

* You will need to install ``setuptools_scm`` into the same environment that
  `polycotylus` is installed in.

* Linux distributions only ubiquitously support simple numerical versions
  meaning that `polycotylus` will have to strip the elaborate development
  suffixes that ``setuptools_scm`` provides. i.e. Instead of
  ``5.7.1.dev11+g2fe4237.d20230818`` you will just get ``5.7.1``.

* And the usual caveat that in a shallow git clone without the tags fetched
  (most common on CI/CD), `polycotylus` won't be able to get the version any
  more that ``setuptools_scm`` can. The ``SETUPTOOLS_SCM_PRETEND_VERSION``
  environment variable override can be used in this case.
