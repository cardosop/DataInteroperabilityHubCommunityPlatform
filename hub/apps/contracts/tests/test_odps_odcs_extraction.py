"""
Phase 26-OB: ODPS-ODCS linking validation tests.

Tests the validate_linking function including the asset consistency
check that prevents cross-asset linking of ODPS and ODCS contracts.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.contracts.linking_validation import (
    LinkingValidationError,
    validate_contract_exists,
    validate_linking,
)
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSODCSExtractionTest(TestCase):
    """ODPS-ODCS linking validation including asset consistency."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Link Tenant {uid}",
            slug=f"link-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"link-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    # -- helpers -------------------------------------------------------

    def _make_hub_json(self, odcs_link=None, odps_link=None):
        """Build minimal hub_contract_json with extensions."""
        extensions = {"x_odps": {}}
        if odcs_link:
            extensions["x_odps"]["odcs_link"] = str(odcs_link)
        if odps_link:
            extensions["x_odps"]["odps_link"] = str(odps_link)
        return {"extensions": extensions}

    def _create_contract(self, spec_type, asset=None, hub_json=None, **overrides):
        defaults = dict(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=spec_type,
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"test"}',
            hub_contract_json=hub_json or self._make_hub_json(),
            created_by=self.user,
        )
        defaults.update(overrides)
        return Contract.objects.create(**defaults)

    def _create_asset(self, **overrides):
        defaults = dict(
            tenant=self.tenant,
            key=f"asset-{uuid.uuid4().hex[:6]}",
            name="Link Asset",
            created_by=self.user,
        )
        defaults.update(overrides)
        return Asset.objects.create(**defaults)

    # -- tests ---------------------------------------------------------

    def test_link_same_asset_succeeds(self):
        """Both contracts linked to the same asset passes validation."""
        asset = self._create_asset()
        # distinct version per (tenant, asset) — see unique_contract_version_per_asset
        odps = self._create_contract(OriginalSpecType.ODPS, asset=asset, version=1)
        odcs = self._create_contract(OriginalSpecType.ODCS, asset=asset, version=2)
        # Should not raise
        result = validate_linking(str(odps.id), str(odcs.id), tenant_id=str(self.tenant.id))
        self.assertEqual(len(result), 2)

    def test_link_different_assets_rejected(self):
        """ODPS on asset A, ODCS on asset B raises ASSET_MISMATCH."""
        asset_a = self._create_asset()
        asset_b = self._create_asset()
        odps = self._create_contract(OriginalSpecType.ODPS, asset=asset_a)
        odcs = self._create_contract(OriginalSpecType.ODCS, asset=asset_b)
        with self.assertRaises(LinkingValidationError) as ctx:
            validate_linking(str(odps.id), str(odcs.id), tenant_id=str(self.tenant.id))
        self.assertEqual(ctx.exception.error_code, "ASSET_MISMATCH")

    def test_link_both_unlinked_succeeds(self):
        """Both contracts with no asset pass validation."""
        odps = self._create_contract(OriginalSpecType.ODPS, asset=None)
        odcs = self._create_contract(OriginalSpecType.ODCS, asset=None)
        result = validate_linking(str(odps.id), str(odcs.id), tenant_id=str(self.tenant.id))
        self.assertEqual(len(result), 2)

    def test_link_one_with_asset_one_without_succeeds(self):
        """ODPS has asset, ODCS has no asset: succeeds (only checked when both have assets)."""
        asset = self._create_asset()
        odps = self._create_contract(OriginalSpecType.ODPS, asset=asset)
        odcs = self._create_contract(OriginalSpecType.ODCS, asset=None)
        result = validate_linking(str(odps.id), str(odcs.id), tenant_id=str(self.tenant.id))
        self.assertEqual(len(result), 2)

    def test_tenant_id_required(self):
        """validate_contract_exists with tenant_id=None raises TENANT_ID_REQUIRED."""
        odps = self._create_contract(OriginalSpecType.ODPS)
        with self.assertRaises(LinkingValidationError) as ctx:
            validate_contract_exists(str(odps.id), tenant_id=None)
        self.assertEqual(ctx.exception.error_code, "TENANT_ID_REQUIRED")

    def test_cross_tenant_contract_rejected(self):
        """Contract from tenant A validated with tenant B raises TENANT_MISMATCH."""
        other_uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {other_uid}",
            slug=f"other-tenant-{other_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        odps = self._create_contract(OriginalSpecType.ODPS)
        with self.assertRaises(LinkingValidationError) as ctx:
            validate_contract_exists(str(odps.id), tenant_id=str(other_tenant.id))
        self.assertEqual(ctx.exception.error_code, "TENANT_MISMATCH")
