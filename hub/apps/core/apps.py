"""
Core app configuration.
"""

import sys

from django.apps import AppConfig


def _should_run_startup_validation() -> bool:
    """Run config validation when starting server, not for migrate/test."""
    if "pytest" in sys.modules:
        return False
    argv = sys.argv
    if len(argv) < 2:
        return True  # e.g. gunicorn (no Django command)
    cmd = argv[1].lower()
    skip_commands = ("migrate", "makemigrations", "test", "validate_config")
    return cmd not in skip_commands


class CoreConfig(AppConfig):
    """Core app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.core"
    verbose_name = "Core"

    def ready(self) -> None:
        """Import subpackage models so Django discovers them, then run config validation."""
        import hub.apps.core.bug_prevention.models
        import hub.apps.core.business_rules.chain_registry

        if not _should_run_startup_validation():
            return
        from django.conf import settings

        env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
        if env not in ("production", "staging"):
            return
        from hub.apps.core.config_validation import validate_all

        validate_all()
        if env != "production":
            # Phase P.8 D6 — startup config (incl. the paid-service settings)
            # is validated loudly in staging too; the live cross-service
            # version check below is production-only.
            return

        # Phase 250.0.14 / D250.15 — cross-service version-compatibility
        # check. Hub queries dq-service /version + compliance-service
        # /version; refuses to start if either is below the configured
        # minimum (HUB_REQUIRED_DQ_SERVICE_VERSION /
        # HUB_REQUIRED_COMPLIANCE_SERVICE_VERSION). Fail-closed at startup
        # so k8s restart-loop surfaces the mismatch as a deploy-time error
        # rather than a runtime 500.
        from hub.apps.core.cross_service_version_check import (
            run_cross_service_version_check,
        )

        run_cross_service_version_check()
