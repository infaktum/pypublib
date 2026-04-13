
"""Ensure test package `pypublib` delegates submodule imports to `src/pypublib`.

Pytest imports this directory as package `pypublib` during collection, which can
shadow the real implementation package. Extending this package path lets imports
like `from pypublib.book import Chapter` resolve to `src/pypublib/book.py`.
"""

import os

HERE = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC_PKG_DIR = os.path.join(PROJECT_ROOT, "src", "pypublib")

if os.path.isdir(SRC_PKG_DIR) and SRC_PKG_DIR not in __path__:
    __path__.append(SRC_PKG_DIR)

