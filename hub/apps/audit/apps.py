from django.apps import AppConfig
import structlog

logger = structlog.get_logger(__name__)


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.audit'

    def ready(self):
        """Initialize audit app when Django is ready."""
        try:
            # Initialize ODPS audit subscriber
            from hub.apps.audit.odps_event_subscriber import initialize_odps_audit_subscriber

            # Only initialize if not in migration mode
            import sys
            if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
                initialize_odps_audit_subscriber()
                logger.info("audit_app_ready", message="Audit app initialized")
        except Exception as e:
            # Log but don't fail startup - subscriber will be initialized when needed
            logger.warning(
                "audit_app_initialization_deferred",
                error=str(e),
                message="Event subscriber initialization deferred"
            )
