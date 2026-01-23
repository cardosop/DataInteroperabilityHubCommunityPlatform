from django.apps import AppConfig
import structlog
from hub.apps.core.utils.test_mode import should_skip_initialization

logger = structlog.get_logger(__name__)


class AuditConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.audit'

    def ready(self):
        """
        Initialize audit app when Django is ready.
        
        Initialization is deferred during tests for performance.
        """
        # Skip initialization during tests and migrations for performance
        if should_skip_initialization():
            logger.debug("audit_app_init_skipped", reason="test_or_migration_mode")
            return
        
        try:
            # Initialize ODPS audit subscriber
            from hub.apps.audit.odps_event_subscriber import initialize_odps_audit_subscriber
            initialize_odps_audit_subscriber()
            logger.info("audit_app_ready", message="Audit app initialized")
        except Exception as e:
            # Log but don't fail startup - subscriber will be initialized when needed
            logger.warning(
                "audit_app_initialization_deferred",
                error=str(e),
                message="Event subscriber initialization deferred"
            )
