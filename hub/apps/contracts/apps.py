from django.apps import AppConfig
import structlog
from hub.apps.core.utils.test_mode import should_skip_initialization

logger = structlog.get_logger(__name__)


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.contracts'

    def ready(self):
        """
        Initialize contracts app when Django is ready.

        This method is called when Django starts up and is used to:
        - Register post_save signals for Redis cache invalidation (15.2)
        - Initialize cache warming on startup (deferred during tests)
        """
        # Always register signals so cache invalidation fires in all environments
        import hub.apps.contracts.signals  # noqa: F401 — registers @receiver decorators
        # Skip initialization during tests and migrations for performance
        if should_skip_initialization():
            logger.debug("contracts_app_init_skipped", reason="test_or_migration_mode")
            return
        
        try:
            # Initialize startup cache warming
            from hub.apps.contracts.ref_warming import warm_cache_on_startup
            warm_cache_on_startup()
            logger.info("contracts_app_ready", message="Contracts app initialized with cache warming")
        except Exception as e:
            # Log but don't fail startup - cache warming is optional
            logger.warning(
                "contracts_app_cache_warming_deferred",
                error=str(e),
                message="Cache warming initialization deferred"
            )
