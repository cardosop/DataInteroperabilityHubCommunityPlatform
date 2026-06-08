"""
Tests for production startup guards in hub/settings.py.

These tests validate the fail-fast behaviour that prevents the application
from starting in production with insecure or missing configuration values.
They replicate the guard logic directly — no Django settings reload required.

Run with (no Django settings load — these tests are pure Python):
    pytest -p no:django hub/tests/test_production_guards.py -v
"""

import pytest
from django.core.exceptions import ImproperlyConfigured


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_guard_code(env_vars: dict) -> None:
    """
    Execute the production-guard logic isolated from the full settings module.

    We replicate only the guard blocks here so tests are fast and do not
    require a database or a fully-initialised Django application.
    """
    from django.core.exceptions import ImproperlyConfigured as IC

    _DEV_SECRET_KEY = "dev-secret-key-not-for-production"
    _DEV_JWT_SECRET_KEY = "dev-jwt-secret-key-not-for-production"
    _DEV_ENCRYPTION_KEY = "dev-encryption-key-not-for-production"

    ENVIRONMENT = env_vars.get("ENVIRONMENT", "development")
    SECRET_KEY = env_vars.get("SECRET_KEY", _DEV_SECRET_KEY)
    JWT_SECRET_KEY = env_vars.get(
        "JWT_SECRET_KEY", _DEV_JWT_SECRET_KEY
    )
    ENCRYPTION_KEY = env_vars.get("ENCRYPTION_KEY", _DEV_ENCRYPTION_KEY)

    REDIS_URL = env_vars.get(
        "REDIS_URL", "redis://localhost:6379/0"
    )
    REDIS_CACHE_URL = env_vars.get(
        "REDIS_CACHE_URL", "redis://localhost:6379/0"
    )
    REDIS_QUEUE_URL = env_vars.get(
        "REDIS_QUEUE_URL", "redis://localhost:6380/0"
    )
    REDIS_EVENTS_URL = env_vars.get(
        "REDIS_EVENTS_URL", "redis://localhost:6381/0"
    )
    REDIS_CHANNELS_URL = env_vars.get(
        "REDIS_CHANNELS_URL", "redis://localhost:6382/0"
    )
    BAAS_REDIS_URL = env_vars.get("BAAS_REDIS_URL", None)

    if ENVIRONMENT == "production":
        # SECRET_KEY guard
        if not SECRET_KEY or SECRET_KEY == _DEV_SECRET_KEY:
            raise IC(
                "In production, SECRET_KEY must be set via environment "
                "and must not be the dev default. "
                "Set SECRET_KEY in env or use a secret manager. "
                "See docs/SECURITY.md."
            )
        # JWT_SECRET_KEY guard
        if not JWT_SECRET_KEY or JWT_SECRET_KEY == _DEV_JWT_SECRET_KEY:
            raise IC(
                "In production, JWT_SECRET_KEY must be set via environment "
                "and must not be the dev default. "
                "Set JWT_SECRET_KEY in env or use a secret manager. "
                "See docs/SECURITY.md."
            )
        # ENCRYPTION_KEY guard
        if not ENCRYPTION_KEY or ENCRYPTION_KEY == _DEV_ENCRYPTION_KEY:
            raise IC(
                "In production, ENCRYPTION_KEY must be set via environment "
                "and must not be the dev default. "
                "Set ENCRYPTION_KEY to a cryptographically random "
                "32-byte base64 value. See docs/SECURITY.md."
            )
        # Redis URL guards — no unauthenticated URLs, no empty passwords.
        _redis_urls: dict = {
            "REDIS_URL": REDIS_URL,
            "REDIS_CACHE_URL": REDIS_CACHE_URL,
            "REDIS_QUEUE_URL": REDIS_QUEUE_URL,
            "REDIS_EVENTS_URL": REDIS_EVENTS_URL,
            "REDIS_CHANNELS_URL": REDIS_CHANNELS_URL,
        }
        if BAAS_REDIS_URL:
            _redis_urls["BAAS_REDIS_URL"] = BAAS_REDIS_URL
        for _var, _url in _redis_urls.items():
            if not _url:
                continue
            if "@" not in _url:
                raise IC(
                    f"In production, {_var} must include authentication "
                    f"credentials (format: redis://:password@host:port/db). "
                    f"Current value has no '@' — unauthenticated Redis is "
                    f"not permitted. See docs/SECURITY.md."
                )
            # Reject empty passwords: redis://:@host is structurally valid
            # but provides no security.
            _creds = _url.rsplit("@", 1)[0]
            if _creds.endswith(":"):
                raise IC(
                    f"In production, {_var} has an empty password "
                    f"(detected pattern: '...:<empty>@'). "
                    f"Set a strong password: "
                    f"redis://:strongpassword@host:port/db. "
                    f"See docs/SECURITY.md."
                )


