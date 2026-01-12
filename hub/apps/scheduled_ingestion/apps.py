"""
Scheduled Ingestion App Configuration
"""
from django.apps import AppConfig


class ScheduledIngestionConfig(AppConfig):
    """Configuration for scheduled ingestion app"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.scheduled_ingestion'
    verbose_name = 'Scheduled Ingestion'

    def ready(self):
        """Import business rules to register them."""
        import hub.apps.scheduled_ingestion.business_rules  # noqa: F401 - Import to register business rules

