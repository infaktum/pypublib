# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import datetime

# Add project root and src to sys.path so autodoc can import the packages
sys.path.insert(0, os.path.abspath(os.path.join('..', 'src')))

# -- Project information -----------------------------------------------------
project = 'PyPubLib'
author = 'Heiko Sippel'
copyright = f"{datetime.now().year}, {author}"

# The full version, including alpha/beta/rc tags
release = '0.1.0'

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # <-- enable Google/NumPy style docstrings
    'sphinx.ext.viewcode',
]

# Allow Markdown files (README.md) to be used as Sphinx source files by
# enabling the MyST parser extension and adding .md to source suffixes.
extensions.append('myst_parser')

# Recognize both reStructuredText and Markdown source files
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
# Napoleon settings: keep defaults but allow both NumPy and Google styles
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True

# Templates path
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------

# Use a nicer theme (ReadTheDocs theme). Requires the `sphinx_rtd_theme`
# package to be installed in the environment.
try:
    import sphinx_rtd_theme  # type: ignore

    html_theme = 'sphinx_rtd_theme'
    # newer sphinx_rtd_theme versions do not require setting html_theme_path;
    # calling get_html_theme_path is deprecated — Sphinx will find the theme
    # automatically when the package is installed.
except Exception:
    # Fallback to the default theme if the package is not available.
    html_theme = 'alabaster'

html_static_path = ['_static']

autodoc_typehints = 'description'

# When building docs on CI (or locally without all optional deps) some modules
# like `pygame` are not available and cause autodoc import errors. Mock them
# so the documentation build succeeds without installing heavy optional deps.
autodoc_mock_imports = ['pygame']
