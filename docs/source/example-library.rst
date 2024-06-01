===================
Packaging a library
===================

This tutorial covers packaging an example Python library. To make it more
interesting from a packaging perspective, this particular library is written in
C and depends heavily on system packages. This makes it a very bad package to
distribute on PyPI but a very suitable one for Linux repositories.


Setup
.....

First, go get the code::

    git clone https://github.com/bwoodsend/polycotylus
    cd polycotylus/examples/ubrotli

`polycotylus` is primarily driven via a `polycotylus.yaml` file. There is a
`polycotylus.yaml` file already written – for the purposes of this exercise,
reset it to an empty file so that we can explore how each line was derived. ::

    rm polycotylus.yaml
    touch polycotylus.yaml


Building for one distribution (Alpine)
.......................................

Let's try our first build. You can start with any Linux distribution but Alpine
is by far the quickest and has the best diagnostics so I always recommend doing
your first build with Alpine. From the root of the project, run::

    polycotylus alpine

Uh oh, false start! It errored out immediately.

.. code-block:: text

    Error: Polycotylus can't determine the SPDX license type. The Trove
    classifier 'License :: OSI Approved :: Apache Software License' could refer
    to any of the SPDX codes ['Apache-1.0', 'Apache-1.1', 'Apache-2.0']. Either
    choose a more specific classifier from https://pypi.org/classifiers/ if such
    a classifier exists or choose the appropriate SPDX identifier from
    https://spdx.org/licenses/ and set it in your polycotylus.yaml as:
        spdx:
          Apache-2.0:

`polycotylus` is complaining that the license identifier given in the
``pyproject.toml`` is too vague to map to an SPDX_ license identifier.
`polycotylus` has many of these little startup checks. They are designed to be
extremely self explanatory so raise an issue if you find fixing one non-trivial.
In this *too vague license* case, we can manually check the contents of
``ubrotli``\ 's ``LICENSE`` file and see that it's specifically an Apache
version 2.0 license and since there is no *Apache version 2.0* trove classifier
on `pypi.org/classifiers <https://pypi.org/classifiers/>`_, we'll have to set
the `spdx` key in the `polycotylus.yaml` like the error suggests.

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

Let's run ``polycotylus alpine`` again and see where we get land next. After
installing some packages and producing some noise, you should find it errors out
when pip is trying to compile C extension whilst building the package.

.. code-block:: bash

    polycotylus._docker.Error: Docker command:
        $ docker run --rm --network=host --platform=linux/x86_64 -v/g/notebooks/polycotylus/examples/ubrotli/.polycotylus/alpine:/io:z -v/home/brenainn/.abuild/bwoodsend@gmail.com-63b087db.rsa:/home/user/.abuild/bwoodsend@gmail.com-63b087db.rsa:z -v/g/notebooks/polycotylus/examples/ubrotli/.polycotylus/alpine/3.20:/home/user/packages:z -t --user=1000 --ulimit nofile=1024:1048576 sha256:d9d05c5db0f32b251e94fa4996f2ab1a8526b6504b04010de9084a3e9118633f sh -ec 'abuild -f'
    returned an error:
    >>> py3-ubrotli: Building /py3-ubrotli 0.1.0-r1 (using abuild 3.11.1-r0) started Sat, 19 Aug 2023 20:32:51 +0000
    >>> py3-ubrotli: Checking sanity of /io/APKBUILD...
    >>> py3-ubrotli: Analyzing dependencies...
    >>> py3-ubrotli: Cleaning up srcdir
    >>> py3-ubrotli: Cleaning up pkgdir
    >>> py3-ubrotli: Fetching py3-ubrotli-0.1.0.tar.gz::https://pypi.io/packages/source/u/ubrotli/ubrotli-0.1.0.tar.gz
    >>> py3-ubrotli: Fetching py3-ubrotli-0.1.0.tar.gz::https://pypi.io/packages/source/u/ubrotli/ubrotli-0.1.0.tar.gz
    >>> py3-ubrotli: Checking sha512sums...
    py3-ubrotli-0.1.0.tar.gz: OK
    >>> py3-ubrotli: Unpacking /io//py3-ubrotli-0.1.0.tar.gz...
    Processing /io/src/ubrotli-0.1.0
      Preparing metadata (pyproject.toml) ... done
    Building wheels for collected packages: ubrotli
      Building wheel for ubrotli (pyproject.toml) ... error
      error: subprocess-exited-with-error

      × Building wheel for ubrotli (pyproject.toml) did not run successfully.
      │ exit code: 1
      ╰─> [14 lines of output]
          /usr/lib/python3.11/site-packages/setuptools/config/pyprojecttoml.py:66: _BetaConfiguration: Support for `[tool.setuptools]` in `pyproject.toml` is still *beta*.
            config = read_configuration(filepath, True, ignore_option_errors, dist)
          running bdist_wheel
          running build
          running build_ext
          building 'ubrotli' extension
          creating build
          creating build/temp.linux-x86_64-cpython-311
          gcc -Wsign-compare -DNDEBUG -g -fwrapv -O3 -Wall -Os -Wformat -Werror=format-security -Os -Wformat -Werror=format-security -fPIC -I/usr/include/python3.11 -c wrapper.c -o build/temp.linux-x86_64-cpython-311/wrapper.o
          wrapper.c:2:10: fatal error: brotli/decode.h: No such file or directory
              2 | #include "brotli/decode.h"
                |          ^~~~~~~~~~~~~~~~~
          compilation terminated.
          error: command '/usr/bin/gcc' failed with exit code 1
          [end of output]

      note: This error originates from a subprocess, and is likely not a problem with pip.
      ERROR: Failed building wheel for ubrotli
    Failed to build ubrotli
    ERROR: Could not build wheels for ubrotli, which is required to install pyproject.toml-based projects
    >>> ERROR: py3-ubrotli: build failed

