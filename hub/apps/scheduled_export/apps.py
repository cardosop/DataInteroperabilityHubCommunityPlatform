"""
Scheduled Export App Configuration
"""

from django.apps import AppConfig


class ScheduledExportConfig(AppConfig):
    """Configuration for scheduled export app"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.scheduled_export"
    verbose_name = "Scheduled Export"

    def ready(self):
        """Import business rules to register them."""
        import hub.apps.scheduled_export.business_rules  # side-effect import: registers business rules
