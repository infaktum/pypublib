# Building the documentation

This folder contains Sphinx sources for the project's documentation. The
following steps show how to build the HTML documentation locally.

Prerequisites
-------------
- Python 3.8+ and pip available
- It is recommended to use a virtual environment.

Install required packages
-------------------------
PowerShell:

    python -m pip install --user --upgrade pip
    python -m pip install sphinx sphinx_rtd_theme

Generate API rst files (optional)
--------------------------------
If you added or changed modules under `src/`, regenerate the API rst files
with sphinx-apidoc:

PowerShell:

    sphinx-apidoc -o docs/api src/pyhexlib src/pyguilib --force --separate --module-first

Build the HTML documentation
----------------------------
PowerShell:

    python -m sphinx -b html docs docs/_build/html

Open the generated docs
-----------------------
Open `docs/_build/html/index.html` in your browser, or serve the folder with a
simple HTTP server:

PowerShell:

    python -m http.server --directory docs/_build/html 8000

Notes
-----
- `docs/conf.py` adds `../src` to the Python path so Sphinx can import the
  `pyhexlib` package.
- If you change docstrings, run the build again to refresh the HTML output.

