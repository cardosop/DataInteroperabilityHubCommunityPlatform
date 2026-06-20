"""RoPA REST API — preview cache, RBAC gate, sync/async generate (real middleware + DB)."""

from __future__ import annotations

import uuid

import pytest
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.ropa.models import RopaGeneration, RopaGenerationStatus, RopaOutputFormat
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class RopaApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"ropa-api-{uid}",
            slug=f"ropa-api-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_ropa_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = self._tenant_admin_user(uid)
        role, _ = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)

    def tearDown(self):
        cache.clear()

    def _tenant_admin_user(self, uid_fragment: str):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            email=f"ropa-{uid_fragment}@example.com",
            password="test-pass-123!",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_preview_miss_then_hit_then_invalidate_after_asset_save(self):
        self.client.force_authenticate(user=self.user)
        url = "/api/v1/ropa/generations/preview/"
        first = self.client.get(url, {"regulation": "GDPR"})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertFalse(first.data.get("cache_hit"))

        second = self.client.get(url, {"regulation": "GDPR"})
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data.get("cache_hit"))

        Asset.objects.create(
            tenant=self.tenant,
            key="inv-cache",
            name="invalidate preview",
            status=AssetStatus.ACTIVE,
        )
        third = self.client.get(url, {"regulation": "GDPR"})
        self.assertEqual(third.status_code, status.HTTP_200_OK)
        self.assertFalse(third.data.get("cache_hit"))

    @pytest.mark.integration
    def test_preview_403_when_feature_disabled(self):
        self.client.force_authenticate(user=self.user)
        self.tenant.compliance_ropa_enabled = False
        self.tenant.save(update_fields=["compliance_ropa_enabled"])

        res = self.client.get("/api/v1/ropa/generations/preview/", {"regulation": "GDPR"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data.get("code"), "ROPA_DISABLED")

    @pytest.mark.integration
    def test_generate_json_sync_returns_201_when_under_threshold(self):
        self.client.force_authenticate(user=self.user)
        res = self.client.post("/api/v1/ropa/generate/?regulation=GDPR&format=json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["output_format"], RopaOutputFormat.JSON)
        self.assertEqual(res.data["status"], RopaGenerationStatus.COMPLETED)
        self.assertGreater(RopaGeneration.objects.filter(tenant=self.tenant).count(), 0)

    @pytest.mark.integration
    def test_generate_low_threshold_returns_202_with_ropa_job_type(self):
        self.client.force_authenticate(user=self.user)
        # ``Asset.name`` is ``CharField(max_length=255)`` — a 400-char
        # value violates the column type. Pad ``description``
        # (``TextField``, unbounded) instead to grow the export body
        # past the 900-byte threshold below.
        for _i in range(5):
            Asset.objects.create(
                tenant=self.tenant,
                key=f"k-{uuid.uuid4().hex}",
                name="x" * 200,
                description="d" * 400,
                status=AssetStatus.ACTIVE,
            )

        with override_settings(ROPA_LARGE_EXPORT_BYTES_THRESHOLD=900):
            res = self.client.post("/api/v1/ropa/generate/?regulation=GDPR&format=json")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(res.data.get("async"))
        self.assertEqual(res.data["status"], RopaGenerationStatus.PENDING)

        job = (
            Job.objects.filter(tenant=self.tenant, type=JobType.ROPA_GENERATE)
            .order_by("-created_at")
            .first()
        )
        self.assertIsNotNone(job)
        self.assertEqual(job.status, JobStatus.PENDING)
        gen = RopaGeneration.objects.get(id=res.data["ropa_generation_id"])
        gen.refresh_from_db()
        self.assertIsNotNone(gen.job)
        self.assertEqual(gen.job.pk, job.pk)

    @pytest.mark.integration
    def test_non_handler_user_cannot_preview(self):
        from django.contrib.auth import get_user_model

        pleb = get_user_model().objects.create_user(
            email=f"nopriv-{uuid.uuid4().hex[:8]}@example.com",
            password="pw",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client.force_authenticate(user=pleb)
        res = self.client.get("/api/v1/ropa/generations/preview/", {"regulation": "GDPR"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_list_generations_paginates(self):
        self.client.force_authenticate(user=self.user)
        gen = RopaGeneration.objects.create(
            tenant=self.tenant,
            regulation="GDPR",
            output_format=RopaOutputFormat.JSON,
            status=RopaGenerationStatus.COMPLETED,
            summary_json={"asset_count": 0},
            gaps_json=[],
        )
        res = self.client.get("/api/v1/ropa/generations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in res.data["results"]]
        self.assertIn(str(gen.id), ids)