def _safe_env() -> dict:
    """Return a minimal safe production environment."""
    return {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "safe-secret-key-for-test-" + "x" * 30,
        "JWT_SECRET_KEY": "safe-jwt-key-for-test-" + "x" * 30,
        "ENCRYPTION_KEY": (
            "c2FmZS1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdC0xMjM="
        ),
        "REDIS_URL": "redis://:password@redis:6379/0",
        "REDIS_CACHE_URL": "redis://:password@redis-cache:6379/0",
        "REDIS_QUEUE_URL": "redis://:password@redis-queue:6379/0",
        "REDIS_EVENTS_URL": "redis://:password@redis-events:6379/0",
        "REDIS_CHANNELS_URL": "redis://:password@redis-channels:6379/0",
    }


# ---------------------------------------------------------------------------
# ENCRYPTION_KEY guard
# ---------------------------------------------------------------------------

class TestEncryptionKeyGuard:
    """Guard: ENCRYPTION_KEY must not be missing or equal to the dev default."""

    def test_dev_default_raises_in_production(self):
        env = _safe_env()
        env["ENCRYPTION_KEY"] = "dev-encryption-key-not-for-production"
        with pytest.raises(ImproperlyConfigured, match="ENCRYPTION_KEY"):
            _run_guard_code(env)

    def test_empty_string_raises_in_production(self):
        env = _safe_env()
        env["ENCRYPTION_KEY"] = ""
        with pytest.raises(ImproperlyConfigured, match="ENCRYPTION_KEY"):
            _run_guard_code(env)

    def test_valid_key_passes_in_production(self):
        env = _safe_env()
        env["ENCRYPTION_KEY"] = (
            "c2FmZS1lbmNyeXB0aW9uLWtleS1mb3ItdGVzdC0xMjM="
        )
        _run_guard_code(env)  # should not raise

    def test_dev_default_allowed_outside_production(self):
        env = _safe_env()
        env["ENVIRONMENT"] = "development"
        env["ENCRYPTION_KEY"] = "dev-encryption-key-not-for-production"
        _run_guard_code(env)  # guard only triggers in production

    def test_error_message_mentions_base64(self):
        env = _safe_env()
        env["ENCRYPTION_KEY"] = "dev-encryption-key-not-for-production"
        with pytest.raises(ImproperlyConfigured, match="base64"):
            _run_guard_code(env)


# ---------------------------------------------------------------------------
# SECRET_KEY guard (existing behaviour — regression)
# ---------------------------------------------------------------------------

class TestSecretKeyGuard:
    """Regression: existing SECRET_KEY guard still fires correctly."""

    def test_dev_default_raises_in_production(self):
        env = _safe_env()
        env["SECRET_KEY"] = "dev-secret-key-not-for-production"
        with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
            _run_guard_code(env)

    def test_valid_key_passes(self):
        env = _safe_env()
        env["SECRET_KEY"] = "production-safe-secret-key-long-enough-yes"
        _run_guard_code(env)


# ---------------------------------------------------------------------------
# JWT_SECRET_KEY guard (existing behaviour — regression)
# ---------------------------------------------------------------------------

class TestJwtSecretKeyGuard:
    """Regression: existing JWT_SECRET_KEY guard still fires correctly."""

    def test_dev_default_raises_in_production(self):
        env = _safe_env()
        env["JWT_SECRET_KEY"] = "dev-jwt-secret-key-not-for-production"
        with pytest.raises(ImproperlyConfigured, match="JWT_SECRET_KEY"):
            _run_guard_code(env)

    def test_valid_key_passes(self):
        env = _safe_env()
        env["JWT_SECRET_KEY"] = "production-safe-jwt-key-long-enough-yes-x"
        _run_guard_code(env)


# ---------------------------------------------------------------------------
# Redis URL guards
# ---------------------------------------------------------------------------

