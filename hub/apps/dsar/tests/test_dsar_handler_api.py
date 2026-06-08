"""Phase 232.2 — authenticated DSAR handler queue (real DB, no mocks)."""

from __future__ import annotations
import pytest

import pytest
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dsar.models import (
    DSARRequest,
    DSARRequestType,
    DSARStatus,
    DSARVerificationMethod,
)
from hub.apps.dsar.workflow import create_dsar_public, transition_status
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _grant_role(tenant: Tenant, user: User, role_name: str) -> None:
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name=role_name,
        defaults={"description": role_name},
    )
    # ``UserRole.tenant`` is the load-bearing field for
    # ``user.has_role(...)`` lookups (the role's own ``tenant`` is
    # denormalised down to the assignment); without it the role is
    # invisible to permission checks and every authenticated request
    # 403s.
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)



class DsarHandlerApiTests(TestCase):
    """Handler ViewSet: list, reject; permission matrix for DPO vs consumer."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dsar-h-{uid}",
            slug=f"dsar-h-{uid}",
            compliance_dsar_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.dpo = User.objects.create_user(
            email=f"dpo-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _grant_role(self.tenant, self.dpo, "DPO")

        self.consumer = User.objects.create_user(
            email=f"cons-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _grant_role(self.tenant, self.consumer, "DATA_CONSUMER")

        self.row = create_dsar_public(
            tenant_id=str(self.tenant.id),
            request_type=DSARRequestType.ACCESS,
            subject_email="subj@example.com",
            regimes=["GDPR"],
            verification_method=DSARVerificationMethod.MANUAL_REVIEW,
        )
        transition_status(self.row, DSARStatus.UNDER_REVIEW)

    @pytest.mark.integration
    def test_list_requires_handler_role(self):
        self.client.force_authenticate(user=self.consumer)
        r = self.client.get("/api/v1/dsar/requests/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_list_returns_tenant_rows_for_dpo(self):
        self.client.force_authenticate(user=self.dpo)
        r = self.client.get("/api/v1/dsar/requests/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        ids = [item["id"] for item in r.data.get("results", r.data)]
        self.assertIn(str(self.row.id), ids)

    @pytest.mark.integration
    def test_reject_transitions_status(self):
        self.client.force_authenticate(user=self.dpo)
        url = f"/api/v1/dsar/requests/{self.row.id}/reject/"
        r = self.client.post(url, {"reason": "Duplicate / vexatious"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["status"], DSARStatus.CLOSED_REJECTED)
        refreshed = DSARRequest.objects.get(pk=self.row.pk)
        self.assertEqual(refreshed.status, DSARStatus.CLOSED_REJECTED)
