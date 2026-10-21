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


def _run_django_with_env(env_overrides, timeout=120, assert_code=None):
    """Run Django settings load in subprocess. Returns (returncode, stderr).
    Timeout 120s: Django setup in test container can take 30-60s."""
    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = HUB_SETTINGS
    env["SKIP_DJANGO_SETUP"] = "1"
    env.pop("SECRET_KEY", None)
    env.pop("JWT_SECRET_KEY", None)
    env.update(env_overrides)
    if assert_code is None:
        assert_code = (
            "import django; django.setup(); from django.conf import settings; "
            "assert settings.SECRET_KEY; assert settings.JWT_SECRET_KEY"
        )
    cmd = [sys.executable, "-c", assert_code]
    result = subprocess.run(
        cmd,
        check=False,
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
        returncode, err = _run_django_with_env(
            {
                "ENVIRONMENT": "production",
                "SECRET_KEY": DEV_SECRET_KEY,
                "JWT_SECRET_KEY": "any-non-default-jwt-secret-for-test",
            }
        )
        assert returncode != 0, (
            f"Expected Django to fail when ENVIRONMENT=production and SECRET_KEY is dev default. stderr: {err}"
        )
        assert "SECRET_KEY" in err or "secret" in err.lower() or "ImproperlyConfigured" in err

    def test_production_fails_when_jwt_secret_key_is_dev_default(self):
        """When ENVIRONMENT=production and JWT_SECRET_KEY is dev default, Django must fail to start."""
        returncode, err = _run_django_with_env(
            {
                "ENVIRONMENT": "production",
                "SECRET_KEY": "any-non-default-secret-for-test",
                "JWT_SECRET_KEY": DEV_JWT_SECRET_KEY,
            }
        )
        assert returncode != 0, (
            f"Expected Django to fail when ENVIRONMENT=production and JWT_SECRET_KEY is dev default. stderr: {err}"
        )
        assert "JWT_SECRET_KEY" in err or "secret" in err.lower() or "ImproperlyConfigured" in err

    def test_production_succeeds_when_both_secrets_are_non_default(self):
        """When ENVIRONMENT=production and both secrets are set to non-default values, Django starts."""
        returncode, err = _run_django_with_env(_production_base_env())
        assert returncode == 0, (
            f"Expected Django to start when ENVIRONMENT=production and both secrets are non-default. stderr: {err}"
        )

    def test_development_allows_dev_default_secrets(self):
        """When ENVIRONMENT is not production, dev default secrets are allowed (no failure)."""
        returncode, err = _run_django_with_env(
            {
                "ENVIRONMENT": "development",
                "SECRET_KEY": DEV_SECRET_KEY,
                "JWT_SECRET_KEY": DEV_JWT_SECRET_KEY,
            }
        )
        assert returncode == 0, (
            f"Expected Django to start in development with dev default secrets. stderr: {err}"
        )


def _production_base_env(**overrides):
    """Production-shaped env that satisfies every guard except the one
    under test. Mirrors the W1.18 subprocess-boot pin convention: real
    settings import in a real subprocess — no mocks."""
    env = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "production-secret-key-at-least-50-chars-long-for-test",
        "JWT_SECRET_KEY": "production-jwt-secret-key-at-least-32-chars",
        "JWT_ALGORITHM": "HS256",
        "ENCRYPTION_KEY": ("dGVzdC1lbmNyeXB0aW9uLWtleS1mb3ItcHJvZHVjdGlvbi1ndWFyZC10ZXN0"),
        # Paid-service config validation (core/config_validation.py) refuses
        # production boot when billing/marketplace are installed — the
        # in-container subprocess inherits the container env, which lacks
        # this. Value is shape-neutral (no sk_ prefix — synthetic pins
        # never carry literal auth shapes).
        "STRIPE_SECRET_KEY": "stripe-secret-for-production-boot-guard-test",
        # The container's Redis URLs are the unauthenticated test
        # instances — production settings reject them before reaching
        # the checks under test. Supply authenticated URLs for every
        # Redis var production validates.
        "REDIS_URL": "redis://:test-auth@localhost:6379/0",
        "REDIS_CACHE_URL": "redis://:test-auth@localhost:6379/1",
        "REDIS_QUEUE_URL": "redis://:test-auth@localhost:6379/2",
        "REDIS_EVENTS_URL": "redis://:test-auth@localhost:6379/3",
        "REDIS_CHANNELS_URL": "redis://:test-auth@localhost:6379/4",
        # Remaining production guards tripped by the container env
        # (empty CORS list, placeholder semantic IRI, insecure cookie
        # defaults). Supply production-shaped values for all of them.
        "CORS_ALLOWED_ORIGINS": "https://example.com",
        "SEMANTIC_BASE_IRI": "https://example.com/semantic",
        "SESSION_COOKIE_SECURE": "true",
        "CSRF_COOKIE_SECURE": "true",
        "SECURE_SSL_REDIRECT": "true",
        # Paid-service config validation (config_validation.py) —
        # required when the paid apps are installed in production.
        "BAAS_DATABASE_URL": "postgresql://baas:baas@localhost:5432/baas",
        "BAAS_REDIS_URL": "redis://:test-auth@localhost:6379/5",
        "ODH_SERVICE_URL": "http://odh-service-test:8080",
    }
    env.update(overrides)
    return env


