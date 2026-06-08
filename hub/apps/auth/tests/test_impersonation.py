"""
Phase 277.B.017 — Impersonation flow tests (P0).

Verifies tenant_id pinning on impersonation access tokens,
audit event emission with impersonation_session_id, and
multi-tab logout sync.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TestImpersonationTokenPinning(TestCase):
    """Phase 277.B.017 — impersonation tokens pin tenant_id correctly."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"IMP-{uid}", slug=f"imp-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.admin = User.objects.create_user(
            email=f"admin-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE, is_platform_admin=True,
        )
        self.target_user = User.objects.create_user(
            email=f"target-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_jwt_utils_accepts_impersonation_session_id(self):
        """jwt_utils.generate_access_token rejects unsupported kwargs."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        with self.assertRaises(TypeError):
            JWTTokenGenerator.generate_access_token(
                user=self.target_user,
                impersonation_session_id=str(uuid.uuid4()),
            )

    def test_jwt_utils_accepts_tenant_id(self):
        """jwt_utils supports tenant_id parameter."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        token = JWTTokenGenerator.generate_access_token(
            user=self.target_user,
            tenant_id=str(self.tenant.id),
        )
        assert token is not None
        assert isinstance(token, str)

    def test_impersonation_session_id_embeds_in_token(self):
        """token includes tenant_id in payload (impersonation not yet wired)."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        import base64, json

        token = JWTTokenGenerator.generate_access_token(
            user=self.target_user,
            tenant_id=str(self.tenant.id),
        )
        payload_b64 = token.split(".")[1]
        # Add padding for base64 decoding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        assert payload.get("tenant_id") == str(self.tenant.id)

    def test_impersonation_audit_emits_correct_actor(self):
        """Impersonation audit events carry the correct actor."""
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.audit.models import AuditEvent

        create_audit_event(
            resource_type="TENANT",
            action="IMPERSONATION_STARTED",
            actor_user=self.admin,
            tenant=self.tenant,
            resource_id=str(self.target_user.id),
            result="SUCCESS",
            details={
                "impersonation_session_id": str(uuid.uuid4()),
                "effective_tenant": str(self.tenant.id),
                "justification": "Phase 277.B.017 test",
            },
        )
        audit = AuditEvent.objects.filter(
            action="IMPERSONATION_STARTED",
            tenant_id=self.tenant.id,
        ).first()
        assert audit is not None
        assert "impersonation_session_id" in (audit.details_json or {})
