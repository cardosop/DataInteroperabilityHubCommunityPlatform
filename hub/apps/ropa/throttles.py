"""Phase 283.3.3.4 — scoped throttles for RoPA views.

Keyed on tenant_id so tenant A's exhaustion does not affect tenant B.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class RopaUserThrottle(SimpleRateThrottle):
    scope = "ropa_user"

    def __init__(self):
        self.rate = getattr(settings, "ROPA_RATE_LIMIT_PER_MIN", "10/min")
        super().__init__()

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            tenant_id = getattr(request.user, "tenant_id", None)
            return f"throttle_ropa_{tenant_id}_{request.user.pk}"
        return self.get_ident(request)
