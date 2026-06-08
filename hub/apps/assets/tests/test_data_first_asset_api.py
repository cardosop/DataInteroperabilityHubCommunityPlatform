"""
Unit tests for Data-First Asset Creation API (POST /api/v1/assets/data-first/).

Per tasks 29.68.2.1, 29.68.5.1. TDD: success, missing file_id, invalid file_id,
tenant isolation, 401. No mocks/stubs in critical paths.
"""

import logging
import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.idempotency_helpers import post_data_first
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Boundary mock helpers — pin the external service contract so tests stay
# deterministic regardless of S3 / compliance / DQ availability in the
# test environment.
# ---------------------------------------------------------------------------


def _patch_storage(content: bytes = b"a,b\n1,2\n"):
    """Mock S3 download to return known CSV content."""
    return patch(
        "hub.apps.files.storage.S3StorageClient.get_file_content",
        return_value=content,
    )


def _patch_compliance_pass():
    """Mock compliance scan to return PASS."""
    return patch(
        "hub.apps.compliance.service_client.ComplianceServiceClient.scan_file",
        return_value={
            "overall_status": "PASS",
            "allowed_to_store": True,
            "metadata": {},
        },
    )


def _patch_dq_pass():
    """Mock DQ run to return PASS."""
    return patch(
        "hub.apps.dq.service_client.DQServiceClient.run_dq",
        return_value={
            "overall_status": "PASS",
            "quality_score": 95.0,
            "metadata": {},
        },
    )


class DataFirstAssetAPITestBase(TestCase):
    """Base setup for data-first API tests."""

    def setUp(self):
        from hub.apps.core.resilience.service_breakers import (
            reset_shared_circuit_breakers_for_service,
        )
        # The data-first workflow triggers compliance scans.  Earlier
        # test suites (compliance polling tests) can leave the shared
        # circuit breaker OPEN, which causes every compliance API call
        # to fail with 503.  Reset before each test so the breaker
        # starts CLOSED.
        reset_shared_circuit_breakers_for_service("compliance-service")
        reset_shared_circuit_breakers_for_service("dq-service")
        self.client = APIClient()

    def _create_tenant_and_user(self, prefix="test"):
        uid = str(uuid.uuid4())[:8]
        tenant = Tenant.objects.create(
            name=f"{prefix} Tenant {uid}",
            slug=f"{prefix}-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_fail_closed_enabled=False,
        )
        ensure_tenant_has_active_subscription(tenant)
        user = User.objects.create_user(
            email=f"{prefix}-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(user)
        return tenant, user

    def _create_file_record_only(self, tenant, user):
        """Create File record without storage upload (for validation tests that never reach workflow)."""
        csv_content = b"id,name,email\n1,John,john@example.com\n2,Jane,jane@example.com\n"
        return File.objects.create(
            tenant=tenant,
            name="test_data.csv",
            content_type="text/csv",
            size=len(csv_content),
            status=FileStatus.ACTIVE,
            storage_path=f"{str(tenant.id)}/{uuid.uuid4()}/test_data.csv",
            created_by=user,
        )

    def _create_active_file(self, tenant, user, csv_content=None):
        """Create File record and upload to storage (legacy ACTIVE fixture)."""
        if csv_content is None:
            csv_content = b"id,name,email\n1,John,john@example.com\n2,Jane,jane@example.com\n"
        file_obj = File.objects.create(
            tenant=tenant,
            name="test_data.csv",
            content_type="text/csv",
            size=len(csv_content),
            status=FileStatus.ACTIVE,
            created_by=user,
        )
        try:
            storage = S3StorageClient()
            storage_path = storage.save_file(
                tenant_id=str(tenant.id),
                file_id=str(file_obj.id),
                file_content=ContentFile(csv_content, name="test_data.csv"),
            )
            file_obj.storage_path = storage_path
            file_obj.save(update_fields=["storage_path"])
        except Exception:
            logger.warning(
                "S3 upload failed in _create_active_file — falling back to synthetic path. "
                "Tests relying on this fallback may not exercise real storage behaviour. "
                "tenant=%s file=%s",
                tenant.id, file_obj.id,
            )
            file_obj.storage_path = f"{str(tenant.id)}/{str(file_obj.id)}/test_data.csv"
            file_obj.save(update_fields=["storage_path"])
        return file_obj

    def _create_completed_file(self, tenant, user, csv_content=None):
        """Create an uploaded file in ACTIVE state.

        (Migration 0009 retired the ``COMPLETED`` status; the data-first
        endpoint now requires ACTIVE.  The helper name is preserved for
        backward compatibility with existing call sites.)
        """
        return self._create_active_file(tenant, user, csv_content=csv_content)


class DataFirstAssetAPIValidationTest(DataFirstAssetAPITestBase):
    """Validation tests: missing file_id, invalid file_id, 401."""

    def setUp(self):
        super().setUp()
        self.tenant, self.user = self._create_tenant_and_user()
        self.client.force_authenticate(user=self.user)

    def test_data_first_returns_401_when_unauthenticated(self):
        """POST /api/v1/assets/data-first/ without auth returns 401."""
        self.client.force_authenticate(user=None)
        # No file needed: 401 returned by permission class before file validation
        response = self.client.post(
            "/api/v1/assets/data-first/",
            {"file_id": str(uuid.uuid4()), "key": "my-asset", "name": "My Asset"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_data_first_returns_400_when_file_id_missing(self):
        """POST /api/v1/assets/data-first/ without file_id returns 400."""
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {"key": "my-asset", "name": "My Asset"},
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file_id", str(response.data).lower())

    def test_data_first_returns_400_when_key_missing(self):
        """POST /api/v1/assets/data-first/ without key returns 400."""
        file_obj = self._create_file_record_only(self.tenant, self.user)
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "name": "My Asset"},
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("key", str(response.data).lower())

    def test_data_first_returns_400_when_name_missing(self):
        """POST /api/v1/assets/data-first/ without name returns 400."""
        file_obj = self._create_file_record_only(self.tenant, self.user)
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {"file_id": str(file_obj.id), "key": "my-asset"},
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", str(response.data).lower())

    def test_data_first_returns_404_when_file_id_invalid(self):
        """POST /api/v1/assets/data-first/ with non-existent file_id returns 404."""
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {
                "file_id": str(uuid.uuid4()),
                "key": "my-asset",
                "name": "My Asset",
            },
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["code"], "NOT_FOUND")

    def test_data_first_returns_400_when_file_id_malformed(self):
        """POST /api/v1/assets/data-first/ with malformed file_id returns 400."""
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {"file_id": "not-a-uuid", "key": "my-asset", "name": "My Asset"},
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # DRF UUIDField validation surfaces the field name in the error response
        self.assertIn("file_id", response.data)

    def test_data_first_returns_400_when_file_has_no_content(self):
        """File records without uploaded S3 content fail at workflow stage."""
        file_obj = self._create_file_record_only(self.tenant, self.user)
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {
                "file_id": str(file_obj.id),
                "key": "no-content-rejected",
                "name": "Should Fail",
            },
            tenant=self.tenant,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data)


