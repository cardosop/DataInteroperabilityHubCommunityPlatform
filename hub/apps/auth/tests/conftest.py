"""Auth app tests — MVP CI marker for all tests in this tree (incl. unittest.TestCase)."""

from __future__ import annotations

from pathlib import Path

import pytest

_MVP_TESTS_ROOT = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items) -> None:
    for item in items:
        p = getattr(item, "path", None)
        if p is None:
            continue
        try:
            p.resolve().relative_to(_MVP_TESTS_ROOT)
        except ValueError:
            continue
        item.add_marker(pytest.mark.mvp)
