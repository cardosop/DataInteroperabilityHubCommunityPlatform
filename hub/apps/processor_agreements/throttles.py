"""Phase 283.3.6.4 — scoped throttles for processor agreement views.

Keyed on tenant_id so tenant A's exhaustion does not affect tenant B.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ProcessorAgreementUserThrottle(SimpleRateThrottle):
    scope = "processor_agreement_user"

    def __init__(self):
        super().__init__()
        self.rate = getattr(settings, "PROCESSOR_AGREEMENT_RATE_LIMIT_PER_MIN", "20/min")

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            tenant_id = getattr(request.user, "tenant_id", None)
            return f"throttle_pa_{tenant_id}_{request.user.pk}"
        return self.get_ident(request)
