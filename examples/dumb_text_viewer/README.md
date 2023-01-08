# dumb_text_viewer Python library example

A plain-text editor so dumb that it doesn't support saving files.

This package is non-trivial to distribute on Linux because it:

* Depends on tkinter, which most Linux distributions ship in a separate package
  to Python itself.

* Is a GUI application and therefore requires display virtualization to be
  testable inside containers or other headless environments.

* Wraps its `gui-scripts` entry point with a `.desktop` file for desktop
  integration.
