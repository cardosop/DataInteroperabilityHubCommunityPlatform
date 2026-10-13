"""
Phase 228 (REQ-LIN-006, 228.0.18) — capability flag tests.

Pins the five lineage flags + the GET /api/v1/capabilities/ endpoint
+ the test-mode / production default policy + per-flag override.
"""

from __future__ import annotations

from pathlib import Path

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
    """REQ-LIN-006 scenario: test env returns all flags True (contract for E2E tests).

    Pins the invariant that ALL lineage capability flags are True and bool
    type in test mode.  Integration and E2E tests that depend on every
    feature being enabled rely on this contract.
    """
    from hub.apps.api.capabilities import LINEAGE_CAPABILITY_FLAGS, get_capabilities

    caps = get_capabilities()
    lineage_caps = {k: v for k, v in caps.items() if k.startswith("lineage.")}
    assert len(lineage_caps) == len(LINEAGE_CAPABILITY_FLAGS), (
        "Number of lineage capability flags in response does not match "
        "LINEAGE_CAPABILITY_FLAGS.  A flag may be missing from get_capabilities() output."
    )
    for flag in LINEAGE_CAPABILITY_FLAGS:
        assert caps[flag] is True, f"flag {flag!r} should be True in test env; got {caps[flag]!r}"
        assert isinstance(caps[flag], bool), f"flag {flag!r} must be bool, got {type(caps[flag])!r}"


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
        import uuid

        from rest_framework.test import APIRequestFactory

        from hub.apps.users.models import User, UserStatus

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
        import uuid

        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

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

        tenant = self._new_tenant(asset_creation_enabled=False, onboarding_completed_at=None)
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is False
        assert caps["asset_creation_blocked_reason"] == "ONBOARDING_INCOMPLETE"

    def test_disabled_with_completion_timestamp_returns_disabled_by_ops(self):
        """asset_creation_enabled=False AND completion_at IS NOT None → DISABLED_BY_OPS."""
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(asset_creation_enabled=False, onboarding_completed_at=True)
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is False
        assert caps["asset_creation_blocked_reason"] == "DISABLED_BY_OPS"

    def test_enabled_with_completion_timestamp_returns_none_reason(self):
        """The 'normal post-onboarding tenant' path — flag True + timestamp set."""
        from hub.apps.api.capabilities import get_capabilities_for_request

        tenant = self._new_tenant(asset_creation_enabled=True, onboarding_completed_at=True)
        request = self._make_request_with_tenant(tenant)
        caps = get_capabilities_for_request(request)
        assert caps["asset_creation"] is True
        assert caps["asset_creation_blocked_reason"] is None


# ---------------------------------------------------------------------------
# 313.H.4 review — per-tenant compliance capability flags
# ---------------------------------------------------------------------------

COMPLIANCE_CAPABILITY_KEYS = (
    "compliance_consent",
    "compliance_dsar",
    "compliance_breach",
    "compliance_ropa",
    "compliance_dpia",
    "compliance_processor_agreements",
    "compliance_retention_enforcer",
)


def test_capabilities_endpoint_returns_per_tenant_compliance_flags(db):
    """The SPA route gates (dpia / breach / processor / retention /
    consent / ropa / dsar) read these keys from GET /capabilities/.
    A tenant with a flag enabled MUST see it on the wire — an absent
    key silently redirects the surface to /unavailable for everyone."""
    import uuid

    from django.contrib.auth import get_user_model

    from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Compliance {uid}",
        slug=f"compliance-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        compliance_consent_enabled=True,
        compliance_breach_enabled=True,
        compliance_dpia_enabled=True,
        # processor agreements left at the model default (False)
    )
    User = get_user_model()
    user = User.objects.create_user(
        email=f"comp-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/capabilities/")
    assert resp.status_code == 200, resp.content
    caps = resp.json()["capabilities"]

    for key in COMPLIANCE_CAPABILITY_KEYS:
        assert key in caps, f"wire missing compliance capability {key!r}"
        assert isinstance(caps[key], bool), f"{key!r} non-bool: {caps[key]!r}"

    assert caps["compliance_consent"] is True
    assert caps["compliance_breach"] is True
    assert caps["compliance_dpia"] is True
    assert caps["compliance_processor_agreements"] is False
    # Unset fields default False (explicit opt-in, per tenant flag docs).
    assert caps["compliance_dsar"] is False
    assert caps["compliance_ropa"] is False
    assert caps["compliance_retention_enforcer"] is False


