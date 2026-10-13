"""
W4.3 / E5 — consent-purpose key partial unique index.

``consent_purpose_tenant_key_uniq`` was a FULL unique constraint on
(tenant, key) — re-creating a purpose after deactivating it
(``is_active=False``) raised IntegrityError (500). The fix relaxes the
constraint to a partial unique index over ACTIVE rows only:

* re-creating a deactivated key is legitimate (new row, active);
* creating a duplicate ACTIVE key is refused with a clean 400
  (pre-fix: 500 IntegrityError with no message);
* reactivating the OLD row while a NEW active row holds the key is
  refused with a clean 400 (the new edge the partial index introduces).

No mocks — real rows through the real ViewSet.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.consent.models import ConsentPurpose
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

PURPOSES_URL = "/api/v1/consent/consent-purposes/"


class PurposeRecreateTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
            role=role,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.key = f"purpose-{uid}"

    def _create(self, key: str, *, is_active: bool = True):
        return self.client.post(
            PURPOSES_URL,
            {
                "key": key,
                "name": "Purpose",
                "description": "pin",
                "retention_days": 30,
                "is_active": is_active,
            },
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _patch(self, purpose_id, *, is_active: bool):
        return self.client.patch(
            f"{PURPOSES_URL}{purpose_id}/",
            {"is_active": is_active},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    @pytest.mark.integration
    def test_recreate_key_after_deactivation_succeeds(self):
        """Re-creating a deactivated purpose's key is legitimate.

        Pre-fix, the full unique constraint made the second create raise
        IntegrityError (500) — the key was permanently burned.
        """
        first = self._create(self.key)
        assert first.status_code == status.HTTP_201_CREATED, first.data
        assert (
            self._patch(first.data["id"], is_active=False).status_code
            == status.HTTP_200_OK
        )

        second = self._create(self.key)
        assert second.status_code == status.HTTP_201_CREATED, second.data
        assert second.data["id"] != first.data["id"]
        assert (
            ConsentPurpose.objects.filter(tenant=self.tenant, key=self.key).count() == 2
        )

    @pytest.mark.integration
    def test_duplicate_active_key_create_is_400(self):
        """Creating a duplicate ACTIVE key is refused with a clean 400
        (pre-fix: an unhandled IntegrityError 500)."""
        first = self._create(self.key)
        assert first.status_code == status.HTTP_201_CREATED, first.data

        duplicate = self._create(self.key)
        assert duplicate.status_code == status.HTTP_400_BAD_REQUEST
        assert "key" in duplicate.data

    @pytest.mark.integration
    def test_reactivation_conflict_is_400(self):
        """Reactivating the OLD row while a NEW active row holds the key is
        refused with a clean 400 (the edge the partial index introduces —
        it must not surface as a 500)."""
        first = self._create(self.key)
        assert first.status_code == status.HTTP_201_CREATED, first.data
        assert (
            self._patch(first.data["id"], is_active=False).status_code
            == status.HTTP_200_OK
        )
        second = self._create(self.key)
        assert second.status_code == status.HTTP_201_CREATED, second.data

        reactivate = self._patch(first.data["id"], is_active=True)
        assert reactivate.status_code == status.HTTP_400_BAD_REQUEST
        assert "key" in reactivate.data