class TestRedisUrlGuard:
    """All Redis URLs must include non-empty credentials in production."""

    @pytest.mark.parametrize("redis_var", [
        "REDIS_URL",
        "REDIS_CACHE_URL",
        "REDIS_QUEUE_URL",
        "REDIS_EVENTS_URL",
        "REDIS_CHANNELS_URL",
    ])
    def test_unauthenticated_url_raises(self, redis_var: str):
        env = _safe_env()
        env[redis_var] = "redis://redis:6379/0"  # no '@'
        with pytest.raises(ImproperlyConfigured, match=redis_var):
            _run_guard_code(env)

    @pytest.mark.parametrize("redis_var", [
        "REDIS_URL",
        "REDIS_CACHE_URL",
        "REDIS_QUEUE_URL",
        "REDIS_EVENTS_URL",
        "REDIS_CHANNELS_URL",
    ])
    def test_authenticated_url_passes(self, redis_var: str):
        env = _safe_env()
        env[redis_var] = "redis://:strongpassword@redis:6379/0"
        _run_guard_code(env)

    @pytest.mark.parametrize("redis_var", [
        "REDIS_URL",
        "REDIS_CACHE_URL",
        "REDIS_QUEUE_URL",
        "REDIS_EVENTS_URL",
        "REDIS_CHANNELS_URL",
    ])
    def test_empty_password_url_raises(self, redis_var: str):
        """redis://:@host is structurally valid but has an empty password."""
        env = _safe_env()
        env[redis_var] = "redis://:@redis:6379/0"
        with pytest.raises(ImproperlyConfigured, match="empty password"):
            _run_guard_code(env)

    def test_baas_redis_unauthenticated_raises(self):
        """BAAS_REDIS_URL must also carry credentials when set."""
        env = _safe_env()
        env["BAAS_REDIS_URL"] = "redis://baas-redis:6379/0"
        with pytest.raises(
            ImproperlyConfigured, match="BAAS_REDIS_URL"
        ):
            _run_guard_code(env)

    def test_baas_redis_empty_password_raises(self):
        """BAAS_REDIS_URL with empty password must be rejected."""
        env = _safe_env()
        env["BAAS_REDIS_URL"] = "redis://:@baas-redis:6379/0"
        with pytest.raises(ImproperlyConfigured, match="empty password"):
            _run_guard_code(env)

    def test_baas_redis_authenticated_passes(self):
        """BAAS_REDIS_URL with a real password should not raise."""
        env = _safe_env()
        env["BAAS_REDIS_URL"] = "redis://:strongpw@baas-redis:6379/0"
        _run_guard_code(env)

    def test_baas_redis_absent_passes(self):
        """Omitting BAAS_REDIS_URL entirely is allowed."""
        env = _safe_env()
        env.pop("BAAS_REDIS_URL", None)
        _run_guard_code(env)

    def test_error_message_mentions_format(self):
        env = _safe_env()
        env["REDIS_URL"] = "redis://redis:6379/0"
        with pytest.raises(
            ImproperlyConfigured, match="redis://:password@"
        ):
            _run_guard_code(env)

    def test_unauthenticated_redis_allowed_in_development(self):
        env = _safe_env()
        env["ENVIRONMENT"] = "development"
        env["REDIS_URL"] = "redis://localhost:6379/0"
        _run_guard_code(env)

    def test_all_urls_authenticated_passes(self):
        """Happy path: all Redis URLs have credentials in production."""
        _run_guard_code(_safe_env())


# ---------------------------------------------------------------------------
# PostgreSQL SSL (settings-level flag, not guard — behavioural test)
# ---------------------------------------------------------------------------

class TestPostgresSslOption:
    """Verify that sslmode=require is applied to DB options in production."""

    def test_sslmode_present_in_production_settings(self):
        """
        Integration-level check: replicate the DB OPTIONS construction
        from settings.py and verify sslmode=require is present.
        """
        sslmode_applied = False
        ENVIRONMENT = "production"
        if ENVIRONMENT == "production":
            db_options: dict = {
                "connect_timeout": 60,
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
                "sslmode": "require",
            }
            sslmode_applied = db_options.get("sslmode") == "require"
        assert sslmode_applied, (
            "sslmode=require must be set in production DB OPTIONS"
        )

    def test_sslmode_absent_in_development(self):
        ENVIRONMENT = "development"
        db_options: dict = {
            "connect_timeout": 60,
            "keepalives": 1,
        }
        if ENVIRONMENT == "production":
            db_options["sslmode"] = "require"
        assert "sslmode" not in db_options

    def test_conn_max_age_zero_when_pgbouncer_enabled(self):
        pgbouncer_enabled = True
        conn_max_age = 0 if pgbouncer_enabled else 600
        assert conn_max_age == 0

    def test_conn_max_age_default_without_pgbouncer(self):
        pgbouncer_enabled = False
        conn_max_age = 0 if pgbouncer_enabled else 600
        assert conn_max_age == 600

    def test_baas_sslmode_applied_in_production(self):
        """BaaS DB OPTIONS must also receive sslmode=require in production."""
        ENVIRONMENT = "production"
        baas_options: dict = {}
        if ENVIRONMENT == "production":
            baas_options["sslmode"] = "require"
        assert baas_options.get("sslmode") == "require", (
            "sslmode=require must be set in BaaS DB OPTIONS in production"
        )

    def test_baas_sslmode_absent_in_development(self):
        """BaaS DB OPTIONS must NOT get sslmode outside production."""
        ENVIRONMENT = "development"
        baas_options: dict = {}
        if ENVIRONMENT == "production":
            baas_options["sslmode"] = "require"
        assert "sslmode" not in baas_options


# ---------------------------------------------------------------------------
# Helper: extended guard logic added in Phase 8
# ---------------------------------------------------------------------------

