"""
Phase 235.4.11 — Impersonation middleware.

Tags ``request.impersonation_session_id`` whenever the request's JWT
carries the ``impersonation_session_id`` claim minted by
``POST /api/v1/admin/impersonate/``. Audit emitters can then pick the
session UUID off the request and stamp it into ``details_json`` on
every event they write under the impersonation JWT — turning every
audit row written while the operator is impersonating into a row that
is forensically linked to the session.

Why a separate middleware (and not just an auth-middleware tweak)?
================================================================

The platform's ``TenantScopingMiddleware`` already decodes the JWT
to set ``request.tenant`` and ``request.user``. Bolting the
impersonation claim onto that surface would:

1.  Couple two unrelated concerns (auth + impersonation tagging)
    and risk a regression where a refactor of the tenant-scoping
    path silently dropped the claim.
2.  Make it harder for audit emitters to consume — they would have
    to import the auth module to discover the convention.

A dedicated middleware that runs AFTER ``TenantScopingMiddleware``
(so ``request.tenant`` is already populated) reads the
``Authorization`` header, decodes the token without DB-version
verification (the verification already happened in the auth path),
and tags ``request.impersonation_session_id``.

Bypass contract
===============

* If the request has no ``Authorization`` header → no tagging.
* If the token does not carry the claim → no tagging.
* If the claim is present but the referenced ``ImpersonationSession``
  is ENDED → no tagging (the JWT may outlive the session if the
  operator clicked Exit before the JWT's natural ``exp``; we trust
  the session row over the token claim).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class ImpersonationMiddleware:
    """Tags ``request.impersonation_session_id`` when the JWT carries it."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self._tag_request(request)
        return self.get_response(request)

    @staticmethod
    def _extract_bearer_token(request: HttpRequest) -> str | None:
        auth = request.META.get("HTTP_AUTHORIZATION") or ""
        if not auth.lower().startswith("bearer "):
            return None
        return auth.split(" ", 1)[1].strip()

    def _tag_request(self, request: HttpRequest) -> None:
        # Default: no impersonation. Set as attribute so downstream
        # callers can ``getattr(request, "impersonation_session_id", None)``
        # without having to ``hasattr``.
        request.impersonation_session_id = None  # type: ignore[attr-defined]  # Django HttpRequest monkey-patch; set before access

        token = self._extract_bearer_token(request)
        if not token:
            return

        try:
            # Lazy import — module load order during Django startup
            # is sensitive (settings have to be configured before
            # ``jwt_utils`` decoding can run).
            from hub.apps.auth.jwt_utils import JWTTokenGenerator

            payload = JWTTokenGenerator.decode_access_token(token, verify_version=False)
        except Exception:  # pragma: no cover — token decoding is best-effort
            return
        if not payload:
            return

        sess_id = payload.get("impersonation_session_id")
        if not sess_id:
            return

        # Validate the session is still ACTIVE — a JWT may outlive
        # its session if the operator clicked Exit before the JWT's
        # natural ``exp``. We trust the row over the claim.
        #
        # The lookup MUST route through the ``admin`` BYPASSRLS alias
        # because at middleware-run time the request's tenant context
        # is the impersonated user's tenant — which equals
        # ``impersonated_tenant_id`` for the session, so the policy
        # would in fact match — BUT the GUC is set later by the
        # tenant-scoping middleware's downstream view-time hooks, NOT
        # at this middleware's run point in environments where
        # ``app.rls_impersonation_sessions_enabled='true'`` is flipped
        # on. Defaulting to admin keeps the lookup correct under any
        # RLS rollout.
        try:
            from .models import ImpersonationSession, ImpersonationSessionStatus

            sess = ImpersonationSession.objects.using("admin").only("status").get(pk=sess_id)
        except Exception:
            return
        if sess.status != ImpersonationSessionStatus.ACTIVE:
            return

        request.impersonation_session_id = str(sess_id)  # type: ignore[attr-defined]  # Django HttpRequest monkey-patch; set before access
