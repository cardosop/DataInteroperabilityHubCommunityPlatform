"""
Integration tests for Data-First Asset Creation flow.

Per tasks 29.68.5.2. Full flow: POST /api/v1/assets/data-first/ → workflow →
asset, dataset, contract created. Uses real storage when available.
No mocks/stubs in critical paths.
"""

import hashlib
import json
import uuid

import pytest
from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.integration]
User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()


class TestDataFirstAssetFlowIntegration(TestCase):
    """Integration tests for data-first asset creation API."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Data First Flow Tenant {uid}",
            slug=f"data-first-flow-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
            compliance_fail_closed_enabled=False,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"data-first-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)

        csv_content = (
            b"id,name,email,age\n1,John Doe,john@example.com,30\n2,Jane Smith,jane@example.com,25\n"
        )
        self.file_obj = File.objects.create(
            tenant=self.tenant,
            name="integration_test_data.csv",
            content_type="text/csv",
            size=len(csv_content),
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        try:
            storage = S3StorageClient()
            storage_path = storage.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file_obj.id),
                file_content=ContentFile(csv_content, name="integration_test_data.csv"),
            )
            self.file_obj.storage_path = storage_path
            self.file_obj.save(update_fields=["storage_path"])
        except Exception:
            self.file_obj.storage_path = (
                f"{self.tenant.id!s}/{self.file_obj.id!s}/integration_test_data.csv"
            )
            self.file_obj.save(update_fields=["storage_path"])

    def test_data_first_flow_creates_asset_dataset_contract(self):
        """POST data-first with valid file creates asset, dataset, contract."""
        self.client.force_authenticate(user=self.user)
        key = f"integration-asset-{uuid.uuid4().hex[:8]}"
        body = {
            "file_id": str(self.file_obj.id),
            "key": key,
            "name": "Integration Test Asset",
            "description": "Created via integration test",
        }
        # Use canonical JSON bytes so the idempotency-key SHA matches
        # what the server computes from request.body (see
        # IdempotencyService.canonical_body_bytes and
        # hub/apps/testing/idempotency_helpers.py).
        canonical_body = json.dumps(
            body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        idem_key = f"{self.tenant.id}:{hashlib.sha256(canonical_body).hexdigest()}"
        response = self.client.post(
            "/api/v1/assets/data-first/",
            canonical_body,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=idem_key,
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            f"Expected 201, got {response.status_code}: {response.data}",
        )
        data = response.data
        asset_id = data["asset_id"]
        dataset_id = data["dataset_id"]
        contract_id = data["contract_id"]

        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.tenant_id, self.tenant.id)
        self.assertEqual(asset.key, key)
        self.assertEqual(asset.created_by_id, self.user.id)

        dataset = Dataset.objects.get(id=dataset_id)
        self.assertEqual(dataset.asset_id, asset.id)
        self.assertEqual(dataset.file_id, self.file_obj.id)
        self.assertEqual(dataset.tenant_id, self.tenant.id)

        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.asset_id, asset.id)
        self.assertEqual(contract.tenant_id, self.tenant.id)
