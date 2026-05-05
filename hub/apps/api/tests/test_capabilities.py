"""
Phase 228 (REQ-LIN-006, 228.0.18) — capability flag tests.

Pins the five lineage flags + the GET /api/v1/capabilities/ endpoint
+ the test-mode / production default policy + per-flag override.
"""
from __future__ import annotations

import pytest
from django.test import override_settings
from rest_framework.test import APIClient


def test_five_lineage_flags_are_registered():
    """REQ-LIN-006 — exactly the five named flags."""
    from hub.apps.api.capabilities import LINEAGE_CAPABILITY_FLAGS

    assert set(LINEAGE_CAPABILITY_FLAGS) == {
        "lineage.cross_tenant_marketplace",
        "lineage.field_level_mapping",
        "lineage.change_notifications",
        "lineage.openlineage_export",
        "lineage.snapshots",
    }


def test_test_environment_auto_enables_all_flags():
    """REQ-LIN-006 scenario: test env returns all flags True."""
    from hub.apps.api.capabilities import get_capabilities, LINEAGE_CAPABILITY_FLAGS

    # Pytest sets PYTEST_CURRENT_TEST so _is_test_environment() returns True.
    caps = get_capabilities()
    for flag in LINEAGE_CAPABILITY_FLAGS:
        assert caps[flag] is True, (
            f"flag {flag!r} should be True in test env; got {caps[flag]!r}"
        )


def test_settings_override_wins_over_default(monkeypatch):
    """Per-flag setting override beats env default."""
    with override_settings(
        CAPABILITY_FLAGS={
            "lineage.field_level_mapping": False,
            "lineage.snapshots": False,
        },
    ):
        from hub.apps.api.capabilities import get_capabilities
        caps = get_capabilities()
        assert caps["lineage.field_level_mapping"] is False
        assert caps["lineage.snapshots"] is False
        # Other flags stay test-default (True under pytest).
        assert caps["lineage.cross_tenant_marketplace"] is True


def test_capabilities_endpoint_returns_flag_map(db):
    """REQ-LIN-006 scenario: ``GET /api/v1/capabilities/`` returns the
    flat capability map. AllowAny so the frontend can call pre-auth."""
    client = APIClient()
    resp = client.get("/api/v1/capabilities/")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    assert "capabilities" in data
    caps = data["capabilities"]
    expected = {
        "lineage.cross_tenant_marketplace",
        "lineage.field_level_mapping",
        "lineage.change_notifications",
        "lineage.openlineage_export",
        "lineage.snapshots",
    }
    assert expected.issubset(caps.keys()), (
        f"endpoint must return all five lineage flags; got {sorted(caps)}"
    )
    # Every value is a bool, EXCEPT the 250.6.D.2 discriminator
    # ``asset_creation_blocked_reason`` which is ``str | None``.
    for k, v in caps.items():
        if k == "asset_creation_blocked_reason":
            assert v is None or isinstance(v, str), (
                f"asset_creation_blocked_reason must be str|None; got {v!r}"
            )
            continue
        assert isinstance(v, bool), f"flag {k!r} non-bool: {v!r}"


def test_is_capability_enabled_unknown_flag_returns_false():
    from hub.apps.api.capabilities import is_capability_enabled
    assert is_capability_enabled("lineage.does_not_exist") is False


# ---------------------------------------------------------------------------
# Phase 250.6.D.2 — asset_creation_blocked_reason discriminator
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestAssetCreationBlockedReason:
    """Pin the three-state truth table on the capabilities response.

    The reason field discriminates the SPA's UX path:
      * ``None`` → render the normal create flow.
      * ``"ONBOARDING_INCOMPLETE"`` → render the picker's onboarding-CTA variant.
      * ``"DISABLED_BY_OPS"`` → redirect to the existing generic disabled page.

    Tests use real Tenant rows + a real authenticated request so the
    request_tenant resolver returns a tenant context (the function
    short-circuits to ``None`` for anonymous, which is its own test).
    """

    @staticmethod
    def _make_request_with_tenant(tenant):
        """Build a request whose ``request_tenant`` resolver returns this tenant.

        Avoids spinning up an authenticated APIClient — we only need
        the tenant resolver to return a value, and the cleanest way
        is to call ``get_capabilities_for_request`` with a request
        whose ``user.tenant`` is set.
        """
        from rest_framework.test import APIRequestFactory
        from hub.apps.users.models import User, UserStatus
        import uuid

        uid = uuid.uuid4().hex[:8]
        user = User.objects.create_user(
            email=f"reason-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        factory = APIRequestFactory()
        request = factory.get("/api/v1/capabilities/")
        request.user = user
        return request

    @staticmethod
    def _new_tenant(*, asset_creation_enabled, onboarding_completed_at=None):
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
        import uuid

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(
            name=f"Reason {uid}",
            slug=f"reason-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            asset_creation_enabled=asset_creation_enabled,
        )
        if onboarding_completed_at is not None:
            from django.utils import timezone

            tenant.onboarding_completed_at = (
                timezone.now() if onboarding_completed_at is True else onboarding_completed_at
            )
            tenant.save(update_fields=["onboarding_completed_at"])
        return tenant

    def test_anonymous_request_returns_none_reason(self, db):
        """No tenant context → reason is None (no block)."""
        from rest_framework.test import APIRequestFactory
        from hub.apps.api.capabilities import get_capabilities_for_request

        request = APIRequestFactory().get("/api/v1/capabilities/")
        # No user — anonymous.
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
        caps = get_capabilities_for_request(request)
        assert "asset_creation_blocked_reason" in caps
        assert caps["asset_creation_blocked_reason"] is None

    def test_enabled_tenant_returns_none_reason(self):
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(asset_creation_enabled=True)
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is True
        assert caps["asset_creation_blocked_reason"] is None

    def test_disabled_with_no_completion_timestamp_returns_onboarding_incomplete(self):
        """asset_creation_enabled=False AND completion_at IS None → ONBOARDING_INCOMPLETE."""
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(
            asset_creation_enabled=False, onboarding_completed_at=None
        )
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is False
        assert caps["asset_creation_blocked_reason"] == "ONBOARDING_INCOMPLETE"

    def test_disabled_with_completion_timestamp_returns_disabled_by_ops(self):
        """asset_creation_enabled=False AND completion_at IS NOT None → DISABLED_BY_OPS."""
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(
            asset_creation_enabled=False, onboarding_completed_at=True
        )
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is False
        assert caps["asset_creation_blocked_reason"] == "DISABLED_BY_OPS"

    def test_enabled_with_completion_timestamp_returns_none_reason(self):
        """The 'normal post-onboarding tenant' path — flag True + timestamp set."""
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(
            asset_creation_enabled=True, onboarding_completed_at=True
        )
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is True
        assert caps["asset_creation_blocked_reason"] is None
