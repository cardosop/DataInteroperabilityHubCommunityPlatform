# Contracts tests conftest — collect_ignore removed after conftest
# infrastructure patches (resilient teardown, post-flush re-seed,
# CASCADE sql_flush) resolved data isolation issues from preceding
# TransactionTestCase tests.

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
