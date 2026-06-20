"""
Pytest configuration and fixtures for CLI tests.
"""

import os
from unittest.mock import patch

import pytest

# Phase 216.X.3 — surface the cleanup_registry autouse fixture and the
# persona teardown plumbing to every test under cli/tests/. The fixture
# is defined in tests/fixtures/cleanup_registry.py but pytest only
# auto-discovers fixtures declared in conftest.py modules, so we
# re-export it here. (F401 is intentional: the import IS the wiring.)
from tests.fixtures.cleanup_registry import (  # noqa: F401
    cleanup_registry,
    drain_persona_teardown_callbacks,
)


def pytest_sessionfinish(session, exitstatus):
    """Phase 216.X.3 layer 2 — drain any persona teardown callbacks left
    over after the session ends.

    Persona-provisioning helpers register a teardown callback at the
    moment they provision a persona; this hook fires once at the end of
    the session and runs every callback in LIFO order, even if a test
    crashed mid-flight. Failures are collected and surfaced via the
    session exit status so a broken teardown does not silently leak.
    """
    failures = drain_persona_teardown_callbacks()
    if failures:
        # Don't override an existing non-zero exitstatus; only mark
        # failure if the session was otherwise green.
        if exitstatus == 0:
            session.exitstatus = 1
        for name, exc in failures:
            session.config.get_terminal_writer().line(
                f"[Phase 216 persona teardown] {name}: {exc!r}"
            )


# ── Optional Django bootstrap ──────────────────────────────────────────────
# The CLI test suite is designed to run standalone (without Django), but some
# test files import Django models to verify cross-package contracts.  When
# Django *is* available in the environment we configure it early so those
# tests don't have to set up settings themselves.
#
# We distinguish three outcomes:
#  1. Django not installed          → skip silently (standalone CLI mode)
#  2. Django installed + config OK  → proceed with Django available
#  3. Django installed + config bad → surface the error (it's a real bug)
try:
    import django
except ImportError:
    django = None  # type: ignore[assignment]

if django is not None:
    # Only configure if not already configured (e.g. by pytest-django)
    from django.conf import settings

    if not settings.configured:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
        try:
            django.setup()
        except RuntimeError as exc:
            # Django raises RuntimeError when setup() is called a second
            # time (e.g. pytest-django already called it).  That is safe.
            # Any *other* exception during setup is a real configuration
            # error and MUST propagate.
            if "populate()" not in str(exc):
                raise


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    # Patch the config paths at module level
    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file


@pytest.fixture
def mock_config(temp_config_dir):
    """Create a config instance (uses real Config, not a mock)"""
    from datahub_cli.config import config

    return config


@pytest.fixture
def mock_api_client():
    """Create a mock API client"""
    with patch("datahub_cli.api_client.api_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_auth_manager():
    """Create a mock auth manager"""
    with patch("datahub_cli.auth.auth_manager") as mock_auth:
        mock_auth.ensure_authenticated.return_value = True
        mock_auth.get_auth_headers.return_value = {
            "Authorization": "Bearer test-token",
            "Content-Type": "application/json",
        }
        yield mock_auth


@pytest.fixture
def sample_asset():
    """Sample asset data"""
    return {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "name": "Test Asset",
        "key": "test-asset",
        "status": "DRAFT",
        "domain": "test",
        "visibility": "INTERNAL",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_contract():
    """Sample contract data"""
    return {
        "id": "223e4567-e89b-12d3-a456-426614174000",
        "version": 1,
        "status": "DRAFT",
        "asset_id": "123e4567-e89b-12d3-a456-426614174000",
        "original_spec_type": "ODCS",
        "original_format": "YAML",
        "normalization_status": "NORMALIZED_OK",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_file():
    """Sample file data"""
    return {
        "id": "323e4567-e89b-12d3-a456-426614174000",
        "name": "test.csv",
        "size": 1024,
        "status": "UPLOADED",
        "content_type": "text/csv",
        "created_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_job():
    """Sample job data"""
    return {
        "id": "423e4567-e89b-12d3-a456-426614174000",
        "type": "DQ_RUN",
        "status": "PENDING",
        "resource_type": "DATASET",
        "resource_id": "123e4567-e89b-12d3-a456-426614174000",
        "created_at": "2025-01-01T00:00:00Z",
    }