def test_anonymous_compliance_flags_default_false(db):
    """Anonymous / unresolvable-tenant requests see the opt-in defaults."""
    resp = APIClient().get("/api/v1/capabilities/")
    assert resp.status_code == 200, resp.content
    caps = resp.json()["capabilities"]
    for key in COMPLIANCE_CAPABILITY_KEYS:
        assert caps.get(key) is False, f"anonymous {key!r} must default False"


# ---------------------------------------------------------------------------
# Phase 1.4 — runtime wire contract (frontend-consumed keys, exact set)
#
# The SPA's ``RUNTIME_CAPABILITY_KEYS`` + ``refreshRuntimeSnapshot`` coercion
# (frontend/src/features/capabilities/services/capabilitiesService.ts) reads
# these keys from ``GET /api/v1/capabilities/``. Any drift in EITHER direction
# silently redirects a surface to /unavailable:
#   * backend stops emitting a key the SPA reads   → the SPA's coercion
#     narrows it to ``false`` and every gate closes;
#   * backend emits a key the SPA does not read    → the registry's
#     enumeration drifts from the wire (dead registry entries grow).
# ---------------------------------------------------------------------------

# Mirrors RUNTIME_CAPABILITY_KEYS — deliberately enumerated HERE (not
# imported) so a frontend rename fails the suite instead of silently
# following it: the test asserts the wire matches the enumerated contract.
FRONTEND_RUNTIME_CAPABILITY_KEYS: frozenset[str] = frozenset(
    {
        # 7 compliance route gates (313.H.4)
        "compliance_consent",
        "compliance_dsar",
        "compliance_breach",
        "compliance_ropa",
        "compliance_dpia",
        "compliance_processor_agreements",
        "compliance_retention_enforcer",
        # DQ kill switch + advanced gate (240.4.B)
        "data_quality",
        "data_quality_advanced",
        # datasets/files/transformation (285.13)
        "datasets",
        "files",
        "transformation_pipelines",
        # asset-creation kill switch + discriminator (250.6.A/D)
        "asset_creation",
        "asset_creation_blocked_reason",
        # databricks control plane (add-databricks-control-plane P0) —
        # runtime-sourced from databricks_control_plane_enabled + the P0
        # kill switch; the SPA's /databricks CapabilityRoute gates on it.
        "databricks",
        # UX v2 staged rollout (278.R.6, close-test-coverage-gaps 3.2) —
        # runtime-sourced from Tenant.ux_v2_enabled (default True for
        # new tenants); the SPA's ProductTourGate reads it.
        "ux_v2",
    }
)

# The ONLY non-bool on the wire: the asset-creation discriminator.
_NON_BOOL_KEYS = frozenset({"asset_creation_blocked_reason"})

# Cross-check source: the SPA's actual RUNTIME_CAPABILITY_KEYS array, parsed
# from the frontend source so this suite fails when the SPA declares a
# runtime-consumed key the backend never emits (the plan_compliance_pro_pack
# class). Simple extraction is deliberate — the array is a flat string list.
_FRONTEND_SERVICE = (
    Path(__file__).resolve().parents[4]
    / "frontend"
    / "src"
    / "features"
    / "capabilities"
    / "services"
    / "capabilitiesService.ts"
)


def _frontend_runtime_keys_from_source() -> frozenset[str]:
    import re

    source = _FRONTEND_SERVICE.read_text()
    match = re.search(
        r"export const RUNTIME_CAPABILITY_KEYS: readonly string\[\] = \[(.*?)\];",
        source,
        re.DOTALL,
    )
    assert match, f"RUNTIME_CAPABILITY_KEYS not found in {_FRONTEND_SERVICE}"
    return frozenset(re.findall(r"['\"]([a-z_0-9.]+)['\"]", match.group(1)))


