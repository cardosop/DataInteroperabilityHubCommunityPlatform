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
        import hub.apps.search.business_rules

        # Register SearchViewSet deprecation in the central
        # APIVersionManager so the deprecation calendar is
        # queryable at runtime.  W12.10: the registered paths are the
        # REAL ViewSet routes (the pre-fix entries pointed at
        # /api/v1/search/ + hyphenated action names that never matched
        # a route), and the dates are the CANONICAL contract the view
        # advertised since 2026-05-12 (90-day sunset window ending
        # 2026-08-10).  The middleware enforces 410 after the sunset
        # date and emits the header contract until then — the view
        # hardcodes nothing.
        try:
            from hub.apps.api.versioning import (
                APIVersionManager,
                DeprecatedEndpoint,
            )

            for action, method in (
                ("search", "GET"),
                ("suggestions", "GET"),
                ("track_click", "POST"),
                ("analytics", "GET"),
                ("rebuild_index", "POST"),
            ):
                path = f"/api/v1/search/{action}/"
                APIVersionManager.register_deprecated_endpoint(
                    DeprecatedEndpoint(
                        path=path,
                        method=method,
                        deprecated_since="2026-05-12",
                        sunset_date="2026-08-10",
                        replacement="/api/search/",
                        migration_guide="Phase 54: migrate to UnifiedSearchView at /api/search/",
                    )
                )
        except Exception:
            pass
