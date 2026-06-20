"""
Observability App Configuration
"""

from django.apps import AppConfig


class ObservabilityConfig(AppConfig):
    """Observability app configuration"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.observability"
    label = "observability"

    def ready(self):
        """Initialize observability components when Django is ready."""
        # Initialize database query instrumentation
        try:
            from hub.apps.observability.db_instrumentation import instrument_database_connection

            instrument_database_connection()
        except Exception:
            # Silently fail if instrumentation cannot be initialized
            pass