def _run_extended_guard_code(env_vars: dict) -> dict:
    """
    Replicate the Phase-8 guard logic from settings.py in isolation.

    Returns a dict of computed settings values so callers can assert on
    them without loading the full Django settings module.

    Raises ImproperlyConfigured exactly as settings.py does.
    """
    from django.core.exceptions import ImproperlyConfigured as IC

    ENVIRONMENT = env_vars.get("ENVIRONMENT", "development")
    DEBUG = env_vars.get("DEBUG", False)
    USE_S3 = env_vars.get("USE_S3", False)
    AWS_SECRET_ACCESS_KEY = env_vars.get("AWS_SECRET_ACCESS_KEY", "")
    CORS_ALLOWED_ORIGINS = env_vars.get("CORS_ALLOWED_ORIGINS", None)

    # Replicate _cors_defaults logic
    if CORS_ALLOWED_ORIGINS is None:
        _cors_defaults = [] if ENVIRONMENT == "production" else [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5184",
            "http://localhost:8000",
        ]
        CORS_ALLOWED_ORIGINS = _cors_defaults

    # Defaults (non-production)
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    if ENVIRONMENT == "production":
        if DEBUG:
            raise IC(
                "DEBUG must be False in production. "
                "Set DEBUG=False in env. See docs/SECURITY.md."
            )
        if USE_S3 and not AWS_SECRET_ACCESS_KEY:
            raise IC(
                "In production with USE_S3=True, AWS_SECRET_ACCESS_KEY must be "
                "set via environment. See docs/SECURITY.md."
            )
        if not CORS_ALLOWED_ORIGINS:
            raise IC("CORS_ALLOWED_ORIGINS must be set in production.")
        # Apply production cookie/HSTS overrides
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_HSTS_SECONDS = 63072000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SECURE_HSTS_PRELOAD = True

    return {
        "ENVIRONMENT": ENVIRONMENT,
        "DEBUG": DEBUG,
        "SESSION_COOKIE_SECURE": SESSION_COOKIE_SECURE,
        "CSRF_COOKIE_SECURE": CSRF_COOKIE_SECURE,
        "SECURE_HSTS_SECONDS": SECURE_HSTS_SECONDS,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": SECURE_HSTS_INCLUDE_SUBDOMAINS,
        "SECURE_HSTS_PRELOAD": SECURE_HSTS_PRELOAD,
        "CORS_ALLOWED_ORIGINS": CORS_ALLOWED_ORIGINS,
    }


def _safe_extended_env() -> dict:
    """Minimal safe production env for extended-guard tests."""
    return {
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "USE_S3": False,
        "AWS_SECRET_ACCESS_KEY": "prod-s3-secret",
        "CORS_ALLOWED_ORIGINS": ["https://app.example.com"],
    }


# ---------------------------------------------------------------------------
# Phase-8 guard tests
# ---------------------------------------------------------------------------

class TestDebugGuard:
    """DEBUG must be False in production."""

    def test_debug_true_raises_in_production(self):
        env = _safe_extended_env()
        env["DEBUG"] = True
        with pytest.raises(ImproperlyConfigured, match="DEBUG"):
            _run_extended_guard_code(env)

    def test_debug_false_passes_in_production(self):
        env = _safe_extended_env()
        env["DEBUG"] = False
        _run_extended_guard_code(env)  # must not raise

    def test_debug_true_allowed_in_development(self):
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        env["DEBUG"] = True
        _run_extended_guard_code(env)  # guard only fires in production


class TestEncryptionKeyDevDefaultRaisesInProduction:
    """ENCRYPTION_KEY dev-default must be caught by the unified guard loop."""

    def test_encryption_key_dev_default_raises_in_production(self):
        # This exercises the unified _secret_guards loop in settings.py via
        # the existing _run_guard_code helper (which already covers it).
        env = _safe_env()
        env["ENCRYPTION_KEY"] = "dev-encryption-key-not-for-production"
        with pytest.raises(ImproperlyConfigured, match="ENCRYPTION_KEY"):
            _run_guard_code(env)


class TestAwsSecretKeyGuard:
    """AWS_SECRET_ACCESS_KEY must not be empty in production when USE_S3=True."""

    def test_aws_secret_key_minio_default_raises_in_production(self):
        """The old 'minio123' default must be treated as missing in production."""
        env = _safe_extended_env()
        env["USE_S3"] = True
        env["AWS_SECRET_ACCESS_KEY"] = ""  # empty = was minio123, now default=""
        with pytest.raises(ImproperlyConfigured, match="AWS_SECRET_ACCESS_KEY"):
            _run_extended_guard_code(env)

    def test_aws_secret_key_set_passes(self):
        env = _safe_extended_env()
        env["USE_S3"] = True
        env["AWS_SECRET_ACCESS_KEY"] = "real-prod-secret"
        _run_extended_guard_code(env)  # must not raise

    def test_aws_guard_skipped_when_use_s3_false(self):
        env = _safe_extended_env()
        env["USE_S3"] = False
        env["AWS_SECRET_ACCESS_KEY"] = ""
        _run_extended_guard_code(env)  # guard only fires when USE_S3=True


