"""Phase 5 (task 5.3) — the Delta Sharing protocol's bearer-token auth.

``DeltaShareTokenAuthentication`` resolves the Authorization header
through the 5.2 registry (``DeltaShareToken.resolve`` — the sha256 hash
lookup, never the plaintext), enforces expiry, stamps ``last_used_at``,
and returns ``(AnonymousUser(), token)`` — DRF puts the token on
``request.auth`` (what the views read) while ``request.user`` stays
user-shaped (the API middleware checks ``is_authenticated`` on every
response). Missing/unknown/expired credentials return None — DRF
converts that to the view's 401 (the protocol's
``WWW-Authenticate: Bearer`` challenge), and the 401 path emits
``WAREHOUSE_SHARE_AUTH_FAILED`` best-effort (the UC-DB-012 contract;
an unresolvable token has no tenant — the row carries none).
"""

from __future__ import annotations

import logging

from rest_framework.authentication import BaseAuthentication

logger = logging.getLogger(__name__)


class DeltaShareTokenAuthentication(BaseAuthentication):
    """Bearer-token auth for the protocol surface — no sessions, no
    DRF user; the token IS the credential (``authenticate_header``
    returns "Bearer" so the 401 carries the protocol's challenge)."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, credentials = header.partition(" ")
        if scheme.lower() != self.keyword.lower() or not credentials.strip():
            return None

        from hub.apps.databricks_admin.models import DeltaShareToken

        token = DeltaShareToken.resolve(credentials.strip())
        if token is None:
            return None

        from django.utils import timezone

        if token.expires_at is not None and token.expires_at <= timezone.now():
            # An expired token authenticates as nothing — and must never
            # stamp last_used_at.
            return None

        token.last_used_at = timezone.now()
        token.save(update_fields=["last_used_at"])

        # DRF maps (user, auth) onto request.user / request.auth: the
        # TOKEN must ride request.auth (the views read it there) while
        # request.user stays user-shaped (the API middleware checks
        # request.user.is_authenticated on every response).
        from django.contrib.auth.models import AnonymousUser

        return AnonymousUser(), token

    def authenticate_header(self, _request):
        return self.keyword
