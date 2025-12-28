"""
Webhooks App Configuration

Django app configuration for webhooks app.
"""

from django.apps import AppConfig
import structlog

logger = structlog.get_logger(__name__)


class WebhooksConfig(AppConfig):
    """Configuration for webhooks app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.webhooks'
    verbose_name = 'Webhooks'

    def ready(self):
        """
        Initialize webhook app when Django is ready.

        This method is called when Django starts up and is used to:
        - Initialize the ODPS event subscriber
        - Register event handlers
        """
        try:
            # Initialize ODPS event subscriber
            from hub.apps.webhooks.odps_event_subscriber import initialize_odps_event_subscriber
            # Initialize mesh event subscriber
            from hub.apps.webhooks.mesh_event_subscriber import initialize_mesh_event_subscriber
            # Initialize virtualization event subscriber
            from hub.apps.webhooks.virtualization_event_subscriber import initialize_virtualization_event_subscriber

            # Only initialize if not in migration mode
            import sys
            if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
                initialize_odps_event_subscriber()
                initialize_mesh_event_subscriber()
                initialize_virtualization_event_subscriber()
                logger.info("webhooks_app_ready", message="Webhooks app initialized")
        except Exception as e:
            # Log but don't fail startup - subscriber will be initialized when needed
            logger.warning(
                "webhooks_app_initialization_deferred",
                error=str(e),
                message="Event subscriber initialization deferred"
            )

