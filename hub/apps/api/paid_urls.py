"""Phase 313.1 — paid-layer URL registry.

Core owns the mount point; paid apps register their full URL prefixes from
``AppConfig.ready()``. In core-only mode (``HUB_CORE_ONLY=1``) this module is
never included, so no paid path exists and OpenAPI generation stays core-only.

Resolution order: Django evaluates ``include("hub.apps.api.paid_urls")``
lazily at first URLconf load, which happens AFTER every app's ``ready()`` has
run — the registry is fully populated by then. Registrations are idempotent
(duplicate-equivalent patterns are skipped), so a repeated ``ready()`` during
test reloads cannot double-register.
"""

from importlib import import_module

# Full-path prefixes registered by paid apps (ready() callbacks). The empty
# root mount in hub/urls.py means each entry carries its complete path
# (e.g. "api/v1/marketplace/" or "graphql/").
_PAID_URLPATTERNS: list = []


class LazyURLConf:
    """Defer importing a URLconf module until the first request to its prefix.

    Moved from ``hub/urls.py`` (Phase 313.1) so paid apps can reuse it without
    importing the root URLconf (which would create an import cycle).
    """

    def __init__(self, module_path: str):
        self._module_path = module_path
        self._urlconf = None

    @property
    def urlpatterns(self):
        if self._urlconf is None:
            self._urlconf = import_module(self._module_path)
        return self._urlconf.urlpatterns


def register_paid_urlpatterns(patterns) -> None:
    """Register URL patterns for a paid app. Call from ``AppConfig.ready()``."""
    for pattern in patterns:
        if pattern not in _PAID_URLPATTERNS:
            _PAID_URLPATTERNS.append(pattern)


# urlpatterns references the SAME list object that registrations mutate —
# Django reads this attribute after ready() has populated it.
urlpatterns = _PAID_URLPATTERNS