The file it's trying to compile (``wrapper.c``) uses the ``brotli/decode.h`` and
``brotli/encode.h`` development headers which our minimal build environment does
not have. Our next step is to figure out which Alpine system package provides
those header files and declare them as build time dependencies. First, let's get
inside an Alpine container by running in *post mortem* mode (``polycotylus
alpine --post-mortem``). This will run the build again, but this time when it
fails, it will drop you into the Alpine container where you can nose around and,
in our case, interact with Alpine's ``apk`` package manager. The
:ref:`package manager cheat sheet <package_manager_cheat_sheet>` tells that we
can use ``apk-file`` to locate a file provider. ::

    /io $ sudo apk add apk-file
    (1/1) Installing apk-file (0.3.6-r19)
    Executing busybox-1.36.1-r2.trigger
    OK: 331 MiB in 84 packages
    /io $ apk-file brotli/decode.h
    FILE                           PACKAGE             BRANCH              REPOSITORY          ARCHITECTURE
    ...
    /usr/include/brotli/decode.h   brotli-dev          edge                main                x86_64
    ...

The package we're looking for is called ``brotli-dev``. If you're familiar with
Linux package managers, you probably already knew of the convention for putting
headers for C libraries in a package called ``${library}-dev`` or
``${library}-devel``. Now that we know the package, we need to declare it as the
correct kind of dependency. ``brotli-dev`` is only required at build time and
it's an Alpine system package so the correct category is
`dependencies.build.$distribution`. Add that to the `polycotylus.yaml` and
rebuild. I'm going to spoil the surprise and tell you that the next build error
will be the same but for ``Python.h`` whose package is ``python3-dev`` so that
needs to go in too:

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

    dependencies:
      build:
        alpine: brotli-dev python3-dev

Whilst we're here we might as well add the corresponding ``brotli`` runtime
dependency. Looking in the ``setup.py`` you should spot the
``extra_link_args=["-lbrotlienc", "-lbrotlidec"]`` which tells us that this
project needs a ``libbrotlienc.so`` and ``libbrotlidec.so`` to run. Using
``apk-file`` again tells us that ``brotli-libs`` is the package we want. Since
this is a runtime dependency, it goes in `dependencies.run.$distribution`:

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

    dependencies:
      build:
        alpine: brotli-dev python3-dev
      run:
        alpine: brotli-libs

Round we go again (``polycotylus alpine``). This time ``abuild`` fails trying to
run the *check stage* (our test suite) because ``pytest`` is not installed. ::

    ...
    /usr/bin/abuild: line 32: pytest: not found
    >>> ERROR: py3-ubrotli: check failed

Again, we need to declare ``pytest`` as a dependency. This time however,
``pytest`` is a *test* time dependency only, and it's a PyPI package which we'd
normally install via ``pip`` so the category is `dependencies.test.pip`.

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

    dependencies:
      build:
        alpine: brotli-dev python3-dev
      run:
        alpine: brotli-libs
      test:
        pip: pytest

Running ``polycotylus alpine`` again brings us to our next error. This time
``abuild`` has finished compiling and verifying and is finally started archiving
it all into an installer. This particular error is an unclear one::

    ...
    >>> py3-ubrotli: Entering fakeroot...
    >>> py3-ubrotli-pyc*: Running split function pyc...
    >>> py3-ubrotli-pyc*: Preparing subpackage py3-ubrotli-pyc...
    >>> ERROR: py3-ubrotli-pyc*: Missing /io/pkg/py3-ubrotli-pyc
    >>> ERROR: py3-ubrotli*: prepare_subpackages failed
    >>> ERROR: py3-ubrotli: rootpkg failed

