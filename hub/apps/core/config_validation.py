"""
Startup configuration validation.

Validates required env/settings (database, Redis, ALLOWED_HOSTS, production
secrets) and raises ImproperlyConfigured on failure. Used by the
validate_config management command and optionally by AppConfig.ready().

See docs/CONFIG_VALIDATION_DESIGN.md.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

# Dev default values (must match hub/settings.py) for production check
_DEV_SECRET_KEY = "dev-secret-key-not-for-production"
_DEV_JWT_SECRET_KEY = "dev-jwt-secret-key-not-for-production"


def _is_production() -> bool:
    env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
    return env == "production"


def _requires_redis() -> bool:
    """True when Redis URL is required (production or staging per design)."""
    env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
    return env in ("production", "staging")


def validate_database_config() -> None:
    """Ensure DATABASES['default'] exists and has required keys."""
    db = getattr(settings, "DATABASES", None) or {}
    default = db.get("default")
    if not default:
        raise ImproperlyConfigured(
            "DATABASES['default'] is missing. Configure via POSTGRES_* env or "
            "DATABASES. See docs/CONFIG_VALIDATION_DESIGN.md."
        )
    for key in ("ENGINE", "NAME", "HOST", "PORT"):
        if key not in default:
            raise ImproperlyConfigured(
                f"DATABASES['default'] must define '{key}'. See docs/CONFIG_VALIDATION_DESIGN.md."
            )
    if not default.get("ENGINE") or not default.get("NAME"):
        raise ImproperlyConfigured(
            "DATABASES['default'] ENGINE and NAME must be non-empty. "
            "See docs/CONFIG_VALIDATION_DESIGN.md."
        )


def validate_redis_config() -> None:
    """Ensure at least one Redis URL is set and has valid scheme."""
    redis_url = getattr(settings, "REDIS_URL", None) or ""
    redis_cache_url = getattr(settings, "REDIS_CACHE_URL", None) or ""
    url = redis_cache_url if redis_cache_url else redis_url
    if not url or not url.strip():
        if _requires_redis():
            raise ImproperlyConfigured(
                "Redis is required in production/staging. Set REDIS_URL or "
                "REDIS_CACHE_URL. See docs/CONFIG_VALIDATION_DESIGN.md."
            )
        logger.warning(
            "Redis URL not set (REDIS_URL/REDIS_CACHE_URL). "
            "Required in production/staging. See docs/CONFIG_VALIDATION_DESIGN.md."
        )
        return
    stripped = url.strip()
    if not (stripped.startswith("redis://") or stripped.startswith("rediss://")):
        raise ImproperlyConfigured(
            f"Redis URL must start with redis:// or rediss:// "
            f"(got: {url[:50]!r}...). See docs/CONFIG_VALIDATION_DESIGN.md."
        )


def validate_allowed_hosts() -> None:
    """In production, ALLOWED_HOSTS must be non-empty."""
    if not _is_production():
        return
    allowed = getattr(settings, "ALLOWED_HOSTS", None)
    if not allowed or (isinstance(allowed, (list, tuple)) and len(allowed) == 0):
        raise ImproperlyConfigured(
            "In production, ALLOWED_HOSTS must be set and non-empty. "
            "Set via env (comma-separated) or in settings. "
            "See docs/CONFIG_VALIDATION_DESIGN.md."
        )


def validate_production_secrets() -> None:
    """In production, SECRET_KEY and JWT_SECRET_KEY must be set, not dev defaults."""
    if not _is_production():
        return
    secret_key = getattr(settings, "SECRET_KEY", None) or ""
    jwt_secret_key = getattr(settings, "JWT_SECRET_KEY", None) or ""
    if not secret_key or secret_key == _DEV_SECRET_KEY:
        raise ImproperlyConfigured(
            "In production, SECRET_KEY must be set via env and not the dev default. "
            "See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md."
        )
    if not jwt_secret_key or jwt_secret_key == _DEV_JWT_SECRET_KEY:
        raise ImproperlyConfigured(
            "In production, JWT_SECRET_KEY must be set via env and not the dev "
            "default. See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md."
        )


def validate_encryption_key() -> None:
    """Validate ENCRYPTION_KEY is set in production."""
    if not _is_production():
        return
    key = getattr(settings, "ENCRYPTION_KEY", "")
    if not key or key == "_DEV_ENCRYPTION_KEY":
        raise ImproperlyConfigured(
            "ENCRYPTION_KEY must be set to a non-default value in production. "
            "See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md."
        )


def validate_all() -> None:
    """
    Run all startup configuration checks.

    Raises ImproperlyConfigured on first failure.
    """
    validate_database_config()
    validate_redis_config()
    validate_allowed_hosts()
    validate_production_secrets()
    validate_encryption_key()