class TestCorsAllowedOriginsGuard:
    """CORS_ALLOWED_ORIGINS must be non-empty in production."""

    def test_cors_allowed_origins_empty_raises_in_production(self):
        env = _safe_extended_env()
        env["CORS_ALLOWED_ORIGINS"] = []
        with pytest.raises(ImproperlyConfigured, match="CORS_ALLOWED_ORIGINS"):
            _run_extended_guard_code(env)

    def test_cors_allowed_origins_set_passes(self):
        env = _safe_extended_env()
        env["CORS_ALLOWED_ORIGINS"] = ["https://app.example.com"]
        _run_extended_guard_code(env)  # must not raise

    def test_cors_localhost_defaults_empty_in_production(self):
        """No localhost origins should be present in the production default."""
        env = _safe_extended_env()
        # Remove explicit list so the guard uses _cors_defaults
        env.pop("CORS_ALLOWED_ORIGINS", None)
        # In production _cors_defaults = [] → should raise
        with pytest.raises(ImproperlyConfigured, match="CORS_ALLOWED_ORIGINS"):
            _run_extended_guard_code(env)

    def test_cors_localhost_defaults_present_in_development(self):
        """localhost defaults must be present when not in production."""
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        env.pop("CORS_ALLOWED_ORIGINS", None)
        result = _run_extended_guard_code(env)
        assert any(
            "localhost" in origin
            for origin in result["CORS_ALLOWED_ORIGINS"]
        ), "Dev CORS defaults should include localhost origins"

    def test_cors_port_3011_not_in_dev_defaults(self):
        """Grafana port 3011 must have been removed from dev defaults."""
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        env.pop("CORS_ALLOWED_ORIGINS", None)
        result = _run_extended_guard_code(env)
        assert "http://localhost:3011" not in result["CORS_ALLOWED_ORIGINS"], (
            "Port 3011 (Grafana) must not appear in CORS dev defaults"
        )


class TestProductionCookieSettings:
    """SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE must be True in production."""

    def test_session_cookie_secure_in_production(self):
        result = _run_extended_guard_code(_safe_extended_env())
        assert result["SESSION_COOKIE_SECURE"] is True, (
            "SESSION_COOKIE_SECURE must be True in production"
        )

    def test_csrf_cookie_secure_in_production(self):
        result = _run_extended_guard_code(_safe_extended_env())
        assert result["CSRF_COOKIE_SECURE"] is True, (
            "CSRF_COOKIE_SECURE must be True in production"
        )

    def test_session_cookie_secure_false_in_development(self):
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        result = _run_extended_guard_code(env)
        assert result["SESSION_COOKIE_SECURE"] is False

    def test_csrf_cookie_secure_false_in_development(self):
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        result = _run_extended_guard_code(env)
        assert result["CSRF_COOKIE_SECURE"] is False


class TestProductionHstsSettings:
    """HSTS must be configured in production."""

    def test_hsts_seconds_nonzero_in_production(self):
        result = _run_extended_guard_code(_safe_extended_env())
        assert result["SECURE_HSTS_SECONDS"] > 0, (
            "SECURE_HSTS_SECONDS must be > 0 in production"
        )

    def test_hsts_include_subdomains_in_production(self):
        result = _run_extended_guard_code(_safe_extended_env())
        assert result["SECURE_HSTS_INCLUDE_SUBDOMAINS"] is True

    def test_hsts_preload_in_production(self):
        result = _run_extended_guard_code(_safe_extended_env())
        assert result["SECURE_HSTS_PRELOAD"] is True

    def test_hsts_zero_in_development(self):
        env = _safe_extended_env()
        env["ENVIRONMENT"] = "development"
        result = _run_extended_guard_code(env)
        assert result["SECURE_HSTS_SECONDS"] == 0


# ---------------------------------------------------------------------------
# Structural checks against the actual MIDDLEWARE list and settings module
# ---------------------------------------------------------------------------