``abuild`` is trying to separate out the bytecode (``.pyc``) files from the rest
but because this package is pure C, there are no ``.py`` files meaning that
there are no ``.pyc`` files! We need to tell `polycotylus` this so that it can
tell ``abuild`` to skip the bytecode collection stage. This is done via the
`contains_py_files` option:

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

    dependencies:
      build:
        alpine: brotli-dev python3-dev
      run:
        alpine: brotli-libs
      test:
        pip: pytest

    contains_py_files: false

The next rebuild should carry you all the way to the end where you should get a message which looks like::

    Built 1 artifact:
    main: .polycotylus/alpine/3.20/x86_64/py3-ubrotli-0.1.0-r1.apk

That's the location of your package! Notice that it's got that ``3.20`` version
number and the architecture ``x86_64`` in its path. That's because the package
we built is only compatible with Alpine v3.20.x and is compiled for ``x86_64``.
Use the following syntaxes to target other versions and architectures::

    polycotylus alpine --architecture=aarch64
    polycotylus alpine:3.17
    polycotylus alpine:3.18 --architecture=ppc64le

fish_ users should find the shell completion very supportive when exploring what
versions and architectures are available. Non fish users can consult the top of
:ref:`each distribution's "building for" page <building for>`.


Building for the second distribution (Fedora)
.............................................

Looking back at our current `polycotylus.yaml`, you can probably guess that most
of the configuration will apply to all Linux distributions but those two lines
with ``alpine`` in them are going to need equivalents for every other Linux
distribution.

Our next Linux distribution will be Fedora. Hopefully you can guess that the
build command is ``polycotylus fedora`` although we'll append the
``--post-mortem`` flag since we'll want to land ourselves in the Fedora
container when those build dependencies aren't met.

.. note::

    Windows users will have to sit this one out since building for Fedora isn't
    supported on Windows.

::

    $ polycotylus fedora --post-mortem
    ...
    Building wheels for collected packages: ubrotli
      Running command Building wheel for ubrotli (pyproject.toml)
      /usr/lib/python3.11/site-packages/setuptools/config/pyprojecttoml.py:108: _BetaConfiguration: Support for `[tool.setuptools]` in `pyproject.toml` is still *beta*.
        warnings.warn(msg, _BetaConfiguration)
      running bdist_wheel
      running build
      running build_ext
      building 'ubrotli' extension
      creating build
      creating build/temp.linux-x86_64-cpython-311
      gcc -Wsign-compare -DDYNAMIC_ANNOTATIONS_ENABLED=1 -DNDEBUG -O2 -fexceptions -g -grecord-gcc-switches -pipe -Wall -Werror=format-security -Wp,-U_FORTIFY_SOURCE,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -fstack-protector-strong -m64 -mtune=generic -fasynchronous-unwind-tables -fstack-clash-protection -fcf-protection -D_GNU_SOURCE -fPIC -fwrapv -O2 -fexceptions -g -grecord-gcc-switches -pipe -Wall -Werror=format-security -Wp,-U_FORTIFY_SOURCE,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -fstack-protector-strong -m64 -mtune=generic -fasynchronous-unwind-tables -fstack-clash-protection -fcf-protection -D_GNU_SOURCE -fPIC -fwrapv -O2 -fexceptions -g -grecord-gcc-switches -pipe -Wall -Werror=format-security -Wp,-U_FORTIFY_SOURCE,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -fstack-protector-strong -m64 -mtune=generic -fasynchronous-unwind-tables -fstack-clash-protection -fcf-protection -D_GNU_SOURCE -fPIC -fwrapv -O2 -flto=auto -ffat-lto-objects -fexceptions -g -grecord-gcc-switches -pipe -Wall -Werror=format-security -Wp,-U_FORTIFY_SOURCE,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -specs=/usr/lib/rpm/redhat/redhat-hardened-cc1 -fstack-protector-strong -specs=/usr/lib/rpm/redhat/redhat-annobin-cc1 -m64 -mtune=generic -fasynchronous-unwind-tables -fstack-clash-protection -fcf-protection -fno-omit-frame-pointer -mno-omit-leaf-frame-pointer -fPIC -I/usr/include/python3.11 -c wrapper.c -o build/temp.linux-x86_64-cpython-311/wrapper.o
      error: command 'gcc' failed: No such file or directory
      error: subprocess-exited-with-error

      × Building wheel for ubrotli (pyproject.toml) did not run successfully.
      │ exit code: 1
      ╰─> See above for output.

      note: This error originates from a subprocess, and is likely not a problem with pip.
      full command: /usr/bin/python3 /usr/lib/python3.11/site-packages/pip/_vendor/pep517/in_process/_in_process.py build_wheel /io/ubrotli-0.1.0/.pyproject-builddir/tmpy2t9fhwp
      cwd: /io/ubrotli-0.1.0
      Building wheel for ubrotli (pyproject.toml) ... error
      ERROR: Failed building wheel for ubrotli
    Failed to build ubrotli
    ERROR: Failed to build one or more wheels
    error: Bad exit status from /var/tmp/rpm-tmp.G71h13 (%build)

    RPM build errors:
        Bad exit status from /var/tmp/rpm-tmp.G71h13 (%build)
    Could not execute compile: Failed to execute command.