def test_anonymous_wire_contract_is_exact_and_pinned():
    """Anonymous GET /capabilities/ must emit EXACTLY the SPA-read keys
    (+ the lineage flags, the endpoint's other documented surface) with
    the pinned anonymous defaults.

    ``plan_compliance_pro_pack`` is deliberately ABSENT: its backend
    source is the subscription plan on ``/me`` (hub/apps/tenants/views.py),
    never the capabilities endpoint — the frontend registry entry for it
    was dead and has been removed.
    """
    from hub.apps.api.capabilities import LINEAGE_CAPABILITY_FLAGS

    resp = APIClient().get("/api/v1/capabilities/")
    assert resp.status_code == 200, resp.content
    caps = resp.json()["capabilities"]

    expected = set(LINEAGE_CAPABILITY_FLAGS) | set(FRONTEND_RUNTIME_CAPABILITY_KEYS)
    assert set(caps) == expected, (
        f"wire drift: got {sorted(set(caps) ^ expected)} "
        f"(missing={sorted(expected - set(caps))}, extra={sorted(set(caps) - expected)})"
    )
    assert "plan_compliance_pro_pack" not in caps, (
        "plan_compliance_pro_pack has no capabilities-endpoint source; it belongs "
        "to /me (subscription plan). Emitting it here re-wires the SPA to a "
        "contract its own registry no longer declares."
    )
    # Cross-check: every key the SPA declares runtime-consumed IS on the wire.
    # (The absence assertion above is redundant with the exact-set check
    # unless the SPA keeps declaring it — this cross-check is the pin that
    # fails if plan_compliance_pro_pack stays in RUNTIME_CAPABILITY_KEYS.)
    frontend_keys = _frontend_runtime_keys_from_source()
    missing = frontend_keys - set(caps)
    assert not missing, (
        f"SPA declares runtime capability keys the wire never emits: {sorted(missing)}"
    )

    # Pinned anonymous defaults — the SPA's pre-auth render depends on them.
    assert caps["data_quality"] is False
    assert caps["data_quality_advanced"] is False
    assert caps["datasets"] is True
    assert caps["files"] is True
    assert caps["transformation_pipelines"] is False
    assert caps["asset_creation"] is True
    assert caps["asset_creation_blocked_reason"] is None
    assert caps["ux_v2"] is False, "anonymous ux_v2 must default False"
    for key in COMPLIANCE_CAPABILITY_KEYS:
        assert caps[key] is False, f"anonymous {key!r} must default False"

    # Every key is a bool, except the documented discriminator.
    for key, value in caps.items():
        if key in _NON_BOOL_KEYS:
            assert value is None or isinstance(value, str), f"{key!r} non-bool: {value!r}"
        else:
            assert isinstance(value, bool), f"{key!r} non-bool: {value!r}"


