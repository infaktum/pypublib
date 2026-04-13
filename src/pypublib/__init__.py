"""Top-level package for pypublib.

This file exposes commonly used submodules and classes so tests and users
can import them as `from pypublib import Book` or `from pypublib.markdown import Html`.
"""

__version__ = "0.1.1"
__author__ = "Heiko Sippel"

# Use relative imports so the local package is resolved correctly when the
# project lives in a `src/` layout and tests insert `src` into sys.path.
from . import epub as epub  # noqa: F401
from .epub import read_book, publish_book  # noqa: F401
from . import book as book  # noqa: F401
from .book import Book, Chapter  # noqa: F401
from . import markdown as markdown  # noqa: F401
from .markdown import Html  # noqa: F401

# Public names exported by the package
__all__ = [
	"__version__",
	"__author__",
	"epub",
	"read_book",
	"publish_book",
	"book",
	"Book",
	"Chapter",
	"markdown",
	"Html",
]
