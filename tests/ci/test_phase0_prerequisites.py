"""
Phase 0 — Prerequisites and Environment (config-only checks).

Verifies tasks 0.3 from testsfix1/tasks.md:
- DJANGO_SETTINGS_MODULE=hub.settings (in pytest.ini and at runtime)
- PYTHONPATH set from repo root (documented; runtime check when running tests)
- pytest.ini and tests/conftest.py in place

These tests run without Docker; for full Phase 0 (0.1 Docker/Compose, 0.2 service health)
run scripts/verify_phase0_prerequisites.sh from repo root.

No mocks/stubs; real file and config checks only.
"""

import configparser
import os
from pathlib import Path

import pytest

# Repo root: tests/ci/test_phase0_prerequisites.py -> parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class TestPhase0_3PytestIni:
    """Phase 0.3: pytest.ini exists and sets DJANGO_SETTINGS_MODULE=hub.settings."""

    def test_pytest_ini_exists(self):
        """pytest.ini must be present in repo root."""
        path = REPO_ROOT / "pytest.ini"
        assert path.is_file(), f"pytest.ini not found at {path}"

    def test_pytest_ini_sets_django_settings_module(self):
        """pytest.ini must set DJANGO_SETTINGS_MODULE to hub.settings."""
        path = REPO_ROOT / "pytest.ini"
        content = path.read_text()
        assert "DJANGO_SETTINGS_MODULE" in content, (
            "pytest.ini must set DJANGO_SETTINGS_MODULE"
        )
        assert "hub.settings" in content, (
            "pytest.ini must set DJANGO_SETTINGS_MODULE=hub.settings (or equivalent)"
        )

    def test_pytest_ini_parseable(self):
        """pytest.ini [pytest] section should be parseable and contain expected key."""
        path = REPO_ROOT / "pytest.ini"
        parser = configparser.ConfigParser()
        parser.read(path)
        assert "pytest" in parser.sections(), "pytest.ini should have [pytest] section"
        # Django uses this; may be under [pytest] as key
        found = False
        if parser.has_option("pytest", "DJANGO_SETTINGS_MODULE"):
            found = parser.get("pytest", "DJANGO_SETTINGS_MODULE").strip() == "hub.settings"
        if not found:
            raw = path.read_text()
            found = "hub.settings" in raw and "DJANGO_SETTINGS_MODULE" in raw
        assert found, "pytest.ini must set DJANGO_SETTINGS_MODULE = hub.settings"


class TestPhase0_3Conftest:
    """Phase 0.3: tests/conftest.py in place."""

    def test_conftest_py_exists(self):
        """tests/conftest.py must exist."""
        path = REPO_ROOT / "tests" / "conftest.py"
        assert path.is_file(), f"tests/conftest.py not found at {path}"


class TestPhase0_3RuntimeEnv:
    """Phase 0.3: runtime environment when tests run (no mocks). Run with full test env (e.g. in CI or script)."""

    def test_django_settings_module_set_at_runtime(self):
        """When pytest runs, DJANGO_SETTINGS_MODULE should be hub.settings."""
        val = os.environ.get("DJANGO_SETTINGS_MODULE")
        assert val == "hub.settings", (
            f"DJANGO_SETTINGS_MODULE must be hub.settings when running tests (got {val!r}). "
            "Set it in pytest.ini or export before pytest."
        )

    def test_repo_root_on_path(self):
        """Repo root must be on sys.path so 'hub' is importable (PYTHONPATH or cwd)."""
        import sys

        repo_str = str(REPO_ROOT)
        resolved_root = REPO_ROOT.resolve()
        for p in sys.path:
            if not p:
                continue
            try:
                if Path(p).resolve() == resolved_root or p == repo_str:
                    return
            except (OSError, RuntimeError):
                continue
        pythonpath = os.environ.get("PYTHONPATH", "")
        assert False, (
            f"Repo root {REPO_ROOT} must be on sys.path (set PYTHONPATH from repo root or run pytest from repo root). "
            f"PYTHONPATH={pythonpath or '(not set)'}"
        )


class TestPhase0_3ComposeFile:
    """Phase 0.1 alignment: docker-compose.test.yml present (config-only)."""

    def test_docker_compose_test_yml_exists(self):
        """docker-compose.test.yml must be present for Phase 0.1."""
        path = REPO_ROOT / "docker-compose.test.yml"
        assert path.is_file(), f"docker-compose.test.yml not found at {path}"
