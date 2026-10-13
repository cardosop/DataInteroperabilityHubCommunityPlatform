"""W7.1 (oss-release-remediation R2-M1) — root-conftest collection-gate pins.

The shipped conftest ignores paid-importing test modules in core mode.
W7.1 narrowed the ignore pattern from ``^\\s*(from|import)`` to column-0
only: a GUARDED import is indented (try/except, is_core_only branch),
so guarded test modules now COLLECT in core/public runs and their
guards degrade or skip at run time — the guard work actually runs in
the public CI instead of being collected away.

No mocks: the REAL conftest module is loaded from the repo root and the
REAL ``pytest_ignore_collect`` is exercised with temp files.  (Loading
the conftest without Django is safe: its django.setup() is wrapped in
``try/except Exception``.)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFTEST = REPO_ROOT / "conftest.py"

spec = importlib.util.spec_from_file_location("root_conftest_w71", CONFTEST)
conftest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(conftest)


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(source)
    return path


UNGUARDED = "from hub.apps.semantic.models import Thing\n\n\ndef test_x():\n    pass\n"
GUARDED = (
    "try:\n"
    "    from hub.apps.semantic.models import Thing\n"
    "except (RuntimeError, ModuleNotFoundError):\n"
    "    Thing = None\n\n\ndef test_y():\n    pass\n"
)
BRANCH_GUARDED = (
    "if not getattr(settings, 'HUB_CORE_ONLY', False):\n"
    "    from hub.apps.billing.models import Subscription\n\n\ndef test_z():\n    pass\n"
)
CLEAN = "def test_clean():\n    pass\n"


@pytest.fixture(autouse=True)
def _core_mode_on(monkeypatch):
    monkeypatch.setenv("HUB_CORE_ONLY", "1")
    conftest._SOURCE_CACHE.clear()


@pytest.fixture
def _core_mode_off(monkeypatch):
    monkeypatch.delenv("HUB_CORE_ONLY", raising=False)
    conftest._SOURCE_CACHE.clear()


class TestCollectionGate:
    def test_column0_unguarded_import_is_ignored(self, tmp_path):
        path = _write(tmp_path, "test_unguarded.py", UNGUARDED)
        assert conftest.pytest_ignore_collect(path, config=None) is True

    def test_indented_guarded_import_collects(self, tmp_path):
        path = _write(tmp_path, "test_guarded.py", GUARDED)
        assert conftest.pytest_ignore_collect(path, config=None) is False

    def test_branch_guarded_import_collects(self, tmp_path):
        path = _write(tmp_path, "test_branch_guarded.py", BRANCH_GUARDED)
        assert conftest.pytest_ignore_collect(path, config=None) is False

    def test_clean_module_collects(self, tmp_path):
        path = _write(tmp_path, "test_clean.py", CLEAN)
        assert conftest.pytest_ignore_collect(path, config=None) is False

    @pytest.mark.usefixtures("_core_mode_off")
    def test_full_mode_never_ignores(self, tmp_path):
        path = _write(tmp_path, "test_unguarded.py", UNGUARDED)
        assert conftest.pytest_ignore_collect(path, config=None) is None

    def test_non_test_modules_never_ignored(self, tmp_path):
        path = _write(tmp_path, "helper.py", UNGUARDED)
        assert conftest.pytest_ignore_collect(path, config=None) is None

    def test_non_python_files_never_ignored(self, tmp_path):
        path = _write(tmp_path, "test_data.json", "not python")
        assert conftest.pytest_ignore_collect(path, config=None) is None
