"""Phase 283.3.1.2 — scoped throttles for consent views.

Keyed on tenant_id so tenant A's exhaustion does not affect tenant B.
Rate values come from Django settings with documented defaults.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ConsentUserThrottle(SimpleRateThrottle):
    scope = "consent_user"

    def __init__(self):
        # Set rate BEFORE super().__init__() — SimpleRateThrottle.__init__
        # calls get_rate() which throws ImproperlyConfigured if the scope
        # is not in DEFAULT_THROTTLE_RATES.  Setting .rate first makes
        # DRF skip the get_rate() lookup.
        self.rate = getattr(settings, "CONSENT_RATE_LIMIT_PER_MIN", "30/min")
        super().__init__()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            tenant_id = getattr(request.user, "tenant_id", None)
            return f"throttle_consent_{tenant_id}_{request.user.pk}"
        return self.get_ident(request)


class ConsentDashboardThrottle(SimpleRateThrottle):
    scope = "consent_dashboard"

    def __init__(self):
        self.rate = getattr(settings, "CONSENT_DASHBOARD_RATE_LIMIT_PER_MIN", "10/min")
        super().__init__()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            tenant_id = getattr(request.user, "tenant_id", None)
            return f"throttle_consent_dashboard_{tenant_id}_{request.user.pk}"
        return self.get_ident(request)
