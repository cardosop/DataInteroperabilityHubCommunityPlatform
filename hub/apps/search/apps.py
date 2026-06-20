"""
Search App Configuration
"""

from django.apps import AppConfig


class SearchConfig(AppConfig):
    """Search app configuration"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hub.apps.search"
    verbose_name = "Search"

    def ready(self):
        """Import business rules and register deprecated endpoints."""
        import hub.apps.search.business_rules  # noqa: F401 - Import to register business rules

        # Register SearchViewSet deprecation in the central
        # APIVersionManager so the deprecation calendar is
        # queryable at runtime.
        try:
            from hub.apps.api.versioning import (
                APIVersionManager,
                DeprecatedEndpoint,
            )

            for action in ("search", "suggestions", "track-click", "analytics", "rebuild-index"):
                path = f"/api/v1/search/{action}/" if action != "search" else "/api/v1/search/"
                APIVersionManager.register_deprecated_endpoint(
                    DeprecatedEndpoint(
                        path=path,
                        method="GET" if action not in ("track-click", "rebuild-index") else "POST",
                        deprecated_since="2026-03-19",
                        sunset_date="2026-04-18",
                        replacement="/api/search/",
                        migration_guide="Phase 54: migrate to UnifiedSearchView at /api/search/",
                    )
                )
        except Exception:
            pass
