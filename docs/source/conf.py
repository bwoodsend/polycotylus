#!/usr/bin/env python
#
# polycotylus documentation build configuration file, created by
# sphinx-quickstart on Fri Jun  9 13:47:02 2017.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

# If extensions (or modules to document with autodoc) are in another
# directory, add these directories to sys.path here. If the directory is
# relative to the documentation root, use os.path.abspath to make it
# absolute, like shown here.
#
from pathlib import Path
from textwrap import indent
from importlib.metadata import version
import runpy

runpy.run_path("schema_to_rst.py")

# -- General configuration ---------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = "1.0"

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named "sphinx.ext.*") or your custom ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx_rtd_theme_configuration",
    "sphinx_inline_tabs",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = [".rst", ".md"]
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "polycotylus"
copyright = "2022-2023, Brénainn Woodsend"
author = "Brénainn Woodsend"

# The version info for the project you"re documenting, acts as replacement
# for |version| and |release|, also used in various other places throughout
# the built documents.
#
# The short X.Y version.
version = version("polycotylus")
# The full version, including alpha/beta/rc tags.
release = version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This patterns also effect to html_static_path and html_extra_path
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# Disable converting single quotes to backtick and forward ticks but keep double
# dash and ellipsis markup.
smartquotes_action = "De"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

with open("rst_prolog.txt", encoding="utf-8") as f:
    rst_prolog = f.read()

# Add intersphinx mappings for :class:`xxx` cross references to non-polycotylus
# docs.
intersphinx_mapping = {
    "python": ("http://docs.python.org/3", None),
}

# Autodoc defaults.
autodoc_default_options = {
    "members": True,
    "special-members": "__init__",
    "undoc-members": True,
}
autodoc_member_order = "groupwise"

# Make `foo` equivalent to :any:`foo`.
default_role = "any"

# Build the changelog from per-release fragments.
histories = sorted(
    Path("history").resolve().glob("*.rst"),
    key=lambda x: tuple(map(int, x.stem.split("."))), reverse=True)

history = """\
=========
Changelog
=========

.. role:: red
    :class: in-red

Release history for `polycotylus`.
Breaking changes are :red:`highlighted in red`.

""" + "\n".join(f"v{i.stem}\n-{'-' * len(i.stem)}\n\n"
                f".. rst-class:: spacious\n\n"
                f"{indent(i.read_text('utf8'), '    ')}" for i in histories)

history_path = Path("history.rst")
if (not history_path.exists()) or history_path.read_text("utf8") != history:
    history_path.write_text(history, "utf-8")

# -- Options for HTML output -------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.

html_theme = "sphinx_rtd_theme"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["static"]


def setup(app):
    app.add_css_file("theme-overrides.css")
    app.add_css_file("dark-theme.css")


html_favicon = 'static/favicon.png'
