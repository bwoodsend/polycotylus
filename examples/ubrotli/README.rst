==============================
ubrotli Python library example
==============================

An example Python library.
This library is deliberately designed to be awkward to distribute in the
following ways:

* It's not pure Python. In fact it's completely written in C making ``gcc`` and
  the headers for libc and Python build time dependencies.
* It dynamically links against the C port of Google's brotli_ library making
  brotli's development headers build time dependencies and brotli's runtime
  libraries runtime dependencies, both of which are to be provided by a Linux
  distribution's package manager rather than ``pip``.

.. _brotli: https://github.com/google/brotli/


The library itself is a simple compression library analogous to the compression
libraries available as part of the standard library (zlib, gzip, bz2 and lzma)
but using the brotli compression algorithm. It's usage is as follows:

.. code-block:: python

    import ubrotli
    data = b"low entropy data\n" * 100
    compressed = ubrotli.compress(data)
    >>> compressed
    b'\x1b\xa3\x06\xf8Eo\xf8{\xae\xdd\xef\x8aO&)\t\x07\x03\x84\x9bL\x1d\xa2v\xd4\x0f\xe7\xd2\x00'
    >>> ubrotli.decompress(compressed)
    b'low entropy data\nlow entropy data\nlow entropy data\nlow entropy data\nlow entropy data\nlow entropy data\nlow entropy data...'


Note that there is a `proper Python port <https://pypi.org/project/Brotli/>`_ of
brotli_ for Python already.
Please use that instead of this wimpy knock-off example project for anything
serious.
