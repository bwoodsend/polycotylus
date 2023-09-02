===============
Packaging a GUI
===============

In this tutorial, we'll be packaging a user interface application. The
application itself is fairly simple packaging-wise so it won't take us long to
get a build that passes. The interesting part will be adding desktop integration
for which we'll need to generate and install a ``.desktop`` file.


Setup
.....

First, go get the example project::

    git clone https://github.com/bwoodsend/polycotylus
    cd polycotylus/examples/dumb_text_viewer

`polycotylus` is primarily driven via a `polycotylus.yaml` file. There is a
`polycotylus.yaml` file already written – for the purposes of this exercise,
we'll reset it to an empty file so that we can explore how each line was
derived. ::

    rm polycotylus.yaml
    touch polycotylus.yaml


Before we start building, let's start with the easy bits. This package has no
special system library requirements but it does have test dependencies which are
conveniently stored in a ``test-requirements.txt`` file. Since they are test
time only requirements and are from PyPI, the dependency category is
`dependencies.test.pip`.

.. code-block:: yaml

    # polycotylus.yaml
    dependencies:
      test:
        pip: -r test-requirements.txt

Time to build! As always, I'll be building first with Alpine since its so much
quicker and easier to diagnose than the other distributions.

.. code-block:: console

    > polycotylus alpine
    ...
    >>> py3-dumb-text-viewer: Unpacking /io//py3-dumb-text-viewer-0.1.0.tar.gz...
    Processing /io/src/dumb_text_viewer-0.1.0
      Preparing metadata (pyproject.toml) ... done
    Building wheels for collected packages: dumb-text-viewer
      Building wheel for dumb-text-viewer (pyproject.toml) ... done
      Created wheel for dumb-text-viewer: filename=dumb_text_viewer-0.1.0-py3-none-any.whl size=9419 sha256=951a965ec3daa3cb9461374d408fa7e470bbe87c0b64b9930bf157cea5e5f750
      Stored in directory: /home/user/.cache/pip/wheels/c9/15/c4/afc5e962d921697b99b4f1130c249db27c19386d297ed4a80d
    Successfully built dumb-text-viewer
    Installing collected packages: dumb-text-viewer
    Successfully installed dumb-text-viewer-0.1.0
    Listing '/io/src/_build/usr/lib/'...
    Listing '/io/src/_build/usr/lib/python3.11'...
    Listing '/io/src/_build/usr/lib/python3.11/site-packages'...
    Listing '/io/src/_build/usr/lib/python3.11/site-packages/dumb_text_viewer'...
    Compiling '/io/src/_build/usr/lib/python3.11/site-packages/dumb_text_viewer/__init__.py'...
    Compiling '/io/src/_build/usr/lib/python3.11/site-packages/dumb_text_viewer/__main__.py'...
    Listing '/io/src/_build/usr/lib/python3.11/site-packages/dumb_text_viewer-0.1.0.dist-info'...
    ============================= test session starts =============================
    platform linux -- Python 3.11.4, pytest-7.3.1, pluggy-1.0.0
    rootdir: /io/src/dumb_text_viewer-0.1.0
    configfile: pytest.ini
    collected 0 items / 1 error

    =================================== ERRORS ====================================
    ______________________ ERROR collecting tests/test_ui.py ______________________
    ImportError while importing test module '/io/src/dumb_text_viewer-0.1.0/tests/test_ui.py'.
    Hint: make sure your test modules/packages have valid Python names.
    Traceback:
    /usr/lib/python3.11/importlib/__init__.py:126: in import_module
        return _bootstrap._gcd_import(name[level:], package, level)
    tests/test_ui.py:1: in <module>
        import tkinter.filedialog
    E   ModuleNotFoundError: No module named 'tkinter'
    =========================== short test summary info ===========================
    ERROR tests/test_ui.py
    !!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
    ============================== 1 error in 0.04s ===============================
    >>> ERROR: py3-dumb-text-viewer: check failed

Uh oh, `tkinter` is missing! Despite being part of Python's standard library,
most Linux distributions ship `tkinter` in a separate package to Python itself
due to its size. Less commonly `sqlite3`, the various compression libraries and
anything linked against LGPL licensed system packages are also kept separate
(see `dependencies.run.python` for the full list). Declare this dependency as
follows:

.. code-block:: yaml

    # polycotylus.yaml
    dependencies:
      run:
        python: tkinter
      test:
        pip: -r test-requirements.txt

The above configuration is sufficient for the next rebuild to pass. It's also
enough to get a working build for any other Linux distribution. Installing one
of the resultant packages will add a ``dumb_text_viewer`` executable, findable
in ``$PATH``, which launches the application. However, most users do not expect
to need to use a terminal in order to launch an application. For that, we need a
``.desktop`` file. At this point, you'll probably want to switch over to
building for your native Linux distribution (assuming it's supported) so that
you can see the results of your changes.

.. code-block:: yaml

    # polycotylus.yaml
    dependencies:
      run:
        python: tkinter
      test:
        pip: -r test-requirements.txt

    desktop_entry_points:
      dumb_text_viewer:
        Name: Dumb Text Viewer
        Exec: dumb_text_viewer %u

