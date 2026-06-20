"""
Phase 274.2 — AssetActivationRule tests.

Covers the three-state taxonomy from validate_activation():
- COMPLIANCE_SCAN_PENDING (no SUCCEEDED/FAILED run)
- COMPLIANCE_SCAN_FAILED
- COMPLIANCE_NOT_ALLOWED_TO_STORE
- COMPLIANCE_THRESHOLD_EXCEEDED (risk above threshold)
- No blockers (allowed)
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.business_rules import AssetActivationRule
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, RiskLevel
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _mk_tenant(**kwargs):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"AAR-{uid}",
        slug=f"aar-{uid}",
        status="ACTIVE",
        kyc_status="VERIFIED",
    )
    from hub.apps.tenants.models import TenantConfig

    threshold = kwargs.get("threshold", RiskLevel.MEDIUM.value)
    TenantConfig.objects.update_or_create(
        tenant=tenant,
        defaults={"compliance_risk_threshold": threshold},
    )
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"aar-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_asset(tenant, created_by):
    return Asset.objects.create(
        tenant=tenant,
        key=f"aar-{uuid.uuid4().hex[:8]}",
        name="Test Asset",
        status=AssetStatus.DRAFT,
        created_by=created_by,
    )


class TestAssetActivationRule(TestCase):
    """Phase 274.2 — compliance-aware activation rule."""

    def setUp(self):
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.asset = _mk_asset(self.tenant, self.user)

    def test_pending_when_no_compliance_run(self):
        result = AssetActivationRule.validate_activation(self.asset)
        assert result["can_activate"] is False
        assert result["blocker_code"] == "COMPLIANCE_SCAN_PENDING"
        assert result["details"]["retry_after_seconds"] == 30

    def test_failed_when_compliance_run_failed(self):
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="FAILED",
            allowed_to_store=None,
            risk_level=RiskLevel.UNKNOWN.value,
        )
        result = AssetActivationRule.validate_activation(self.asset)
        assert result["can_activate"] is False
        assert result["blocker_code"] == "COMPLIANCE_SCAN_FAILED"

    def test_blocked_when_allowed_to_store_false(self):
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="SUCCEEDED",
            allowed_to_store=False,
            risk_level=RiskLevel.LOW.value,
        )
        result = AssetActivationRule.validate_activation(self.asset)
        assert result["can_activate"] is False
        assert result["blocker_code"] == "COMPLIANCE_NOT_ALLOWED_TO_STORE"

    def test_blocked_when_risk_exceeds_threshold(self):
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="SUCCEEDED",
            allowed_to_store=True,
            risk_level=RiskLevel.HIGH.value,  # exceeds MEDIUM threshold
        )
        result = AssetActivationRule.validate_activation(self.asset)
        assert result["can_activate"] is False
        assert result["blocker_code"] == "COMPLIANCE_THRESHOLD_EXCEEDED"

    def test_allows_when_risk_below_threshold(self):
        ComplianceRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status="SUCCEEDED",
            allowed_to_store=True,
            risk_level=RiskLevel.LOW.value,
        )
        result = AssetActivationRule.validate_activation(self.asset)
        assert result["can_activate"] is True
        assert result["blocker_code"] is None
