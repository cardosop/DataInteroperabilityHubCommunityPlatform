"""
Integration tests for the ApprovalDelegation API surface (Phase 272.6).

The FE consumer is DelegationSettingsPage (frontend
`/settings/delegation`, TENANT_ADMIN|PLATFORM_ADMIN). These tests pin the
FE-frozen contract:

- GET  /api/v1/governance/delegations/      → a PLAIN ARRAY (no pagination)
- POST /api/v1/governance/delegations/      → 201; validation errors surface
  under ``{"detail": "..."}`` (the page reads ``body.detail``)
- DELETE /api/v1/governance/delegations/{id}/ → 204 (the page's Revoke)

Real DB and real audit events. No mocks.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.governance.models import ApprovalDelegation
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

LIST_URL = "/api/v1/governance/delegations/"


class DelegationApiBase(TestCase):
    """Shared fixture block: a tenant with a TENANT_ADMIN + a delegate."""

    def setUp(self):
        self.client = APIClient()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Delegation Tenant {uid}",
            slug=f"delegation-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        def make_user(prefix, *, roles=(), display_name=""):
            user = User.objects.create_user(
                email=f"{prefix}-{uid}@example.com",
                password="testpass123",
                tenant=self.tenant,
                status=UserStatus.ACTIVE,
                display_name=display_name,
            )
            for role_name in roles:
                role, _ = Role.objects.get_or_create(tenant=self.tenant, name=role_name)
                UserRole.objects.get_or_create(user=user, role=role)
            return user

        self.admin = make_user("ta", roles=("TENANT_ADMIN",))
        self.delegate = make_user("delegate", display_name="Delegate User")
        self.provider = make_user("provider", roles=("DATA_PROVIDER",))

        now = timezone.now()
        self.valid_window = {
            "delegate_email": self.delegate.email,
            "start_at": (now - timedelta(hours=1)).isoformat(),
            "end_at": (now + timedelta(days=1)).isoformat(),
            "reason": "Out of office",
        }


class DelegationListTests(DelegationApiBase):
    def test_anon_get_returns_401(self):
        resp = self.client.get(LIST_URL)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_non_admin_get_returns_403_auth_forbidden(self):
        self.client.force_authenticate(user=self.provider)
        resp = self.client.get(LIST_URL)
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        body = resp.json()
        assert body.get("error", {}).get("code") == "AUTH_FORBIDDEN", body

    def test_tenant_admin_get_returns_paginated_shape(self):
        # The platform-standard pagination envelope — the FE reads
        # ``data.results`` (array-or-results tolerant).
        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["count"] == 0
        assert body["results"] == []
        assert {"count", "next", "previous", "results"} <= set(body)

    def test_list_is_tenant_isolated(self):
        other = Tenant.objects.create(
            name="Other Tenant",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        ensure_tenant_has_active_subscription(other)
        other_admin = User.objects.create_user(
            email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other,
            status=UserStatus.ACTIVE,
        )
        other_role, _ = Role.objects.get_or_create(tenant=other, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=other_admin, role=other_role)
        other_delegate = User.objects.create_user(
            email=f"other-delegate-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other,
            status=UserStatus.ACTIVE,
        )
        now = timezone.now()
        ApprovalDelegation.objects.create(
            tenant=other,
            delegator=other_admin,
            delegate=other_delegate,
            start_at=now,
            end_at=now + timedelta(days=1),
        )

        self.client.force_authenticate(user=self.admin)
        resp = self.client.get(LIST_URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["results"] == []


class DelegationCreateTests(DelegationApiBase):
    def test_create_future_window_returns_201_with_fe_shape(self):
        self.client.force_authenticate(user=self.admin)
        now = timezone.now()
        resp = self.client.post(
            LIST_URL,
            {
                "delegate_email": self.delegate.email,
                "start_at": (now + timedelta(hours=2)).isoformat(),
                "end_at": (now + timedelta(days=2)).isoformat(),
                "reason": "Conference next week",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        body = resp.json()
        assert body["delegate_email"] == self.delegate.email
        assert body["delegate_name"] == self.delegate.display_name
        assert body["reason"] == "Conference next week"
        assert body["is_active"] is False
        assert set(body) == {
            "id",
            "delegate_email",
            "delegate_name",
            "start_at",
            "end_at",
            "reason",
            "is_active",
            "created_at",
        }
        row = ApprovalDelegation.objects.get(id=body["id"])
        assert row.tenant == self.tenant
        assert row.delegator == self.admin
        assert row.delegate == self.delegate

    def test_create_active_window_marks_active(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(LIST_URL, self.valid_window, format="json")
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()["is_active"] is True

    def test_create_without_reason_succeeds(self):
        # The FE drops undefined fields via JSON.stringify — the omitted
        # reason key must not KeyError the view (the 4.5 live run's 500).
        self.client.force_authenticate(user=self.admin)
        payload = dict(self.valid_window)
        payload.pop("reason")
        resp = self.client.post(LIST_URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        assert resp.json()["reason"] is None

    def test_create_emits_audit_event(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(LIST_URL, self.valid_window, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        event = AuditEvent.objects.filter(action="DELEGATION_CREATED").latest("timestamp")
        assert event.actor_user == self.admin
        assert event.tenant == self.tenant
        assert str(event.resource_id) == resp.json()["id"]
        # The audit layer sanitizes PII (emails masked) — pin the field's
        # presence and the surviving domain, never the raw address.
        assert "@example.com" in event.details_json["delegate_email"]

    def test_create_rejects_unknown_delegate_email(self):
        self.client.force_authenticate(user=self.admin)
        payload = dict(self.valid_window)
        payload["delegate_email"] = "ghost@example.com"
        resp = self.client.post(LIST_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "active user" in resp.json()["detail"]

    def test_create_rejects_cross_tenant_delegate(self):
        other = Tenant.objects.create(
            name="Other Tenant",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        stranger = User.objects.create_user(
            email=f"stranger-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.admin)
        payload = dict(self.valid_window)
        payload["delegate_email"] = stranger.email
        resp = self.client.post(LIST_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "active user" in resp.json()["detail"]

    def test_create_rejects_end_before_start(self):
        self.client.force_authenticate(user=self.admin)
        now = timezone.now()
        resp = self.client.post(
            LIST_URL,
            {
                "delegate_email": self.delegate.email,
                "start_at": (now + timedelta(days=2)).isoformat(),
                "end_at": (now + timedelta(days=1)).isoformat(),
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "after start date" in resp.json()["detail"]

    def test_create_rejects_self_delegation(self):
        self.client.force_authenticate(user=self.admin)
        payload = dict(self.valid_window)
        payload["delegate_email"] = self.admin.email
        resp = self.client.post(LIST_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "yourself" in resp.json()["detail"]

    def test_create_rejects_overlapping_pair(self):
        self.client.force_authenticate(user=self.admin)
        first = self.client.post(LIST_URL, self.valid_window, format="json")
        assert first.status_code == status.HTTP_201_CREATED
        second = self.client.post(LIST_URL, self.valid_window, format="json")
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "overlap" in second.json()["detail"].lower()


class DelegationDestroyTests(DelegationApiBase):
    def setUp(self):
        super().setUp()
        now = timezone.now()
        self.row = ApprovalDelegation.objects.create(
            tenant=self.tenant,
            delegator=self.admin,
            delegate=self.delegate,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(days=1),
            reason="Out of office",
        )

    def test_delete_removes_row_and_emits_audit(self):
        self.client.force_authenticate(user=self.admin)
        resp = self.client.delete(f"{LIST_URL}{self.row.id}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not ApprovalDelegation.objects.filter(id=self.row.id).exists()
        event = AuditEvent.objects.filter(action="DELEGATION_REVOKED").latest("timestamp")
        assert str(event.resource_id) == str(self.row.id)
        assert event.actor_user == self.admin

    def test_delete_cross_tenant_returns_404(self):
        other = Tenant.objects.create(
            name="Other Tenant",
            slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        ensure_tenant_has_active_subscription(other)
        other_admin = User.objects.create_user(
            email=f"other-admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other,
            status=UserStatus.ACTIVE,
        )
        other_role, _ = Role.objects.get_or_create(tenant=other, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=other_admin, role=other_role)
        self.client.force_authenticate(user=other_admin)
        resp = self.client.delete(f"{LIST_URL}{self.row.id}/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert ApprovalDelegation.objects.filter(id=self.row.id).exists()

    def test_non_admin_delete_returns_403(self):
        self.client.force_authenticate(user=self.provider)
        resp = self.client.delete(f"{LIST_URL}{self.row.id}/")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert ApprovalDelegation.objects.filter(id=self.row.id).exists()
