"""
Phase 26-OB: Asset status state-machine transition tests.

Validates VALID_TRANSITIONS = {
    DRAFT: [ACTIVE],
    ACTIVE: [PUBLIC, RETIRED],
    PUBLIC: [RETIRED],
    RETIRED: [],
}
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus, DQStatus
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

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class AssetStatusTransitionTest(TestCase):
    """Test the asset status state machine via model full_clean()."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Trans Tenant {uid}",
            slug=f"trans-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"trans-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    # -- helpers ----------------------------------------------------------

    def _make_asset(self, status=AssetStatus.DRAFT, **kwargs):
        uid = uuid.uuid4().hex[:6]
        return Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name=f"Asset {uid}",
            status=status,
            created_by=self.user,
            **kwargs,
        )

    def _make_valid_contract(self, asset):
        return Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"t","name":"T","schema":{"fields":[{"name":"id","type":"string"}]}}',
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

    def _force_status(self, asset, target_status):
        """Set status bypassing clean() for test setup."""
        Asset.objects.filter(pk=asset.pk).update(status=target_status)
        asset.refresh_from_db()

    # -- allowed transitions ----------------------------------------------

    def test_draft_to_active_allowed(self):
        """DRAFT -> ACTIVE succeeds when all activation requirements are met."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        asset.status = AssetStatus.ACTIVE
        asset.full_clean()  # should not raise

    def test_active_to_retired_allowed(self):
        """ACTIVE -> RETIRED succeeds."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.ACTIVE)
        asset.status = AssetStatus.RETIRED
        asset.full_clean()  # should not raise

    def test_active_to_public_allowed(self):
        """ACTIVE -> PUBLIC succeeds."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.ACTIVE)
        asset.status = AssetStatus.PUBLIC
        asset.full_clean()  # should not raise

    def test_public_to_retired_allowed(self):
        """PUBLIC -> RETIRED succeeds."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.PUBLIC)
        asset.status = AssetStatus.RETIRED
        asset.full_clean()  # should not raise

    # -- forbidden transitions --------------------------------------------

    def test_active_to_draft_forbidden(self):
        """ACTIVE -> DRAFT raises ValidationError."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.ACTIVE)
        asset.status = AssetStatus.DRAFT
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_retired_to_active_forbidden(self):
        """RETIRED -> ACTIVE raises ValidationError."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.RETIRED)
        asset.status = AssetStatus.ACTIVE
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_retired_to_draft_forbidden(self):
        """RETIRED -> DRAFT raises ValidationError."""
        asset = self._make_asset()
        self._force_status(asset, AssetStatus.RETIRED)
        asset.status = AssetStatus.DRAFT
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_draft_to_retired_forbidden(self):
        """DRAFT -> RETIRED (must go through ACTIVE first) raises ValidationError."""
        asset = self._make_asset()
        asset.status = AssetStatus.RETIRED
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_draft_to_public_forbidden(self):
        """DRAFT -> PUBLIC raises ValidationError."""
        asset = self._make_asset()
        asset.status = AssetStatus.PUBLIC
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_public_to_active_forbidden(self):
        """PUBLIC -> ACTIVE raises ValidationError."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS, compliance_status=ComplianceStatus.PASS
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.PUBLIC)
        asset.status = AssetStatus.ACTIVE
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    def test_public_to_draft_forbidden(self):
        """PUBLIC -> DRAFT raises ValidationError."""
        asset = self._make_asset(
            dq_status=DQStatus.PASS, compliance_status=ComplianceStatus.PASS
        )
        self._make_valid_contract(asset)
        self._force_status(asset, AssetStatus.PUBLIC)
        asset.status = AssetStatus.DRAFT
        with self.assertRaises(ValidationError) as ctx:
            asset.full_clean()
        self.assertIn("Invalid status transition", str(ctx.exception))

    # -- edge case: new asset ---------------------------------------------

    def test_new_asset_no_transition_validation(self):
        """New asset (no pk yet) with status DRAFT passes full_clean()."""
        asset = Asset(
            tenant=self.tenant,
            key=f"new-{uuid.uuid4().hex[:6]}",
            name="Brand New Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        asset.full_clean()  # should not raise