@pytest.mark.security
class TestCookieDomainDefaults:
    """W1.18 — cookie domains default to host-only (None), never a baked-in
    vendor domain. Explicit env config is the only way to span subdomains."""

    def test_production_cookie_domains_default_to_host_only(self):
        assert_code = (
            "import django; django.setup(); from django.conf import settings; "
            "assert settings.SESSION_COOKIE_DOMAIN is None; "
            "assert settings.CSRF_COOKIE_DOMAIN is None"
        )
        returncode, err = _run_django_with_env(
            _production_base_env(), assert_code=assert_code
        )
        # No inherited cookie-domain env from the host shell may leak in.
        assert "SESSION_COOKIE_DOMAIN" not in os.environ, (
            "Host shell exports SESSION_COOKIE_DOMAIN — pin cannot be trusted"
        )
        assert returncode == 0, (
            f"Expected production cookie domains to default to None "
            f"(host-only). stderr: {err}"
        )


def _generate_rsa_keypair():
    """Generate a real RS256 key pair (PEM) for the boot pins."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.mark.security
class TestJwtKeyPairProductionGuard:
    """W1.18 — asymmetric JWT algorithms (RS256 et al.) cannot boot in
    production without a PEM-valid key pair; a half-pair or garbage PEM
    fails closed. HS256 mode is unaffected (shared-secret JWT_SECRET_KEY
    already guarded)."""

    def test_rs256_without_keys_fails_to_boot(self):
        returncode, err = _run_django_with_env(
            _production_base_env(JWT_ALGORITHM="RS256")
        )
        assert returncode != 0, (
            f"Expected RS256 with no key pair to fail. stderr: {err}"
        )
        assert "JWT" in err or "jwt" in err.lower(), (
            f"Boot failure must name the JWT misconfig. stderr: {err}"
        )

    def test_rs256_half_pair_fails_to_boot(self):
        private_pem, public_pem = _generate_rsa_keypair()
        returncode, err = _run_django_with_env(
            _production_base_env(JWT_ALGORITHM="RS256", JWT_PRIVATE_KEY=private_pem)
        )
        assert returncode != 0, f"Expected private-only pair to fail. stderr: {err}"
        returncode, err = _run_django_with_env(
            _production_base_env(JWT_ALGORITHM="RS256", JWT_PUBLIC_KEY=public_pem)
        )
        assert returncode != 0, f"Expected public-only pair to fail. stderr: {err}"

    def test_rs256_garbage_pem_fails_to_boot(self):
        returncode, err = _run_django_with_env(
            _production_base_env(
                JWT_ALGORITHM="RS256",
                JWT_PRIVATE_KEY="not-a-pem-at-all",
                JWT_PUBLIC_KEY="also-not-a-pem",
            )
        )
        assert returncode != 0, f"Expected garbage PEM to fail. stderr: {err}"

    def test_rs256_valid_pair_boots(self):
        private_pem, public_pem = _generate_rsa_keypair()
        returncode, err = _run_django_with_env(
            _production_base_env(
                JWT_ALGORITHM="RS256",
                JWT_PRIVATE_KEY=private_pem,
                JWT_PUBLIC_KEY=public_pem,
            )
        )
        assert returncode == 0, (
            f"Expected RS256 with a valid pair to boot. stderr: {err}"
        )

    def test_hs256_without_keys_boots(self):
        returncode, err = _run_django_with_env(_production_base_env())
        assert returncode == 0, f"Expected HS256 without a pair to boot. stderr: {err}"

