"""
API App Configuration

Django app configuration for API app with URL pattern validation at startup.
"""

import structlog
from django.apps import AppConfig

logger = structlog.get_logger(__name__)


class ApiConfig(AppConfig):
    """Configuration for API app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.api"

    def ready(self):
        """
        Initialize API app when Django is ready.

        This method is called when Django starts up and is used to:
        - Validate URL patterns against naming standards
        - Register Django system checks (deploy-only) for MVP_MODE and E2E_TEST_SECRET
        """
        # Register deploy-only system checks. Importing the module triggers
        # @register() side-effects. Checks are gated with deploy=True so they
        # only fire on `manage.py check --deploy`, not during migrate/collectstatic.
        from hub.apps.api import checks  # noqa: F401

        # Only validate in non-migration contexts
        if self._should_validate():
            try:
                from hub.apps.api.utils.url_pattern_validator import validate_url_patterns

                # Validate URL patterns (warnings only, don't fail startup)
                result = validate_url_patterns(strict=False, raise_on_error=False)

                if not result.passed:
                    logger.error(
                        "url_pattern_validation_failed_at_startup",
                        errors=len(result.errors),
                        warnings=len(result.warnings),
                        message="URL pattern validation found issues at startup",
                    )
                    # Log formatted errors for debugging
                    from hub.apps.api.utils.url_pattern_validator import URLPatternValidator

                    validator = URLPatternValidator()
                    error_message = validator.format_errors(result)
                    logger.error("url_pattern_validation_details", details=error_message)
                else:
                    logger.info(
                        "url_pattern_validation_passed_at_startup",
                        total_patterns=result.total_patterns,
                        message="URL pattern validation passed at startup",
                    )

            except Exception as e:
                # Log but don't fail startup - validation is non-critical
                logger.warning(
                    "url_pattern_validation_deferred",
                    error=str(e),
                    message="URL pattern validation deferred due to error",
                )

    def _should_validate(self) -> bool:
        """
        Determine if URL pattern validation should run.

        Skip validation during migrations, tests, and other management commands.
        """
        from hub.apps.core.utils.test_mode import should_skip_initialization

        # Skip during tests, migrations, and other management commands
        if should_skip_initialization():
            return False

        return True
