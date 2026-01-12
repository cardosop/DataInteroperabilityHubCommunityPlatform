from django.apps import AppConfig
import structlog

logger = structlog.get_logger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.notifications'

    def ready(self):
        """Initialize notifications app when Django is ready."""
        try:
            # Import signals
            import hub.apps.notifications.signals  # noqa

            # Initialize ODPS notification subscriber
            from hub.apps.notifications.odps_event_subscriber import initialize_odps_notification_subscriber

            # Only initialize if not in migration mode
            import sys
            if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
                initialize_odps_notification_subscriber()
                logger.info("notifications_app_ready", message="Notifications app initialized")
        except Exception as e:
            # Log but don't fail startup - subscriber will be initialized when needed
            logger.warning(
                "notifications_app_initialization_deferred",
                error=str(e),
                message="Event subscriber initialization deferred"
            )

