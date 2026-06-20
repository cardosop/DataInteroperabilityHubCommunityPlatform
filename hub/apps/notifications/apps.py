import structlog
from django.apps import AppConfig

from hub.apps.core.utils.test_mode import should_skip_initialization

logger = structlog.get_logger(__name__)


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.notifications"

    def ready(self):
        """
        Initialize notifications app when Django is ready.

        Initialization is deferred during tests for performance.
        """
        # Register business rules (Phase 75.1)
        import hub.apps.notifications.business_rules

        # Always import signals (needed for tests)
        try:
            import hub.apps.notifications.signals  # noqa
        except Exception:
            pass  # Signals may not be critical for all test scenarios

        # Skip event subscriber initialization during tests and migrations for performance
        if should_skip_initialization():
            logger.debug("notifications_app_init_skipped", reason="test_or_migration_mode")
            return

        try:
            # Initialize ODPS notification subscriber
            from hub.apps.notifications.odps_event_subscriber import (
                initialize_odps_notification_subscriber,
            )

            initialize_odps_notification_subscriber()
            logger.info("notifications_app_ready", message="Notifications app initialized")
        except Exception as e:
            # Log but don't fail startup - subscriber will be initialized when needed
            logger.warning(
                "notifications_app_initialization_deferred",
                error=str(e),
                message="Event subscriber initialization deferred",
            )
