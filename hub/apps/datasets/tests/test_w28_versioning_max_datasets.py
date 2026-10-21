"""W2.8 (R2 B-9) — versioning checks ``max_datasets``.

``DatasetService.create_version_from_dataset`` creates a NEW Dataset row
(each version is a row), but it never checked ``max_datasets`` — the
versioning path was a free pass around the dataset cap (the P1 pattern:
the check exists on dataset creation, the sibling path doesn't use it).

Evidence pins:

* **at cap → version creation blocked** with ``plan_limit_exceeded``
  (service ValidationError, http_status 403) and no new row written.
* **under cap → the version row is created** (and now counts toward
  the cap).

Real DB and the real service — no mocks/stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.services import DatasetService
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VersioningMaxDatasetsTest(TestCase):
    """create_version_from_dataset routes through the max_datasets cap."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        # A plan with a REAL max_datasets cap (the test-support free plan
        # omits the key → get_limit() would read None = unlimited).
        self.plan = TenantPlan.objects.create(
            slug=f"w28-{uid}",
            name="W2.8 Plan",
            tier=PlanTier.PRO,
            limits_json={"max_datasets": 2},
            is_active=True,
        )
        self.tenant.plan = self.plan
        self.tenant.save(update_fields=["plan"])
        self.user = User.objects.create_user(
            email=f"u-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = DatasetService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def _make_dataset(self, version):
        return Dataset.objects.create(
            tenant=self.tenant,
            asset=None,
            file=None,
            schema_json=None,
            row_count=0,
            format="csv",
            version=version,
            created_by=self.user,
        )

    def test_versioning_blocked_at_max_datasets_cap(self):
        """THE pin: at the cap, a new version row is rejected."""
        first = self._make_dataset(1)
        self._make_dataset(2)

        with pytest.raises(ValidationError) as ctx:
            self.service.create_version_from_dataset(
                source_dataset_id=str(first.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                semantic_version="1.1.0",
            )
        self.assertEqual(ctx.value.code, "plan_limit_exceeded")
        self.assertEqual(
            Dataset.objects.filter(tenant=self.tenant).count(),
            2,
            "no version row may be written when the cap blocks",
        )

    def test_versioning_allowed_under_cap(self):
        first = self._make_dataset(1)
        result = self.service.create_version_from_dataset(
            source_dataset_id=str(first.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            semantic_version="1.1.0",
        )

        self.assertEqual(result.version, 2)
        self.assertEqual(Dataset.objects.filter(tenant=self.tenant).count(), 2)