Like we had with Alpine, we're stuck trying to compile that piece of C code
although this time, it doesn't even have a C compiler! Fedora is a rarity in
that it doesn't have a set of *build base* packages containing the most common
build dependencies such as ``gcc`` and ``make``. Alpine has an ``alpine-sdk``
package which is assumed to be installed when running ``abuild`` which is why we
got away with not adding ``gcc`` to Alpine's build dependencies.

Some rather less clear ``yum`` queries tells us what packages we need to get
``gcc``, the ``brotli`` runtime and the ``Python`` and ``brotli`` headers (again
see :ref:`the package manager cheat sheet <package_manager_cheat_sheet>`).

.. code-block:: console

    [user@manjaro-2212 io]$ sudo yum search gcc
    Last metadata expiration check: 1:37:20 ago on Sun Aug 20 20:19:29 2023.
    ========================= Name Exactly Matched: gcc =========================
    gcc.x86_64 : Various compilers (C, C++, Objective-C, ...)
    ...
    [user@manjaro-2212 io]$ sudo yum whatprovides '*/Python.h'
    ...
    python3-devel-3.11.2-1.fc39.x86_64 : Libraries and header files needed for
                                       : Python development
    Repo        : fedora
    Matched from:
    Filename    : /usr/include/python3.11/Python.h
    ...
    [user@manjaro-2212 io]$ sudo yum whatprovides '*/brotli/decode.h'
    ...
    brotli-devel-1.0.9-11.fc39.x86_64 : Lossless compression algorithm
                                      : (development files)
    Repo        : fedora
    Matched from:
    Filename    : /usr/include/brotli/decode.h
    [user@manjaro-2212 io]$ sudo yum whatprovides '*/libbrotlienc*'
    ...
    libbrotli-1.0.9-11.fc39.x86_64 : Library for brotli lossless compression algorithm
    Repo        : fedora
    Matched from:
    Filename    : /usr/lib64/libbrotlienc.so.1
    Filename    : /usr/lib64/libbrotlienc.so.1.0.9


These are ``gcc``, ``libbrotli``, ``brotli-devel`` and ``python3-devel``.

.. code-block:: yaml

    # polycotylus.yaml
    spdx:
      Apache-2.0:

    dependencies:
      build:
        alpine: brotli-dev python3-dev
        fedora: gcc brotli-devel python3-devel
      run:
        alpine: brotli-libs
        fedora: libbrotli
      test:
        pip: pytest

    contains_py_files: false

The next ``polycotylus fedora`` run takes us to the end. ::

    Built 3 artifacts:
    debuginfo: .polycotylus/fedora/x86_64/python3-ubrotli-debuginfo-0.1.0-1.fc39.x86_64.rpm
    debugsource: .polycotylus/fedora/x86_64/python3-ubrotli-debugsource-0.1.0-1.fc39.x86_64.rpm
    main: .polycotylus/fedora/x86_64/python3-ubrotli-0.1.0-1.fc39.x86_64.rpm

You'll notice that this time, there are three packages produced. The one
labelled ``main`` is the one you'd distribute. See :ref:`building for Fedora
<fedora_quirks>` for information about the other two.

.. note::

    If you want to locate the packages that `polycotylus` builds
    programmatically, then please use the ``.polycotylus/artifacts.json`` file.
    Neither parsing the last few lines of `polycotylus`\ 's console output nor
    trying to guess the paths are likely to survive future changes to
    `polycotylus`.


The next distribution and beyond
................................

Building for the rest of the Linux distributions should follow more or less the
same steps before. We've been skipping it in this tutorial but each time you try
a new distribution, it's a good idea to check :ref:`each distribution's quirks
page <building for>`. In particular, check for a *Caveats* section that may warn
you if what you're about to do is not going to work.