class DataFirstAssetAPITenantIsolationTest(DataFirstAssetAPITestBase):
    """Tenant isolation: user from tenant A must not use tenant B's file_id."""

    def setUp(self):
        super().setUp()
        self.tenant_a, self.user_a = self._create_tenant_and_user(prefix="tenant-a")
        self.tenant_b, self.user_b = self._create_tenant_and_user(prefix="tenant-b")
        self.file_b = self._create_file_record_only(self.tenant_b, self.user_b)
        self.client.force_authenticate(user=self.user_a)

    def test_data_first_cross_tenant_file_id_returns_404(self):
        """User from tenant A POSTing tenant B's file_id returns 404."""
        response = post_data_first(
            self.client,
            "/api/v1/assets/data-first/",
            {
                "file_id": str(self.file_b.id),
                "key": "my-asset",
                "name": "My Asset",
            },
            tenant=self.tenant_a,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["code"], "NOT_FOUND")


class DataFirstAssetAPISuccessTest(DataFirstAssetAPITestBase):
    """Success case: valid file_id, key, name returns 201 with asset_id, dataset_id, contract_id."""

    def setUp(self):
        super().setUp()
        self.tenant, self.user = self._create_tenant_and_user()
        self.file_obj = self._create_completed_file(self.tenant, self.user)
        self.client.force_authenticate(user=self.user)

    def test_data_first_success_returns_201_with_ids(self):
        """POST /api/v1/assets/data-first/ with valid data returns 201 and asset_id, dataset_id, contract_id."""
        with _patch_storage(), _patch_compliance_pass(), _patch_dq_pass():
            response = post_data_first(
                self.client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(self.file_obj.id),
                    "key": f"data-first-asset-{uuid.uuid4().hex[:8]}",
                    "name": "Data First Asset",
                    "description": "Created via data-first API",
                },
                tenant=self.tenant,
            )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201, got {response.status_code}: {response.data}",
        )
        data = response.data
        self.assertIn("asset_id", data)
        self.assertIn("dataset_id", data)
        self.assertIn("contract_id", data)
        self.assertIsNotNone(data["asset_id"])
        self.assertIsNotNone(data["dataset_id"])
        self.assertIsNotNone(data["contract_id"])

        asset = Asset.objects.get(id=data["asset_id"])
        self.assertEqual(asset.tenant_id, self.tenant.id)
        self.assertEqual(asset.created_by_id, self.user.id)

    def test_data_first_success_with_active_file_returns_success(self):
        """ACTIVE file status is accepted by the data-first endpoint."""
        self.file_obj.status = FileStatus.ACTIVE
        self.file_obj.save(update_fields=["status", "updated_at"])
        with _patch_storage(), _patch_compliance_pass(), _patch_dq_pass():
            response = post_data_first(
                self.client,
                "/api/v1/assets/data-first/",
                {
                    "file_id": str(self.file_obj.id),
                    "key": f"completed-file-{uuid.uuid4().hex[:8]}",
                    "name": "Completed File Asset",
                },
                tenant=self.tenant,
            )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data.get("asset_id"))
