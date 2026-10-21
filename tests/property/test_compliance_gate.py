"""
Property-based tests for the real compliance gate (281.A.2.3).

Tests that ``compliance_gate_codes_for_asset()`` correctly gates
access based on the latest ``ComplianceRun`` for an asset.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def gate_tenant():
    """Create a throwaway tenant for compliance gate tests."""
    import uuid

    from hub.apps.tenants.models import KYCStatus, Tenant

    slug = f"gate-prop-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"Gate Property Test {slug}",
        slug=slug,
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )


@pytest.fixture
def gate_asset(gate_tenant):
    """Create a minimal asset for compliance gate testing."""
    import uuid

    from hub.apps.assets.models import Asset, AssetStatus

    suffix = uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=gate_tenant,
        name=f"gate-test-asset-{suffix}",
        key=f"gate-test-asset-{suffix}",
        status=AssetStatus.DRAFT,
    )


class TestComplianceGateBasics:
    """Compliance gate returns codes based on ComplianceRun state."""

    def test_no_compliance_run_blocks(self, gate_tenant, gate_asset):
        """Without any ComplianceRun, the gate blocks with RUN_REQUIRED."""
        from hub.apps.marketplace.compliance_gate import (
            compliance_gate_codes_for_asset,
        )

        code, msg = compliance_gate_codes_for_asset(
            gate_asset,
            tenant_id=str(gate_tenant.id),
        )
        assert code == "COMPLIANCE_RUN_REQUIRED"
        assert msg is not None

    def test_succeeded_run_allows(self, gate_tenant, gate_asset):
        """A succeeded run with acceptable risk level allows."""
        from hub.apps.compliance.models import (
            ComplianceRun,
            ComplianceRunStatus,
            RiskLevel,
        )
        from hub.apps.marketplace.compliance_gate import (
            compliance_gate_codes_for_asset,
        )

        ComplianceRun.objects.create(
            tenant=gate_tenant,
            asset=gate_asset,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.LOW,
        )

        code, msg = compliance_gate_codes_for_asset(
            gate_asset,
            tenant_id=str(gate_tenant.id),
        )
        assert code is None  # allowed
        assert msg is None

    def test_succeeded_run_with_high_risk_blocks(self, gate_tenant, gate_asset):
        """A succeeded run exceeding the risk threshold blocks."""
        from hub.apps.compliance.models import (
            ComplianceRun,
            ComplianceRunStatus,
            RiskLevel,
        )
        from hub.apps.marketplace.compliance_gate import (
            compliance_gate_codes_for_asset,
        )

        ComplianceRun.objects.create(
            tenant=gate_tenant,
            asset=gate_asset,
            status=ComplianceRunStatus.SUCCEEDED,
            risk_level=RiskLevel.CRITICAL,
        )

        code, _msg = compliance_gate_codes_for_asset(
            gate_asset,
            tenant_id=str(gate_tenant.id),
        )
        # CRITICAL exceeds default HIGH threshold → blocked
        assert code is not None
        assert "THRESHOLD_EXCEEDED" in (code or "")

    def test_failed_run_does_not_satisfy_gate(self, gate_tenant, gate_asset):
        """Only SUCCEEDED runs satisfy the gate; FAILED runs do not."""
        from hub.apps.compliance.models import (
            ComplianceRun,
            ComplianceRunStatus,
            RiskLevel,
        )
        from hub.apps.marketplace.compliance_gate import (
            compliance_gate_codes_for_asset,
        )

        ComplianceRun.objects.create(
            tenant=gate_tenant,
            asset=gate_asset,
            status=ComplianceRunStatus.FAILED,
            risk_level=RiskLevel.LOW,
        )

        code, _msg = compliance_gate_codes_for_asset(
            gate_asset,
            tenant_id=str(gate_tenant.id),
        )
        # FAILED run doesn't count → gate requires a SUCCEEDED run
        assert code == "COMPLIANCE_RUN_REQUIRED"
