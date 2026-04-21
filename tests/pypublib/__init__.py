"""Test-package bridge for `pypublib`.

Pytest imports this package because the tests live in a folder named
`pypublib`. To avoid shadowing the real implementation in `src/`, this module
provides the package-level logger helpers and loads the implementation modules
from `src/pypublib` under their public names.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional

__version__ = "0.1.1"
__author__ = "Heiko Sippel"

logger = logging.getLogger("pypublib")
if not logger.handlers:
    logger.addHandler(logging.NullHandler())

_initialized: bool = False
_config: Dict[str, Any] = {}


def get_logger(name: str):
    """Return a logger within the `pypublib` namespace.

    Args:
        name: Logger name or dotted module name.

    Returns:
        logging.Logger: Logger instance in the `pypublib` namespace.
    """
    if isinstance(name, str) and name.startswith("pypublib"):
        return logging.getLogger(name)
    return logging.getLogger(f"pypublib.{name}")


def init(
        settings: Optional[Dict[str, Any]] = None,
        *,
        log_level: Optional[int] = None,
) -> Dict[str, Any]:
    """Initialize lightweight package state for tests and runtime imports.

    Args:
        settings: Optional configuration dictionary.
        log_level: Optional logging level to apply to the package logger.

    Returns:
        Dict[str, Any]: A copy of the resolved configuration.
    """
    global _initialized, _config

    cfg = dict(settings or {})
    if log_level is not None:
        logger.setLevel(log_level)
        cfg["log_level"] = log_level

    _config = cfg
    _initialized = True
    return _config


def is_initialized() -> bool:
    """Return whether :func:`init` has been called."""
    return _initialized


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent.parent
SRC_PKG_DIR = PROJECT_ROOT / "src" / "pypublib"


def _load_public_module(module_name: str):
    """Load a public submodule from the real package in `src/`.

    Args:
        module_name: Base module name, for example ``"book"`` or ``"epub"``.

    Returns:
        module: The imported module object.
    """
    fullname = f"pypublib.{module_name}"
    module = sys.modules.get(fullname)
    if module is not None:
        setattr(sys.modules[__name__], module_name, module)
        return module

    path = SRC_PKG_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(fullname, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {fullname!r} from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(fullname, None)
        raise

    setattr(sys.modules[__name__], module_name, module)
    return module


chapter = _load_public_module("chapter")
book = _load_public_module("book")
epub = _load_public_module("epub")
markdown = _load_public_module("markdown")

from pypublib.book import Book
from pypublib.chapter import Chapter
from pypublib.epub import publish_book, read_book
from pypublib.markdown import Html

__all__ = [
    "__version__",
    "__author__",
    "logger",
    "get_logger",
    "init",
    "is_initialized",
    "epub",
    "read_book",
    "publish_book",
    "chapter",
    "book",
    "Book",
    "Chapter",
    "markdown",
    "Html",
]