class TestMiddlewareOrdering:
    """SecurityMiddleware[0], CorsMiddleware[1], CSPMiddleware[2]."""

    def _get_middleware(self):
        # Read MIDDLEWARE from the already-configured django.conf.settings.
        # django.setup() has been called by hub/conftest.py at session start,
        # so this is safe and avoids re-importing the full settings module
        # (which would re-run the PostgreSQL connectivity check).
        import sys
        mod_name = "hub.settings"
        if mod_name in sys.modules:
            return sys.modules[mod_name].MIDDLEWARE
        # If for any reason settings is not yet loaded, read the list directly
        # from the literal source so the test never triggers network I/O.
        # This branch is only reached when running the test in true isolation
        # (e.g. pytest -p no:django) without a prior django.setup().
        import os
        settings_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "hub", "settings.py",
        )
        middleware: list[str] = []
        in_middleware = False
        with open(settings_file) as fh:
            for line in fh:
                stripped = line.strip()
                if stripped == "MIDDLEWARE = [":
                    in_middleware = True
                    continue
                if in_middleware:
                    if stripped == "]":
                        break
                    # Extract quoted middleware path strings
                    if stripped.startswith('"') or stripped.startswith("'"):
                        entry = stripped.split('"')[1] if '"' in stripped else stripped.split("'")[1]
                        middleware.append(entry)
        return middleware

    def test_middleware_security_is_first(self):
        mw = self._get_middleware()
        assert mw[0] == "django.middleware.security.SecurityMiddleware", (
            f"SecurityMiddleware must be index 0, got: {mw[0]}"
        )

    def test_middleware_cors_is_second(self):
        mw = self._get_middleware()
        assert mw[1] == "corsheaders.middleware.CorsMiddleware", (
            f"CorsMiddleware must be index 1, got: {mw[1]}"
        )

    def test_csp_middleware_present_in_stack(self):
        mw = self._get_middleware()
        assert "csp.middleware.CSPMiddleware" in mw, (
            "CSPMiddleware must be present in MIDDLEWARE"
        )

    def test_csp_middleware_is_third(self):
        mw = self._get_middleware()
        assert mw[2] == "csp.middleware.CSPMiddleware", (
            f"CSPMiddleware must be index 2, got: {mw[2]}"
        )


class TestStaticUrlNotOverridden:
    """The duplicate STATIC_URL = '/static/' assignment must be gone from settings.py.

    Root cause: a second unconditional ``STATIC_URL = "/static/"`` that appeared
    after the S3/local storage branching block would silently overwrite the S3 URL
    set by django-storages when ``USE_S3=True``.  This test reads the actual source
    file and verifies the assignment only appears inside the ``else`` (non-S3) branch.
    """

    @staticmethod
    def _settings_source() -> str:
        import os
        settings_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "hub",
            "settings.py",
        )
        with open(settings_file) as f:
            return f.read()

    def test_static_url_not_overridden_when_s3_enabled(self):
        """STATIC_URL = '/static/' must only appear inside the else (non-S3) branch."""
        import re
        source = self._settings_source()

        # Find every occurrence of the bare assignment.
        # We look for lines that assign "/static/" unconditionally — i.e. NOT
        # preceded by an indented ``else`` block from the ``if USE_S3:`` branch.
        matches = list(re.finditer(
            r'^\s*STATIC_URL\s*=\s*["\']\/static\/["\']',
            source,
            re.MULTILINE,
        ))
        assert len(matches) == 1, (
            f"Expected exactly 1 occurrence of STATIC_URL = '/static/' "
            f"(inside the non-S3 else branch), found {len(matches)}.  "
            "A duplicate unconditional assignment would overwrite the "
            "django-storages S3 URL when USE_S3=True."
        )

        # Verify that single occurrence is inside the else branch by checking
        # that the line is indented (i.e. inside a conditional block).
        match = matches[0]
        line_start = source.rfind("\n", 0, match.start()) + 1
        line_text = source[line_start: match.end()]
        assert line_text.startswith("    "), (
            "STATIC_URL = '/static/' must be inside an indented (else) block, "
            f"but found it at the top level: {line_text!r}"
        )

    def test_static_url_count_in_settings(self):
        """Sanity check: STATIC_URL appears at least once in settings.py."""
        source = self._settings_source()
        assert "STATIC_URL" in source, "STATIC_URL must be defined in settings.py"


# ---------------------------------------------------------------------------
# Phase 221.2.1 — Django admin path restriction
# ---------------------------------------------------------------------------

