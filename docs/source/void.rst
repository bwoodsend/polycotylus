=======================
Building for Void Linux
=======================

Basic usage::

    polycotylus void

Supported architectures: ``aarch64 armv6l armv7l x86_64``


libc implementation
...................

Void Linux comes in two variants – one where all packages are linked against
glibc_ and the other linked against musl_. Build for each variant using the
following::

    polycotylus void:glibc  # The default, equivalent to `polycotylus void`
    polycotylus void:musl
