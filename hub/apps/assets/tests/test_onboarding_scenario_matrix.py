"""
Phase 26-OB: Onboarding scenario matrix tests.

Combinatorial coverage of contract type x DQ x compliance -> activation result.
Uses the real Django API stack with APIClient.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.contracts.models import (
    Contract,
)
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class OnboardingScenarioMatrixTest(TestCase):
    """Combinatorial coverage of contract type x DQ x compliance -> activation."""

    def setUp(self):
        self.client = APIClient()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Matrix Tenant {uid}",
            slug=f"matrix-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"matrix-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.client.force_authenticate(user=self.user)

    # -- helpers -------------------------------------------------------

    def _setup_full_asset(
        self,
        contract_type="ODCS",
        contract_format="JSON",
        dq_status="PASS",
        compliance_status="PASS",
        contract_validation="VALID",
        contract_normalization="NORMALIZED_OK",
        contract_status="ACTIVE",
        with_dataset=True,
        file_content_type="text/csv",
        file_name="data.csv",
    ):
        """Create asset + contract + optional dataset with given statuses."""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"matrix-{uuid.uuid4().hex[:6]}",
            name="Matrix Asset",
            dq_status=dq_status,
            compliance_status=compliance_status,
            created_by=self.user,
        )

        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=contract_status,
            validation_status=contract_validation,
            normalization_status=contract_normalization,
            original_spec_type=contract_type,
            original_format=contract_format,
            original_raw='{"id":"test"}',
            created_by=self.user,
        )

        if with_dataset:
            file_obj = File.objects.create(
                tenant=self.tenant,
                name=file_name,
                content_type=file_content_type,
                size=1024,
                storage_path=f"test/{uuid.uuid4().hex}.dat",
                status=FileStatus.ACTIVE,
                created_by=self.user,
            )
            Dataset.objects.create(
                tenant=self.tenant,
                asset=asset,
                file=file_obj,
                format="CSV",
                created_by=self.user,
            )

        return asset

    def _activate(self, asset):
        return self.client.post(
            f"/api/v1/assets/{asset.id}/activate/",
            {"version": asset.version},
            format="json",
        )

    # == Contract type tests ==========================================

    def test_odcs_json_valid_activates(self):
        asset = self._setup_full_asset(contract_type="ODCS", contract_format="JSON")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_odcs_yaml_valid_activates(self):
        asset = self._setup_full_asset(contract_type="ODCS", contract_format="YAML")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_odps_json_valid_activates(self):
        asset = self._setup_full_asset(contract_type="ODPS", contract_format="JSON")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_contract_warning_only_activates(self):
        asset = self._setup_full_asset(contract_validation="WARNING_ONLY")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_contract_skipped_validation_blocks(self):
        asset = self._setup_full_asset(contract_validation="SKIPPED")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_contract_normalization_failed_blocks(self):
        asset = self._setup_full_asset(contract_normalization="NORMALIZATION_FAILED")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    # == Data format tests ============================================

    def test_csv_file_onboarding(self):
        asset = self._setup_full_asset(file_content_type="text/csv", file_name="data.csv")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_json_file_onboarding(self):
        asset = self._setup_full_asset(file_content_type="application/json", file_name="data.json")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_parquet_file_onboarding(self):
        asset = self._setup_full_asset(
            file_content_type="application/octet-stream", file_name="data.parquet"
        )
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # == DQ status tests ==============================================

    def test_dq_pass_activates(self):
        asset = self._setup_full_asset(dq_status="PASS")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dq_warn_activates(self):
        asset = self._setup_full_asset(dq_status="WARN")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dq_fail_blocks(self):
        asset = self._setup_full_asset(dq_status="FAIL")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_dq_unknown_blocks(self):
        asset = self._setup_full_asset(dq_status="UNKNOWN")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    # == Compliance status tests ======================================

    def test_compliance_pass_activates(self):
        asset = self._setup_full_asset(compliance_status="PASS")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_compliance_warn_activates(self):
        asset = self._setup_full_asset(compliance_status="WARN")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_compliance_fail_blocks(self):
        asset = self._setup_full_asset(compliance_status="FAIL")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    def test_compliance_unknown_blocks(self):
        asset = self._setup_full_asset(compliance_status="UNKNOWN")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["code"], "ASSET_ACTIVATION_BLOCKED")

    # == Combined tests ===============================================

    def test_all_pass_activates(self):
        asset = self._setup_full_asset(dq_status="PASS", compliance_status="PASS")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_dq_pass_compliance_fail_blocks(self):
        asset = self._setup_full_asset(dq_status="PASS", compliance_status="FAIL")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dq_fail_compliance_pass_blocks(self):
        asset = self._setup_full_asset(dq_status="FAIL", compliance_status="PASS")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_both_warn_activates(self):
        asset = self._setup_full_asset(dq_status="WARN", compliance_status="WARN")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_no_dataset_contract_only_activates(self):
        """Contract-only asset (no dataset) does not need DQ or compliance."""
        asset = self._setup_full_asset(
            with_dataset=False,
            dq_status="UNKNOWN",
            compliance_status="UNKNOWN",
        )
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_contract_draft_blocks(self):
        asset = self._setup_full_asset(contract_status="DRAFT")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_contract_invalid_blocks(self):
        asset = self._setup_full_asset(contract_validation="INVALID")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_normalization_with_warnings_activates(self):
        asset = self._setup_full_asset(contract_normalization="NORMALIZED_WITH_WARNINGS")
        resp = self._activate(asset)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
