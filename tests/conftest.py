"""Pytest bootstrap: make the repo-root modules importable from tests/.

pytest's default (prepend) import mode puts the *tests* directory on sys.path,
not the repo root, so top-level modules (PassGenerator, WordlistFixer, modules/)
would not import without this.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
