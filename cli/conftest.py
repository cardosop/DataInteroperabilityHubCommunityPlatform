"""
Root-level conftest for the CLI test suite.

When pytest runs from the cli/ directory, it discovers pyproject.toml in the
project root and inserts that directory at sys.path[0].  The project root
contains its own ``tests/`` package, which shadows ``cli/tests/`` during
subpackage imports because Python's import machinery temporarily pushes the
importing module's directory onto sys.path[0], and the project root wins
over cli/ for ``import tests``.

This conftest patches ``importlib.import_module`` (which pytest uses to
load conftest and test modules) so that the project root is purged from
sys.path before every module import.
"""

import os
import sys

_CLI_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CLI_DIR)


def _repair_sys_path() -> None:
    """Remove the project root from sys.path so it can't shadow cli/tests/."""
    sys.path[:] = [p for p in sys.path if os.path.abspath(p) != _PROJECT_ROOT]
    if _CLI_DIR not in sys.path:
        sys.path.insert(0, _CLI_DIR)


# Patch importlib.import_module — pytest uses this for all conftest and test
# module imports, so we get a repair before every module load.
import importlib as _importlib

_orig_import_module = _importlib.import_module


def _patched_import_module(name: str, package: str | None = None):
    _repair_sys_path()
    return _orig_import_module(name, package=package)


_importlib.import_module = _patched_import_module
