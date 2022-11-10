======================================
Dependency locking/Reproducible builds
======================================

It's a common practice in Python, and even more so in other languages such as
Java, to do at least one of the following:

1.  Pin all dependencies to known working versions to avoid breaking changes or
    regressions in dependencies.

2.  Pin all dependencies so that builds are bit-for-bit reproducible. An
    artifact on one machine can be rebuilt identically on another.

3.  Add upper bound version constraints (e.g. ``package<3.0`` or
    ``package~=2.2``) to block usage with potentially breaking unreleased
    versions of dependencies or *just to be on the safe side*.

The majority of Linux distributions are *rolling builds* meaning that only the
latest version of each package is available - the previous version being deleted
as soon as a new one comes out. Practices 1 and 2 are therefore impossible since
the package would almost never be installable and practice 3 would lead to a
package that can only be installed when its latest release is newer than that of
all its dependencies.

For these reasons, any kind of version constraint which could block use with the
latest version of another package is disallowed by most Linux repositories and
therefore by `polycotylus`.
