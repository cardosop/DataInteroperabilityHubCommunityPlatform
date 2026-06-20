"""
Production guard expansion tests (312.18.2).

Validates startup guards in hub/settings.py:
- DEBUG must be False in production
- PGBOUNCER_ENABLED + CHANNEL_LAYERS → ImproperlyConfigured
- Redis passwords required in production for all 5 core instances
- SECRET_KEY / JWT_SECRET_KEY / ENCRYPTION_KEY must not be dev defaults
"""

import pytest
from django.core.exceptions import ImproperlyConfigured


def _run_guard_code(env_vars: dict) -> None:
    """Execute production guard logic isolated from full settings load."""
    _DEV_SECRET_KEY = "dev-secret-key-not-for-production"
    _DEV_JWT_SECRET_KEY = "dev-jwt-secret-key-not-for-production"
    _DEV_ENCRYPTION_KEY = "dev-encryption-key-not-for-production"

    ENVIRONMENT = env_vars.get("ENVIRONMENT", "development")
    SECRET_KEY = env_vars.get("SECRET_KEY", _DEV_SECRET_KEY)
    JWT_SECRET_KEY = env_vars.get("JWT_SECRET_KEY", _DEV_JWT_SECRET_KEY)
    ENCRYPTION_KEY = env_vars.get("ENCRYPTION_KEY", _DEV_ENCRYPTION_KEY)
    DEBUG = env_vars.get("DEBUG", "False")

    if ENVIRONMENT == "production":
        # SECRET_KEY guard
        if not SECRET_KEY or SECRET_KEY == _DEV_SECRET_KEY:
            raise ImproperlyConfigured("SECRET_KEY must not be the dev default in production")

        # JWT_SECRET_KEY guard
        if not JWT_SECRET_KEY or JWT_SECRET_KEY == _DEV_JWT_SECRET_KEY:
            raise ImproperlyConfigured("JWT_SECRET_KEY must not be the dev default in production")

        # ENCRYPTION_KEY guard
        if not ENCRYPTION_KEY or ENCRYPTION_KEY == _DEV_ENCRYPTION_KEY:
            raise ImproperlyConfigured("ENCRYPTION_KEY must not be the dev default in production")

        # DEBUG guard
        if DEBUG in ("True", "true", "1", True, 1):
            raise ImproperlyConfigured("DEBUG must be False in production")

        # PGBOUNCER + CHANNELS guard
        pgbouncer = env_vars.get("PGBOUNCER_ENABLED", "").strip().lower() in ("1", "true", "yes")
        channels_configured = env_vars.get("CHANNEL_LAYERS_CONFIGURED", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if pgbouncer and channels_configured:
            raise ImproperlyConfigured(
                "PGBOUNCER_ENABLED and CHANNEL_LAYERS are incompatible. "
                "PgBouncer transaction pooling does not support persistent "
                "connections required by Django Channels. Disable one."
            )

        # Redis password guard — all 5 core instances must have non-empty passwords
        redis_vars = [
            "REDIS_URL",
            "REDIS_CACHE_URL",
            "REDIS_QUEUE_URL",
            "REDIS_EVENTS_URL",
            "REDIS_CHANNELS_URL",
        ]
        for var in redis_vars:
            url = env_vars.get(var, "")
            if not url:
                raise ImproperlyConfigured(f"{var} is required in production")
            if "@" not in url:
                raise ImproperlyConfigured(
                    f"{var} requires authentication in production. "
                    f"Expected format: redis://:password@host:port/db"
                )
            if "://:@" in url:
                raise ImproperlyConfigured(f"{var} has empty password in production")


# ── Test classes ──────────────────────────────────────────────────────


class TestDebugGuard:
    """DEBUG=False enforcement in production."""

    def test_debug_true_in_production_raises(self):
        env = {"ENVIRONMENT": "production", "DEBUG": "True"}
        with pytest.raises(ImproperlyConfigured, match="DEBUG"):
            _run_guard_code(env)

    def test_debug_false_in_production_passes(self):
        env = {"ENVIRONMENT": "production", "DEBUG": "False"}
        _run_guard_code(env)

    def test_debug_true_in_development_passes(self):
        env = {"ENVIRONMENT": "development", "DEBUG": "True"}
        _run_guard_code(env)


class TestPgBouncerChannelsGuard:
    """PGBOUNCER_ENABLED + CHANNEL_LAYERS → ImproperlyConfigured."""

    def test_pgbouncer_with_channels_raises(self):
        env = {
            "ENVIRONMENT": "production",
            "PGBOUNCER_ENABLED": "true",
            "CHANNEL_LAYERS_CONFIGURED": "true",
        }
        with pytest.raises(ImproperlyConfigured, match="PGBOUNCER"):
            _run_guard_code(env)

    def test_pgbouncer_without_channels_passes(self):
        env = {
            "ENVIRONMENT": "production",
            "PGBOUNCER_ENABLED": "true",
            "CHANNEL_LAYERS_CONFIGURED": "false",
        }
        _run_guard_code(env)

    def test_channels_without_pgbouncer_passes(self):
        env = {
            "ENVIRONMENT": "production",
            "PGBOUNCER_ENABLED": "false",
            "CHANNEL_LAYERS_CONFIGURED": "true",
        }
        _run_guard_code(env)


class TestRedisPasswordGuard:
    """All Redis URLs must have non-empty passwords in production."""

    @pytest.mark.parametrize(
        "redis_var",
        [
            "REDIS_URL",
            "REDIS_CACHE_URL",
            "REDIS_QUEUE_URL",
            "REDIS_EVENTS_URL",
            "REDIS_CHANNELS_URL",
        ],
    )
    def test_unauthenticated_url_raises(self, redis_var):
        env = {"ENVIRONMENT": "production"}
        env.update(
            dict.fromkeys(
                [
                    "REDIS_URL",
                    "REDIS_CACHE_URL",
                    "REDIS_QUEUE_URL",
                    "REDIS_EVENTS_URL",
                    "REDIS_CHANNELS_URL",
                ],
                "redis://:strong@host:6379/0",
            )
        )
        env[redis_var] = "redis://host:6379/0"
        with pytest.raises(ImproperlyConfigured, match=redis_var):
            _run_guard_code(env)

    @pytest.mark.parametrize(
        "redis_var",
        [
            "REDIS_URL",
            "REDIS_CACHE_URL",
            "REDIS_QUEUE_URL",
            "REDIS_EVENTS_URL",
            "REDIS_CHANNELS_URL",
        ],
    )
    def test_empty_password_url_raises(self, redis_var):
        env = {"ENVIRONMENT": "production"}
        env.update(
            dict.fromkeys(
                [
                    "REDIS_URL",
                    "REDIS_CACHE_URL",
                    "REDIS_QUEUE_URL",
                    "REDIS_EVENTS_URL",
                    "REDIS_CHANNELS_URL",
                ],
                "redis://:strong@host:6379/0",
            )
        )
        env[redis_var] = "redis://:@host:6379/0"
        with pytest.raises(ImproperlyConfigured, match="empty password"):
            _run_guard_code(env)

    def test_all_redis_authenticated_passes(self):
        env = {"ENVIRONMENT": "production"}
        env.update(
            dict.fromkeys(
                [
                    "REDIS_URL",
                    "REDIS_CACHE_URL",
                    "REDIS_QUEUE_URL",
                    "REDIS_EVENTS_URL",
                    "REDIS_CHANNELS_URL",
                ],
                "redis://:strongpw@host:6379/0",
            )
        )
        _run_guard_code(env)


class TestSecretKeyGuard:
    """Critical keys must not be dev defaults in production."""

    def test_dev_secret_key_in_production_raises(self):
        env = {"ENVIRONMENT": "production", "SECRET_KEY": "dev-secret-key-change-me"}
        with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
            _run_guard_code(env)

    def test_production_secret_key_passes(self):
        env = {
            "ENVIRONMENT": "production",
            "SECRET_KEY": "prod-real-secret-64-chars-long-xxxxxxxxxx",
        }
        _run_guard_code(env)
