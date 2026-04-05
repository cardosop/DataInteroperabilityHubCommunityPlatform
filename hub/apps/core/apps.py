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
    if cmd in skip_commands:
        return False
    return True


class CoreConfig(AppConfig):
    """Core app configuration."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.core'
    verbose_name = 'Core'

    def ready(self) -> None:
        """Import subpackage models so Django discovers them, then run config validation."""
        import hub.apps.core.bug_prevention.models  # noqa: F401

        if not _should_run_startup_validation():
            return
        from django.conf import settings
        env = getattr(settings, "ENVIRONMENT", "development").strip().lower()
        if env != "production":
            return
        try:
            from hub.apps.core.config_validation import validate_all
            validate_all()
        except Exception:
            # Let it propagate so server fails to start
            raise
