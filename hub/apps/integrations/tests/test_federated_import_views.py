"""
284.A.9 — Backend tests for FederatedImportViewSet.

Real DB, mock only at provider boundary (AWS Secrets Manager resolution).
Tests the full HTTP request/response cycle through the DRF test client.
"""
import pytest

import uuid as _uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()


def _grant_role(user, tenant, role_name: str) -> None:
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name=role_name,
        defaults={"description": ""},
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


class FederatedImportViewSetTest(TestCase):
    """Test the FederatedImportViewSet endpoints with real DB.

    Uses per-method setUp (not setUpTestData) because with --reuse-db,
    class-level data creation can fail silently when unique constraints
    collide across test runs.  Per-method setUp runs inside the test's
    transaction and propagates errors properly.
    """

    def setUp(self):
        super().setUp()
        uid = _uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"test-tenant-{uid}",
            slug=f"test-tenant-{uid}",
            federated_import_enabled=True,
            marketplace_integrations_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@meshant.com",
            password="testpass123",
            tenant=self.tenant,
        )
        _grant_role(self.user, self.tenant, "TENANT_ADMIN")
        _grant_role(self.user, self.tenant, "PLATFORM_ADMIN")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_list_providers_returns_200(self):
        url = reverse("federated-import-list-providers")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, msg=f"Response: {response.content.decode()}")
        data = response.json()
        self.assertIn("providers", data, msg=f"Response: {data}")
        assert "count" in data
        assert data["count"] == 4
        assert any(p["id"] == "snowflake_marketplace" for p in data["providers"])

    @pytest.mark.integration
    def test_create_import_creates_job(self):
        url = reverse("federated-import-create-import")
        response = self.client.post(
            url,
            {
                "provider_id": "snowflake_marketplace",
                "credential_ref": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "data_strategy": "METADATA_ONLY",
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == JobStatus.PENDING
        assert data["provider_id"] == "snowflake_marketplace"

    @pytest.mark.integration
    def test_create_import_rejects_invalid_arn(self):
        url = reverse("federated-import-create-import")
        response = self.client.post(
            url,
            {
                "provider_id": "snowflake_marketplace",
                "credential_ref": "not-an-arn",
                "data_strategy": "METADATA_ONLY",
            },
            format="json",
        )
        assert response.status_code == 400

    @pytest.mark.integration
    def test_create_import_rejects_unknown_provider(self):
        url = reverse("federated-import-create-import")
        response = self.client.post(
            url,
            {
                "provider_id": "nonexistent",
                "credential_ref": "arn:aws:secretsmanager:us-east-1:123456789:secret:test",
                "data_strategy": "METADATA_ONLY",
            },
            format="json",
        )
        assert response.status_code == 400

    @pytest.mark.integration
    def test_get_status_returns_job(self):
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.FEDERATED_IMPORT,
            status=JobStatus.PENDING,
            resource_id=str(_uuid.uuid4()),
            details_json={"provider_id": "snowflake_marketplace", "credential_ref": "arn:..."},
        )
        url = reverse("federated-import-get-status", kwargs={"job_id": str(job.id)})
        response = self.client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(job.id)
        assert data["status"] == JobStatus.PENDING

    @pytest.mark.integration
    def test_get_status_404_for_wrong_tenant(self):
        other_tenant = Tenant.objects.create(
            name="other", slug="other",
            federated_import_enabled=True,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        job = Job.objects.create(
            tenant=other_tenant,
            type=JobType.FEDERATED_IMPORT,
            status=JobStatus.PENDING,
            resource_id=str(_uuid.uuid4()),
            details_json={},
        )
        url = reverse("federated-import-get-status", kwargs={"job_id": str(job.id)})
        response = self.client.get(url)
        assert response.status_code == 404

    @pytest.mark.integration
    def test_cancel_pending_job(self):
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.FEDERATED_IMPORT,
            status=JobStatus.PENDING,
            resource_id=str(_uuid.uuid4()),
            details_json={},
        )
        url = reverse("federated-import-cancel", kwargs={"job_id": str(job.id)})
        response = self.client.post(url)
        assert response.status_code == 200
        job.refresh_from_db()
        assert job.status == JobStatus.CANCELLED

    @pytest.mark.integration
    def test_cancel_completed_job_returns_409(self):
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.FEDERATED_IMPORT,
            status=JobStatus.COMPLETED,
            resource_id=str(_uuid.uuid4()),
            details_json={},
        )
        url = reverse("federated-import-cancel", kwargs={"job_id": str(job.id)})
        response = self.client.post(url)
        assert response.status_code == 409
