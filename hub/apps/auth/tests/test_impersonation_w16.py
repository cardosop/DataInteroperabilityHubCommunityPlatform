"""
W1.6 (R2-S12) — impersonation backend pins: switch_tenant blocked +
session exit revokes.

The round-1 P0s:

1. ``switch_tenant`` under an impersonation JWT silently minted a NEW
   access token WITHOUT the ``impersonation_session_id`` claim — the
   operator kept acting as the impersonated user but the audit trail
   lost the session linkage, and the re-minted token outlived the
   session (no claim → no revocation). Fix: the switch is BLOCKED
   (403 IMPERSONATION_TENANT_SWITCH_BLOCKED + audit row carrying the
   session id) whenever the authenticated identity is impersonation-
   linked.

2. ``ImpersonationSession`` exit did not revoke anything: the
   impersonation JWT stayed cryptographically valid until its natural
   ``exp`` and kept authenticating the operator AS the impersonated
   user (the middleware merely stopped tagging). Fix: JWTAuthentication
   binds any token carrying the claim to its session row — a missing /
   ENDED session fails closed with 401 IMPERSONATION_SESSION_ENDED on
   EVERY surface (REST and GraphQL alike).

No mocks: real sessions, real JWTs, the real middleware + auth + view
stack.
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import ImpersonationSession, Tenant
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import UserStatus, UserTenantMembership

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()

ME_QUERY = "query { me { id email } }"


class ImpersonationBackendPinTest(TestCase):
    """switch_tenant blocking + session-exit revocation pins."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Impersonation Tenant {uid}",
            slug=f"imp-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.other_tenant = Tenant.objects.create(
            name=f"Impersonation Other {uid}",
            slug=f"imp-other-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.impersonator = User.objects.create_user(
            email=f"operator-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.target = User.objects.create_user(
            email=f"target-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # An active subscription so the GraphQL MVP gate does not 403
        # the gated path before the view's auth layer can answer — the
        # pin under test is the auth 401, not the plan gate.
        ensure_tenant_has_active_subscription(self.tenant)
        # The target legitimately holds membership in the other tenant —
        # the pre-fix switch would have SUCCEEDED (making the pin sharp).
        UserTenantMembership.objects.create(
            user=self.target, tenant=self.other_tenant
        )
        now = timezone.now()
        self.session = ImpersonationSession.objects.create(
            impersonator=self.impersonator,
            impersonated_user=self.target,
            impersonator_tenant=self.tenant,
            impersonated_tenant=self.tenant,
            started_at=now,
            expires_at=now + timedelta(minutes=60),
            max_minutes=60,
            reason="W1.6 impersonation pin test justification",
        )
        self.impersonation_jwt = JWTTokenGenerator.generate_access_token(
            self.target,
            tenant_id=str(self.tenant.id),
            impersonation_session_id=str(self.session.id),
        )

    def _bearer(self, token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    # ── switch_tenant under impersonation ────────────────────────────────

    def test_switch_tenant_blocked_under_impersonation(self):
        """An impersonation JWT MUST NOT switch tenants — 403 + audit."""
        response = self._bearer(self.impersonation_jwt).post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.other_tenant.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            response.json()["code"], "IMPERSONATION_TENANT_SWITCH_BLOCKED"
        )
        # The audit-trail pin: a row carrying the session id so the
        # auditor can join the blocked attempt to the session row.
        audit = AuditEvent.objects.filter(
            action="IMPERSONATION_TENANT_SWITCH_BLOCKED"
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(
            (audit.details_json or {}).get("impersonation_session_id"),
            str(self.session.id),
        )

    def test_switch_tenant_allowed_for_regular_token(self):
        """The guard must not block the normal (non-impersonation) path."""
        plain_jwt = JWTTokenGenerator.generate_access_token(
            self.target, tenant_id=str(self.tenant.id)
        )
        response = self._bearer(plain_jwt).post(
            "/api/v1/auth/switch-tenant/",
            {"tenant_id": str(self.other_tenant.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.json())

    # ── exit revokes ─────────────────────────────────────────────────────

    def test_active_session_jwt_authenticates(self):
        """The ACTIVE-session guard does not over-block (control pin)."""
        response = self._bearer(self.impersonation_jwt).get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ended_session_jwt_401s_on_rest(self):
        """Exit revokes: after ``session.end()`` the JWT stops
        authenticating on REST surfaces."""
        self.session.end(reason="manual_exit")

        response = self._bearer(self.impersonation_jwt).get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json()["error"]["code"], "IMPERSONATION_SESSION_ENDED"
        )

    def test_ended_session_jwt_401s_on_graphql(self):
        """Exit revokes on the GraphQL surface too (DRF auth on
        strawberry paths — the W1.6 GraphQL fix)."""
        # graphql is the paid layer — skip when it is not installed
        # (W7.1: the core-only suite has no GraphQL surface).
        from django.apps import apps as django_apps

        if not django_apps.is_installed("hub.apps.graphql"):
            pytest.skip("graphql (paid layer) not installed in core-only mode")
        self.session.end(reason="manual_exit")

        response = self._bearer(self.impersonation_jwt).post(
            "/graphql/", {"query": ME_QUERY}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        body = response.json()
        self.assertIn("errors", body)
        self.assertEqual(
            body["errors"][0]["extensions"]["code"],
            "IMPERSONATION_SESSION_ENDED",
        )

    def test_unknown_session_jwt_401s(self):
        """A claim referencing a nonexistent session fails closed."""
        bogus_jwt = JWTTokenGenerator.generate_access_token(
            self.target,
            tenant_id=str(self.tenant.id),
            impersonation_session_id=str(uuid.uuid4()),
        )
        response = self._bearer(bogus_jwt).get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.json()["error"]["code"], "IMPERSONATION_SESSION_ENDED"
        )

    def test_plain_token_without_claim_unaffected(self):
        """Tokens without the claim are untouched by the session check."""
        plain_jwt = JWTTokenGenerator.generate_access_token(
            self.target, tenant_id=str(self.tenant.id)
        )
        response = self._bearer(plain_jwt).get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