@pytest.mark.django_db(transaction=True)
def test_tenant_wire_contract_flags_follow_the_tenant():
    """A tenant-context request sees the SAME exact key set, with every
    tenant-controlled value mirroring the tenant row.

    The tenant context is injected via ``request.user`` on a factory request
    (the pattern TestAssetCreationBlockedReason proves) — NOT via an
    authenticated APIClient. ``get_request_tenant`` resolves the tenant from
    ``request.tenant_id``/``request.tenant``/``request.user``, and an
    APIClient request carries none of them at this call depth, so an
    APIClient-based test would silently exercise the ANONYMOUS branch and
    every tenant-value assertion would be vacuous.
    """
    import uuid

    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory

    from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Wire {uid}",
        slug=f"wire-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        asset_creation_enabled=False,
        data_quality_enabled=True,
        data_quality_advanced_enabled=True,
        datasets_enabled=False,
        files_enabled=True,
        transformation_enabled=True,
        compliance_consent_enabled=True,
        compliance_breach_enabled=True,
    )
    User = get_user_model()
    user = User.objects.create_user(
        email=f"wire-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )
    request = APIRequestFactory().get("/api/v1/capabilities/")
    request.user = user
    from hub.apps.api.capabilities import LINEAGE_CAPABILITY_FLAGS, get_capabilities_for_request

    caps = get_capabilities_for_request(request)

    expected = set(LINEAGE_CAPABILITY_FLAGS) | set(FRONTEND_RUNTIME_CAPABILITY_KEYS)
    assert set(caps) == expected, f"wire drift on tenant request: {sorted(set(caps) ^ expected)}"

    # Tenant-controlled values mirror the row — the SPA gates on these.
    assert caps["asset_creation"] is False
    assert caps["asset_creation_blocked_reason"] == "ONBOARDING_INCOMPLETE"
    assert caps["data_quality"] is True
    assert caps["data_quality_advanced"] is True
    assert caps["datasets"] is False
    assert caps["files"] is True
    assert caps["transformation_pipelines"] is True
    assert caps["compliance_consent"] is True
    assert caps["compliance_breach"] is True
    # Unset compliance flags default False (explicit opt-in).
    assert caps["compliance_dpia"] is False
    assert caps["compliance_processor_agreements"] is False
    # Unset databricks control plane defaults False (explicit opt-in —
    # the P0 kill-switch AND databricks_control_plane_enabled must open).
    assert caps["databricks"] is False
    # UX v2 is default-ON for new tenants (Tenant._default_ux_v2_enabled):
    # this tenant was created without the flag, so the capability opens.
    assert caps["ux_v2"] is True


@pytest.mark.django_db(transaction=True)
def test_ux_v2_capability_follows_the_tenant_flag():
    """``ux_v2`` mirrors ``Tenant.ux_v2_enabled`` explicitly set on the row
    (close-test-coverage-gaps 3.2 — the SPA's ProductTourGate consumes it)."""
    import uuid

    from django.contrib.auth import get_user_model
    from rest_framework.test import APIRequestFactory

    from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

    uid = uuid.uuid4().hex[:8]
    User = get_user_model()

    def _caps_for(ux_v2_enabled: bool) -> dict:
        tenant = Tenant.objects.create(
            name=f"UxV2 {uid} {ux_v2_enabled}",
            slug=f"uxv2-{uid}-{int(ux_v2_enabled)}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            ux_v2_enabled=ux_v2_enabled,
        )
        user = User.objects.create_user(
            email=f"uxv2-{uid}-{int(ux_v2_enabled)}@example.com",
            password="testpass123",
            tenant=tenant,
        )
        request = APIRequestFactory().get("/api/v1/capabilities/")
        request.user = user
        from hub.apps.api.capabilities import get_capabilities_for_request

        return get_capabilities_for_request(request)

    assert _caps_for(True)["ux_v2"] is True
    assert _caps_for(False)["ux_v2"] is False


# ---------------------------------------------------------------------------
# openspec add-databricks-control-plane P0 — databricks capability flag
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestDatabricksCapability:
    """Pin the truth table for the ``databricks`` capability key.

    The SPA's /databricks route gates on
    ``<CapabilityRoute capability="databricks">``. Before the wiring the
    key was never sent, so every tenant was silently redirected to
    /unavailable (JOURNEY-DB-001 timed out waiting for the management
    page). Explicit opt-in: ``databricks_control_plane_enabled`` AND
    the P0 emergency kill switch must be open.
    """

    @staticmethod
    def _new_tenant(*, control_plane_enabled=False, kill_switch=False):
        import uuid

        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus

        uid = uuid.uuid4().hex[:8]
        return Tenant.objects.create(
            name=f"Databricks {uid}",
            slug=f"databricks-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            databricks_control_plane_enabled=control_plane_enabled,
            databricks_workspaces_kill_switch=kill_switch,
        )

    @staticmethod
    def _caps_for(tenant):
        import uuid

        from rest_framework.test import APIRequestFactory

        from hub.apps.api.capabilities import get_capabilities_for_request
        from hub.apps.users.models import User, UserStatus

        uid = uuid.uuid4().hex[:8]
        user = User.objects.create_user(
            email=f"databricks-{uid}@example.com",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        request = APIRequestFactory().get("/api/v1/capabilities/")
        request.user = user
        return get_capabilities_for_request(request)

    def test_enabled_tenant_with_open_kill_switch(self):
        caps = self._caps_for(self._new_tenant(control_plane_enabled=True, kill_switch=False))
        assert caps["databricks"] is True

    def test_kill_switch_closes_the_capability(self):
        caps = self._caps_for(self._new_tenant(control_plane_enabled=True, kill_switch=True))
        assert caps["databricks"] is False

    def test_defaults_are_opt_in(self):
        caps = self._caps_for(self._new_tenant())
        assert caps["databricks"] is False

    def test_anonymous_request_reports_unavailable(self):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.test import APIRequestFactory

        from hub.apps.api.capabilities import get_capabilities_for_request

        request = APIRequestFactory().get("/api/v1/capabilities/")
        request.user = AnonymousUser()
        assert get_capabilities_for_request(request)["databricks"] is False
