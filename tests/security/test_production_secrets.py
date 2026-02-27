"""
Phase 12: Production secrets validation.

Tests that when ENVIRONMENT=production, SECRET_KEY and JWT_SECRET_KEY are not
the dev default values. Uses real env/settings via subprocess; no mocks.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Dev default values from hub/settings.py (must match exactly for assertion)
DEV_SECRET_KEY = "dev-secret-key-not-for-production"
DEV_JWT_SECRET_KEY = "dev-jwt-secret-key-not-for-production"

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
HUB_SETTINGS = "hub.settings"


def _run_django_with_env(env_overrides, timeout=120):
    """Run Django settings load in subprocess. Returns (returncode, stderr).
    Timeout 120s: Django setup in test container can take 30-60s."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = HUB_SETTINGS
    env["SKIP_DJANGO_SETUP"] = "1"
    env.pop("SECRET_KEY", None)
    env.pop("JWT_SECRET_KEY", None)
    env.update(env_overrides)
    cmd = [
        sys.executable,
        "-c",
        "import django; django.setup(); from django.conf import settings; "
        "assert settings.SECRET_KEY; assert settings.JWT_SECRET_KEY",
    ]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stderr + result.stdout


@pytest.mark.security
class TestProductionSecrets:
    """Production must not use default SECRET_KEY or JWT_SECRET_KEY."""

    def test_production_fails_when_secret_key_is_dev_default(self):
        """When ENVIRONMENT=production and SECRET_KEY is dev default, Django must fail to start."""
        returncode, err = _run_django_with_env({
            "ENVIRONMENT": "production",
            "SECRET_KEY": DEV_SECRET_KEY,
            "JWT_SECRET_KEY": "any-non-default-jwt-secret-for-test",
        })
        assert returncode != 0, (
            f"Expected Django to fail when ENVIRONMENT=production and SECRET_KEY is dev default. stderr: {err}"
        )
        assert "SECRET_KEY" in err or "secret" in err.lower() or "ImproperlyConfigured" in err

    def test_production_fails_when_jwt_secret_key_is_dev_default(self):
        """When ENVIRONMENT=production and JWT_SECRET_KEY is dev default, Django must fail to start."""
        returncode, err = _run_django_with_env({
            "ENVIRONMENT": "production",
            "SECRET_KEY": "any-non-default-secret-for-test",
            "JWT_SECRET_KEY": DEV_JWT_SECRET_KEY,
        })
        assert returncode != 0, (
            f"Expected Django to fail when ENVIRONMENT=production and JWT_SECRET_KEY is dev default. stderr: {err}"
        )
        assert "JWT_SECRET_KEY" in err or "secret" in err.lower() or "ImproperlyConfigured" in err

    def test_production_succeeds_when_both_secrets_are_non_default(self):
        """When ENVIRONMENT=production and both secrets are set to non-default values, Django starts."""
        returncode, err = _run_django_with_env({
            "ENVIRONMENT": "production",
            "SECRET_KEY": "production-secret-key-at-least-50-chars-long-for-test",
            "JWT_SECRET_KEY": "production-jwt-secret-key-at-least-32-chars",
        })
        assert returncode == 0, (
            f"Expected Django to start when ENVIRONMENT=production and both secrets are non-default. stderr: {err}"
        )

    def test_development_allows_dev_default_secrets(self):
        """When ENVIRONMENT is not production, dev default secrets are allowed (no failure)."""
        returncode, err = _run_django_with_env({
            "ENVIRONMENT": "development",
            "SECRET_KEY": DEV_SECRET_KEY,
            "JWT_SECRET_KEY": DEV_JWT_SECRET_KEY,
        })
        assert returncode == 0, (
            f"Expected Django to start in development with dev default secrets. stderr: {err}"
        )