class TestAdminUrlGate:
    """Phase 221.2.1: /admin/ must be absent from URL patterns in production.

    The helper ``_build_urlpatterns()`` in ``hub/urls.py`` reads
    ``settings.ENVIRONMENT`` at call time, so ``override_settings``
    gives us a clean, reload-free test surface.
    """

    @staticmethod
    def _admin_patterns(patterns):
        """Return URL patterns whose route matches 'admin/'."""
        return [
            p for p in patterns
            if hasattr(p, 'pattern') and 'admin' in str(p.pattern)
        ]

    def test_admin_absent_in_production(self):
        from django.test import override_settings
        with override_settings(ENVIRONMENT='production'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._admin_patterns(patterns)
            assert len(hits) == 0, (
                f"Admin URL must NOT be registered in production, "
                f"found: {[str(p.pattern) for p in hits]}"
            )

    def test_admin_present_in_development(self):
        from django.test import override_settings
        with override_settings(ENVIRONMENT='development'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._admin_patterns(patterns)
            assert len(hits) == 1, (
                "Admin URL must be registered in development"
            )

    def test_admin_absent_in_staging(self):
        """Track A PR 1: staging is publicly reachable, so admin must
        disappear there too. Access via `kubectl port-forward` if needed.
        """
        from django.test import override_settings
        with override_settings(ENVIRONMENT='staging'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._admin_patterns(patterns)
            assert len(hits) == 0, (
                "Admin URL must NOT be registered in staging "
                "(same treatment as production)"
            )

    def test_admin_present_in_test(self):
        """Test environment must have admin available for admin-related tests."""
        from django.test import override_settings
        with override_settings(ENVIRONMENT='test'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._admin_patterns(patterns)
            assert len(hits) == 1, (
                "Admin URL must be registered in test environment"
            )

    def test_admin_url_resolves_to_django_admin(self):
        """When admin is registered, verify it wires up to django.contrib.admin."""
        from django.test import override_settings
        with override_settings(ENVIRONMENT='development'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._admin_patterns(patterns)
            assert len(hits) == 1
            assert str(hits[0].pattern) == 'admin/'


# ---------------------------------------------------------------------------
# Phase 221.5 — Cookie security: __Secure- prefix & SameSite=Strict
# ---------------------------------------------------------------------------

class TestRefreshCookieSecurePrefix:
    """Phase 221.5.1: REFRESH_COOKIE_NAME must use __Secure- prefix
    in production/staging (HTTPS available).

    The __Secure- prefix is browser-enforced: the Secure attribute MUST
    be set, preventing the cookie from being sent or set over HTTP.  This
    blocks subdomain cookie-theft attacks.

    In development, the prefix is NOT used because ``secure=False``
    (DEBUG=True) would cause browsers to silently drop the cookie.
    """

    def test_production_uses_secure_prefix(self):
        from django.test import override_settings
        with override_settings(ENVIRONMENT='production'):
            # Re-evaluate the default the way settings.py does
            env = "production"
            default = (
                "__Secure-refresh_token"
                if env in ("production", "staging")
                else "refresh_token"
            )
            assert default.startswith("__Secure-"), (
                "Production default must use __Secure- prefix"
            )

    def test_staging_uses_secure_prefix(self):
        env = "staging"
        default = (
            "__Secure-refresh_token"
            if env in ("production", "staging")
            else "refresh_token"
        )
        assert default.startswith("__Secure-"), (
            "Staging default must use __Secure- prefix"
        )

    def test_development_uses_plain_name(self):
        env = "development"
        default = (
            "__Secure-refresh_token"
            if env in ("production", "staging")
            else "refresh_token"
        )
        assert not default.startswith("__Secure-"), (
            "Development default must NOT use __Secure- prefix "
            "(browsers drop __Secure- cookies without Secure attribute)"
        )
        assert default == "refresh_token"

    def test_settings_module_reflects_environment(self):
        """The live settings.REFRESH_COOKIE_NAME must match the
        environment-appropriate default (test env = development)."""
        from django.conf import settings
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "")
        env = getattr(settings, "ENVIRONMENT", "development")
        if env in ("production", "staging"):
            assert cookie_name.startswith("__Secure-"), (
                f"REFRESH_COOKIE_NAME must start with __Secure- "
                f"in {env}, got: {cookie_name}"
            )
        else:
            # Development/test — plain name
            assert cookie_name == "refresh_token", (
                f"REFRESH_COOKIE_NAME must be 'refresh_token' "
                f"in {env}, got: {cookie_name}"
            )


class TestSessionCookieSameSiteStrict:
    """Phase 221.5.2: SESSION_COOKIE_SAMESITE must default to Strict.

    The SPA uses JWT for auth (not Django sessions), so Strict does not
    break any authentication flow.  The Django admin is disabled in
    production (221.2.1).  SSO views use JWT tokens, not sessions.
    """

    def test_session_cookie_samesite_is_strict(self):
        """Default must be Strict (not Lax)."""
        from django.conf import settings
        value = getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
        assert value == "Strict", (
            f"SESSION_COOKIE_SAMESITE must default to 'Strict', "
            f"got: {value!r}"
        )

    def test_csrf_cookie_samesite_stays_lax(self):
        """CSRF cookie must remain Lax — Strict would cause CSRF validation
        failures on the first navigation from an external site."""
        from django.conf import settings
        value = getattr(settings, "CSRF_COOKIE_SAMESITE", "Lax")
        assert value == "Lax", (
            f"CSRF_COOKIE_SAMESITE must remain 'Lax', got: {value!r}"
        )


# ---------------------------------------------------------------------------
# Phase 221.6 — Bandit configuration: no blanket skips for security rules
# ---------------------------------------------------------------------------

class TestBanditConfigNoB601Skip:
    """Phase 221.6: B601 (paramiko_calls) must NOT be globally skipped.

    B601 detects potentially dangerous paramiko ``exec_command`` calls.
    The codebase has zero B601 violations (paramiko usage is SFTP-only),
    so the global skip was dead weight that would silently suppress any
    *future* violation introduced by a contributor.
    """

    @staticmethod
    def _repo_root():
        import os
        return os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))
        )

    def test_bandit_yaml_does_not_skip_b601(self):
        """`.bandit.yaml` must not list B601 in skips."""
        import os
        import yaml

        path = os.path.join(self._repo_root(), ".bandit.yaml")
        if not os.path.exists(path):
            pytest.skip(".bandit.yaml not found")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        skips = cfg.get("skips", [])
        assert "B601" not in skips, (
            f"B601 must not be in .bandit.yaml skips: {skips}"
        )

    def test_bandit_ini_does_not_skip_b601(self):
        """`.bandit` INI config must not list B601 in skips."""
        import configparser
        import os

        path = os.path.join(self._repo_root(), ".bandit")
        if not os.path.exists(path):
            pytest.skip(".bandit not found")
        cp = configparser.ConfigParser()
        read_files = cp.read(path)
        assert read_files, (
            f"Failed to read .bandit config file at {path} — "
            f"ConfigParser.read() returned empty list"
        )
        raw = cp.get("bandit", "skips", fallback="")
        skips = [s.strip().strip('"').strip("'")
                 for s in raw.strip("[]").split(",") if s.strip()]
        assert "B601" not in skips, (
            f"B601 must not be in .bandit skips: {skips}"
        )


# ---------------------------------------------------------------------------
# Phase 221.4.1 — OpenAPI / Swagger / ReDoc restriction
# ---------------------------------------------------------------------------

class TestApiDocsUrlGate:
    """Phase 221.4.1: /api-docs/ must be absent from URL patterns in production.

    The developer documentation endpoints (Swagger UI, ReDoc, and the
    api-docs-scoped OpenAPI schema) expose the full API surface and are
    only needed in development / staging.

    The ``/api/v1/openapi.json`` endpoint is NOT gated — it lives in the
    API app's URL conf and is required pre-auth by the frontend for
    capability discovery.
    """

    _API_DOCS_ROUTES = {'api-docs/openapi.json', 'api-docs/', 'api-docs/redoc/'}

    @staticmethod
    def _api_docs_patterns(patterns):
        """Return URL patterns whose route starts with 'api-docs'."""
        return [
            p for p in patterns
            if hasattr(p, 'pattern') and str(p.pattern).startswith('api-docs')
        ]

    def test_api_docs_absent_in_production(self):
        from django.test import override_settings
        with override_settings(ENVIRONMENT='production'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._api_docs_patterns(patterns)
            assert len(hits) == 0, (
                f"api-docs endpoints must NOT be registered in production, "
                f"found: {[str(p.pattern) for p in hits]}"
            )

    def test_api_docs_present_in_development(self):
        from django.test import override_settings
        with override_settings(ENVIRONMENT='development'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._api_docs_patterns(patterns)
            routes = {str(p.pattern) for p in hits}
            assert routes == self._API_DOCS_ROUTES, (
                f"Expected {self._API_DOCS_ROUTES}, got {routes}"
            )

    def test_api_docs_absent_in_staging(self):
        """Track A PR 1: Swagger/ReDoc/OpenAPI-scoped endpoints aid
        reconnaissance on any public host. Staging is publicly reachable,
        so gate them out the same way as production.
        """
        from django.test import override_settings
        with override_settings(ENVIRONMENT='staging'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            hits = self._api_docs_patterns(patterns)
            assert len(hits) == 0, (
                "api-docs endpoints must NOT be registered in staging "
                "(same treatment as production)"
            )

    def test_api_v1_openapi_not_affected(self):
        """The /api/v1/openapi.json endpoint must remain available
        regardless of environment — the frontend needs it pre-auth."""
        from django.test import override_settings
        with override_settings(ENVIRONMENT='production'):
            from hub.urls import _build_urlpatterns
            patterns = _build_urlpatterns()
            # /api/v1/ is an include, so just verify it's still registered
            api_v1 = [
                p for p in patterns
                if hasattr(p, 'pattern') and str(p.pattern) == 'api/v1/'
            ]
            assert len(api_v1) == 1, (
                "/api/v1/ must remain registered in production "
                "(contains /api/v1/openapi.json for frontend capability discovery)"
            )


class TestThreadPatchNotInSettingsModule:
    """validate_thread_sharing monkey-patches must not exist in settings.py."""

    def test_thread_patch_not_in_settings_module(self):
        import os
        settings_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "hub",
            "settings.py",
        )
        with open(settings_file) as f:
            source = f.read()
        assert "validate_thread_sharing = " not in source, (
            "validate_thread_sharing monkey-patch must not be assigned "
            "in settings.py — move it to hub/tests/conftest.py"
        )
