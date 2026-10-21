"""
Property-based tests for the real ABAC engine (281.A.2.3).

Tests that ``ABACEngine.evaluate_access()`` produces deterministic,
consistent results for identical inputs using Hypothesis to generate
randomized access patterns against real database-backed policies.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def abac_tenant():
    """Create (or reuse) a throwaway tenant for ABAC policy records."""
    import uuid

    from hub.apps.tenants.models import KYCStatus, Tenant

    slug = f"abac-prop-{uuid.uuid4().hex[:8]}"
    return Tenant.objects.create(
        name=f"ABAC Property Test {slug}",
        slug=slug,
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )


def _make_abac_args(**overrides):
    """Build a complete evaluate_access kwargs dict with defaults."""
    defaults = {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "tenant_id": "00000000-0000-0000-0000-000000000099",
        "resource_type": "ASSET",
        "resource_id": "00000000-0000-0000-0000-000000000002",
        "access_type": "READ",
        "user_attributes": {"user_roles": ["VIEWER"]},
        "environment_attributes": {},
    }
    defaults.update(overrides)
    return defaults


class TestABACDeterminism:
    """ABAC engine must produce consistent, deterministic results."""

    @given(
        resource_type=st.sampled_from(["ASSET", "DATASET", "FILE"]),
        access_type=st.sampled_from(["READ", "WRITE", "DOWNLOAD"]),
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_abac_is_deterministic(
        self,
        abac_tenant,
        resource_type,
        access_type,
    ):
        """The same input always produces the same ABAC decision."""
        from hub.apps.governance.abac import ABACEngine

        args1 = _make_abac_args(
            tenant_id=str(abac_tenant.id),
            resource_type=resource_type,
            access_type=access_type,
        )
        args2 = dict(args1)

        decision1 = ABACEngine.evaluate_access(**args1)
        decision2 = ABACEngine.evaluate_access(**args2)

        assert decision1.allowed == decision2.allowed

    @given(
        roles=st.lists(
            st.sampled_from(["TENANT_ADMIN", "DATA_ENGINEER", "VIEWER"]),
            min_size=1,
            max_size=3,
            unique=True,
        ),
    )
    @settings(
        max_examples=10,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    def test_abac_result_is_boolean(self, abac_tenant, roles):
        """ABAC evaluation always returns a boolean allowed flag."""
        from hub.apps.governance.abac import ABACEngine

        result = ABACEngine.evaluate_access(
            **_make_abac_args(
                tenant_id=str(abac_tenant.id),
                user_attributes={"user_roles": roles},
            )
        )
        assert isinstance(result.allowed, bool)


class TestABACExplicitPolicy:
    """ABAC engine respects explicit ALLOW policies."""

    def test_explicit_allow_policy_grants_access(self, abac_tenant):
        """An ALLOW policy matching user role permits access."""
        from hub.apps.governance.abac import ABACEngine
        from hub.apps.governance.models import AccessPolicy

        AccessPolicy.objects.create(
            tenant=abac_tenant,
            name="test-allow-viewer-read",
            conditions={
                "user": {"user_roles": ["VIEWER"]},
            },
            effect="ALLOW",
        )

        result = ABACEngine.evaluate_access(
            **_make_abac_args(
                tenant_id=str(abac_tenant.id),
                user_attributes={"user_roles": ["VIEWER"]},
            )
        )
        assert result.allowed

    def test_deny_policy_blocks_access(self, abac_tenant):
        """A higher-priority DENY policy overrides a lower-priority ALLOW."""
        from hub.apps.governance.abac import ABACEngine
        from hub.apps.governance.models import AccessPolicy

        # ALLOW with priority 10
        AccessPolicy.objects.create(
            tenant=abac_tenant,
            name="test-allow-viewer",
            conditions={"user": {"user_roles": ["VIEWER"]}},
            effect="ALLOW",
            priority=10,
        )
        # DENY with priority 1 (higher priority — evaluated first)
        AccessPolicy.objects.create(
            tenant=abac_tenant,
            name="test-deny-viewer",
            conditions={"user": {"user_roles": ["VIEWER"]}},
            effect="DENY",
            priority=1,
        )

        result = ABACEngine.evaluate_access(
            **_make_abac_args(
                tenant_id=str(abac_tenant.id),
                user_attributes={"user_roles": ["VIEWER"]},
            )
        )
        # DENY with priority 1 is evaluated before ALLOW with priority 10
        assert not result.allowed
