.. _windows_quirks:

=====================
Building from Windows
=====================

`polycotylus` supports building from (but not for!) Windows with almost complete
feature parity. See `Docker Desktop for Windows`_ to obtain a suitable Docker
installation.


.. _windows_caveats:

Caveats
.......

* Building for Fedora is not supported due to :ref:`a clash <fedora_caveats>`
  between Fedora's zchunk and the Windows file system format.
