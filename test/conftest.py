import sys
import os

# Ensure the src directory is on sys.path so tests can import the package after
# the project was reorganized to put the package in `src/`.
# This mirrors the behavior of projects that use a `src` layout.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'src')

if os.path.isdir(SRC) and SRC not in sys.path:
    sys.path.insert(0, SRC)

# Optional: also add project root so tests that import test fixtures or
# examples relative to the repo can find them. If added, append it after
# `src` so the package in `src/` is preferred over the top-level folder
# named `pypublib` (which would shadow the real package).
if ROOT not in sys.path:
    sys.path.append(ROOT)

