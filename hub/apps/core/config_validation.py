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


def _is_deployed_env() -> bool:
    """True for the environments where missing paid config must fail loudly."""
    env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
    return env in ("production", "staging")


def _paid_apps_installed() -> frozenset[str]:
    """Module names of the paid apps present in INSTALLED_APPS.

    INSTALLED_APPS entries are module paths, occasionally with a trailing
    ``.apps.XxxConfig`` class (see hub/apps/manifest.py ALL_HUB_APPS) —
    ``module_name()`` normalizes both forms, so a paid app installed under
    either spelling is detected.
    """
    from hub.apps.manifest import PAID_APPS, module_name

    installed = {module_name(entry) for entry in getattr(settings, "INSTALLED_APPS", [])}
    return installed & {module_name(entry) for entry in PAID_APPS}


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
    if not (stripped.startswith(("redis://", "rediss://"))):
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


def validate_paid_service_config() -> None:
    """Validate the settings the PAID apps depend on (Phase P.8 D6).

    In core-only mode (``HUB_CORE_ONLY=1``) no paid setting is required —
    the published OSS tree must boot without payment, triple-store, BaaS or
    ML configuration. In a deployed full-mode environment, however, each
    installed paid app's required settings MUST be present: a production
    deploy missing them previously booted healthy and failed at first use.
    Every failure names the setting AND the capability it powers, per the
    paid-runtime-integrity spec.

    Enforced in production AND staging (a missing value there fails just as
    loudly); development keeps the in-repo defaults.
    """
    if getattr(settings, "HUB_CORE_ONLY", False):
        return
    if not _is_deployed_env():
        return

    installed = _paid_apps_installed()

    if ("hub.apps.billing" in installed or "hub.apps.marketplace" in installed) and not getattr(
        settings, "STRIPE_SECRET_KEY", None
    ):
        raise ImproperlyConfigured(
            "STRIPE_SECRET_KEY is required when the billing/marketplace "
            "apps are installed (full mode) in production/staging — it "
            "powers Stripe payment processing. Set it via env. "
            "See docs/CONFIG_VALIDATION_DESIGN.md and docs/SECURITY.md."
        )

    if "hub.apps.baas" in installed:
        if not getattr(settings, "BAAS_DATABASE_URL", None):
            raise ImproperlyConfigured(
                "BAAS_DATABASE_URL is required when the baas app is installed "
                "in production/staging — it powers BaaS usage/quota storage. "
                "See docs/runbooks/BAAS_INFRASTRUCTURE.md."
            )
        if not getattr(settings, "BAAS_REDIS_URL", None):
            raise ImproperlyConfigured(
                "BAAS_REDIS_URL is required when the baas app is installed "
                "in production/staging — it powers BaaS usage/quota caching. "
                "See docs/runbooks/BAAS_INFRASTRUCTURE.md."
            )

    if "hub.apps.semantic" in installed:
        for setting_name in ("FUSEKI_URL", "SEMANTIC_SERVICE_URL"):
            value = getattr(settings, setting_name, None)
            if not value:
                raise ImproperlyConfigured(
                    f"{setting_name} is required when the semantic app is "
                    "installed in production/staging — it powers the SPARQL "
                    "triple store and the semantic service client."
                )
            if not value.strip().startswith(("http://", "https://")):
                raise ImproperlyConfigured(
                    f"{setting_name} must be an http(s) URL (got "
                    f"{value[:50]!r}...). See docs/CONFIG_VALIDATION_DESIGN.md."
                )

    if "hub.apps.ml" in installed:
        for setting_name in (
            "ODH_TRAINING_OPERATOR_URL",
            "ODH_SERVICE_URL",
            "ODH_INFERENCE_SCHEDULER_URL",
        ):
            value = getattr(settings, setting_name, None)
            if not value:
                raise ImproperlyConfigured(
                    f"{setting_name} is required when the ml app is installed "
                    "in production/staging — it powers ODH model training and "
                    "inference."
                )
            if not value.strip().startswith(("http://", "https://")):
                raise ImproperlyConfigured(
                    f"{setting_name} must be an http(s) URL (got "
                    f"{value[:50]!r}...). See docs/CONFIG_VALIDATION_DESIGN.md."
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
    validate_paid_service_config()
