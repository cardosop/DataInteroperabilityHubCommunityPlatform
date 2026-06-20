import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class TransformationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.transformation"

    def ready(self):
        """Connect transformation signals when Django is ready."""
        try:
            import hub.apps.transformation.signals  # noqa: F401
        except Exception as exc:
            logger.warning(
                "transformation_signals_import_failed error=%s",
                exc,
            )
        try:
            from . import business_rules  # noqa: F401 — preload @register_rule
        except Exception as exc:
            logger.warning(
                "transformation_business_rules_import_failed error=%s",
                exc,
            )
