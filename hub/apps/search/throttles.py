"""
Phase 273.2 — rate-limit throttle classes for the search hot path.

Keyed on tenant_id via DRF's ``UserRateThrottle`` so tenant A's
exhaustion does not affect tenant B. The rate values come from
Django settings (env-vars with documented defaults).

Phase 273.3 — ``throttled()`` override emits SEARCH_RATE_LIMIT_EXCEEDED
audit event on every 429 response. Wrapped in try/except so audit-DB
outage never blocks the throttle response.
"""
from django.conf import settings
from rest_framework.throttling import UserRateThrottle


class _AuditableThrottle(UserRateThrottle):
    """Base class that emits audit events on rate-limit hits."""

    audit_action: str = "SEARCH_RATE_LIMIT_EXCEEDED"

    def throttled(self, request, wait):
        """Emit metric + audit event on 429, then delegate to parent."""
        # Phase 273.4 — record throttled outcome before audit.
        try:
            from hub.apps.search.metrics import record_search

            query = request.GET.get("q", "") or request.data.get("query", "")
            record_search(
                kind="fts",
                outcome="throttled",
                duration_s=0.0,
                result_count=0,
                query_length=len(query.encode("utf-8")) if query else 0,
            )
        except Exception:
            pass
        try:
            from hub.apps.audit.event_types import (
                SEARCH_RATE_LIMIT_EXCEEDED,
                SPARQL_RATE_LIMIT_EXCEEDED,
            )
            from hub.apps.audit.utils import create_audit_event

            action = (
                SPARQL_RATE_LIMIT_EXCEEDED
                if "sparql" in self.audit_action.lower()
                else SEARCH_RATE_LIMIT_EXCEEDED
            )
            query = request.GET.get("q", "") or request.data.get("query", "")
            create_audit_event(
                resource_type="SEARCH_QUERY",
                action=action,
                actor_user=request.user if request.user.is_authenticated else None,
                tenant=getattr(request.user, "tenant", None) if request.user.is_authenticated else None,
                resource_id=None,
                result="THROTTLED",
                details={
                    "query_truncated": query[:256] if query else "",
                    "remote_addr": request.META.get("REMOTE_ADDR", ""),
                    "wait_seconds": int(wait),
                },
                infer_tenant_from_actor=True,
            )
        except Exception:
            pass
        super().throttled(request, wait)


class SearchUserThrottle(_AuditableThrottle):
    """Throttle for UnifiedSearchView + SearchViewSet search/suggestions."""

    audit_action = "SEARCH_RATE_LIMIT_EXCEEDED"

    def __init__(self):
        super().__init__()
        self.rate = getattr(settings, "SEARCH_RATE_LIMIT_PER_MIN", "60/min")

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_search_{request.user.tenant_id}"
        return self.get_ident(request)


class SuggestionsUserThrottle(_AuditableThrottle):
    """Throttle for autocomplete/suggestions endpoint (higher limit)."""

    audit_action = "SEARCH_RATE_LIMIT_EXCEEDED"

    def __init__(self):
        super().__init__()
        self.rate = getattr(settings, "SUGGESTIONS_RATE_LIMIT_PER_MIN", "120/min")

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return f"throttle_suggestions_{request.user.tenant_id}"
        return self.get_ident(request)
