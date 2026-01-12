from django.apps import AppConfig
import structlog

logger = structlog.get_logger(__name__)


class ContractsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'hub.apps.contracts'

    def ready(self):
        """
        Initialize contracts app when Django is ready.

        This method is called when Django starts up and is used to:
        - Initialize cache warming on startup
        """
        try:
            # Only initialize if not in migration mode
            import sys
            if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
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
