"""
Phase 240.4.B.5 — feature-flag gating tests.

Asserts the two-flag conjunctive contract:

* ``Tenant.data_quality_enabled`` (default True) is the BASE kill-
  switch — when False, ALL DQ API endpoints (DQRunViewSet,
  DQAlertingRuleViewSet, DQQualityViewSet) return HTTP 403 +
  ``error_code: DATA_QUALITY_DISABLED`` regardless of role.
* ``Tenant.data_quality_advanced_enabled`` (default False)
  ADDITIONALLY gates the Phase 240.3.B advanced endpoints
  (anomalies / trends / scorecards / root_cause_analysis).  The base
  flag must ALSO be True for the advanced surface to work — i.e. the
  gate is conjunctive ``data_quality_enabled AND
  data_quality_advanced_enabled``.

Test matrix (4 cells × N endpoint families):

  | base | advanced | basic endpoints | advanced endpoints |
  |------|----------|-----------------|--------------------|
  | T    | T        | 200             | 200                |
  | T    | F        | 200             | 403 advanced       |
  | F    | T        | 403 base        | 403 base           |
  | F    | F        | 403 base        | 403 base           |

All tests use real DB rows + real DRF dispatch — no mocks.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Endpoint inventory.  Each tuple: ``(label, http_method, url, body)``.
# Hit at request-time so the URL / payload reflects whatever the
# tenant + user fixtures resolve to at runtime.
# ─────────────────────────────────────────────────────────────────────


def _basic_endpoints(self):
    """Endpoints gated by the BASE flag (data_quality_enabled)."""
    return [
        ("DQRun list", "get", "/api/v1/dq/runs/", None),
        ("Alerting rule list", "get", "/api/v1/dq/alerting-rules/", None),
    ]


def _advanced_endpoints(self):
    """Endpoints gated by BOTH flags (data_quality_advanced_enabled
    AND data_quality_enabled)."""
    return [
        ("Anomalies", "get", "/api/v1/dq/quality/anomalies/", None),
        ("Trends", "get", f"/api/v1/dq/quality/trends/?asset_id={self.asset.id}", None),
        ("Scorecards", "get", "/api/v1/dq/quality/scorecards/", None),
        (
            "RootCause",
            "get",
            f"/api/v1/dq/quality/root_cause_analysis/?dq_run_id={self.dq_run.id}",
            None,
        ),
    ]


def _hit(client: APIClient, method: str, url: str, body: dict | None = None):
    fn = getattr(client, method)
    if body is None:
        return fn(url)
    return fn(url, body, format="json")


# ─────────────────────────────────────────────────────────────────────
# Shared fixture: an asset + a SUCCEEDED DQ run for the trends /
# root-cause endpoints to bind to.
# ─────────────────────────────────────────────────────────────────────


class FeatureFlagTestBase(DQAPITestBase):

    def setUp(self):
        super().setUp()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
        from django.utils import timezone as dj_tz

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="ff-asset",
            name="FF Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=92.5,
            checks_json=[],
            details_json={},
            completed_at=dj_tz.now(),
        )

    def _set_flags(self, *, base: bool, advanced: bool):
        """Mutate tenant flags atomically."""
        self.tenant.data_quality_enabled = base
        self.tenant.data_quality_advanced_enabled = advanced
        self.tenant.save(
            update_fields=["data_quality_enabled", "data_quality_advanced_enabled"],
        )
        self.tenant.refresh_from_db()


# ─────────────────────────────────────────────────────────────────────
# Truth-table coverage.
# ─────────────────────────────────────────────────────────────────────


class TestBaseFlagOnAdvancedFlagOn(FeatureFlagTestBase):
    """[T, T] — full access. Basic + advanced endpoints all 200."""

    def test_basic_endpoints_return_200(self):
        self._set_flags(base=True, advanced=True)
        for label, method, url, body in _basic_endpoints(self):
            r = _hit(self.client, method, url, body)
            self.assertEqual(
                r.status_code, status.HTTP_200_OK,
                f"{label}: expected 200, got {r.status_code} body={r.content!r}",
            )

    def test_advanced_endpoints_return_200(self):
        self._set_flags(base=True, advanced=True)
        for label, method, url, body in _advanced_endpoints(self):
            r = _hit(self.client, method, url, body)
            self.assertEqual(
                r.status_code, status.HTTP_200_OK,
                f"{label}: expected 200, got {r.status_code} body={r.content!r}",
            )


class TestBaseFlagOnAdvancedFlagOff(FeatureFlagTestBase):
    """[T, F] — basic OK, advanced 403 with DATA_QUALITY_ADVANCED_DISABLED."""

    def test_basic_endpoints_return_200(self):
        self._set_flags(base=True, advanced=False)
        for label, method, url, body in _basic_endpoints(self):
            r = _hit(self.client, method, url, body)
            self.assertEqual(
                r.status_code, status.HTTP_200_OK,
                f"{label}: expected 200, got {r.status_code} body={r.content!r}",
            )

    def test_advanced_endpoints_return_403_with_advanced_disabled_code(self):
        self._set_flags(base=True, advanced=False)
        for label, method, url, body in _advanced_endpoints(self):
            r = _hit(self.client, method, url, body)
            self.assertEqual(
                r.status_code, status.HTTP_403_FORBIDDEN,
                f"{label}: expected 403, got {r.status_code} body={r.content!r}",
            )
            payload = r.json()
            self.assertEqual(
                payload.get("error_code"),
                "DATA_QUALITY_ADVANCED_DISABLED",
                f"{label}: expected error_code "
                f"DATA_QUALITY_ADVANCED_DISABLED, got "
                f"{payload.get('error_code')!r} (full body={payload!r})",
            )


class TestBaseFlagOff(FeatureFlagTestBase):
    """[F, *] — base flag wins.  Both basic AND advanced endpoints 403
    with the BASE error_code regardless of advanced flag value."""

    def _assert_all_403_base_disabled(self):
        for label, method, url, body in _basic_endpoints(self) + _advanced_endpoints(self):
            r = _hit(self.client, method, url, body)
            self.assertEqual(
                r.status_code, status.HTTP_403_FORBIDDEN,
                f"{label}: expected 403, got {r.status_code} body={r.content!r}",
            )
            payload = r.json()
            self.assertEqual(
                payload.get("error_code"),
                "DATA_QUALITY_DISABLED",
                f"{label}: expected error_code DATA_QUALITY_DISABLED, "
                f"got {payload.get('error_code')!r} (full body={payload!r})",
            )

    def test_base_off_advanced_off_blocks_everything(self):
        self._set_flags(base=False, advanced=False)
        self._assert_all_403_base_disabled()

    def test_base_off_advanced_on_still_blocks_advanced_via_base(self):
        """[F, T] — base flag is dominant.  Even with advanced=True,
        the conjunctive gate fails on the base flag first, so the
        error_code is BASE-disabled (not advanced-disabled)."""
        self._set_flags(base=False, advanced=True)
        self._assert_all_403_base_disabled()


# ─────────────────────────────────────────────────────────────────────
# Default-on / default-off semantics on a fresh tenant.
# ─────────────────────────────────────────────────────────────────────


class TestDefaultFlagSemantics(FeatureFlagTestBase):
    """A fresh tenant has the documented defaults: base=True, advanced=False."""

    def test_fresh_tenant_has_base_enabled_advanced_disabled(self):
        # NEW tenant, NOT the test fixture tenant.
        suffix = uuid.uuid4().hex[:8]
        fresh = Tenant.objects.create(
            name=f"Fresh {suffix}",
            slug=f"fresh-{suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        fresh.refresh_from_db()
        self.assertTrue(
            fresh.data_quality_enabled,
            "Phase 240.4.B.1: data_quality_enabled MUST default True "
            "(D240.18 — existing tenants keep current behaviour).",
        )
        self.assertFalse(
            fresh.data_quality_advanced_enabled,
            "Phase 240.4.B.1: data_quality_advanced_enabled MUST default "
            "False (D240.18 — advanced surface needs staged rollout).",
        )


# ─────────────────────────────────────────────────────────────────────
# Capability surface — /api/v1/capabilities/ exposes the flags so the
# SPA can render menus correctly per 240.4.B.4.
# ─────────────────────────────────────────────────────────────────────


class TestCapabilitiesExposeFlags(FeatureFlagTestBase):

    def test_capabilities_endpoint_exposes_data_quality_flags(self):
        self._set_flags(base=True, advanced=False)
        r = self.client.get("/api/v1/capabilities/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        caps = r.json().get("capabilities", {})
        self.assertIn(
            "data_quality", caps,
            "Phase 240.4.B.4: /api/v1/capabilities/ MUST expose "
            "``data_quality`` so the SPA can render the DQ menu.",
        )
        self.assertIn(
            "data_quality_advanced", caps,
            "Phase 240.4.B.4: /api/v1/capabilities/ MUST expose "
            "``data_quality_advanced``.",
        )
        self.assertEqual(caps["data_quality"], True)
        self.assertEqual(caps["data_quality_advanced"], False)

    def test_capabilities_reflect_flag_changes(self):
        # Flip both; capability response should reflect the new state.
        self._set_flags(base=False, advanced=True)
        r = self.client.get("/api/v1/capabilities/")
        caps = r.json().get("capabilities", {})
        self.assertEqual(caps["data_quality"], False)
        # The advanced capability is conjunctive in the API surface
        # too — when the base is off, advanced is off regardless of
        # the underlying flag.  This matches the backend gate
        # semantics so the SPA never advertises a sub-feature whose
        # parent is disabled.
        self.assertEqual(
            caps["data_quality_advanced"], False,
            "Capability ``data_quality_advanced`` MUST be False "
            "whenever ``data_quality`` is False — conjunctive.",
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 240.4.B audit-fix Gap 1 — DQTestBase regression pin.
# ─────────────────────────────────────────────────────────────────────


class TestDQTestBaseDefaultsBothFlagsOn(FeatureFlagTestBase):
    """Phase 240.4.B audit-fix Gap 1 regression.

    The test base class (``DQTestBase``) MUST default both DQ flags
    ON in test fixtures, so the existing 240.3.B advanced-endpoint
    tests don't regress to 403 on the conjunctive gate.  The
    PRODUCTION default for ``data_quality_advanced_enabled`` is
    ``False`` (D240.18, staged rollout) but TEST fixtures want full
    DQ access by default — this test pins that contract so a future
    refactor of ``test_base.py`` doesn't silently revert it.
    """

    def test_base_class_tenant_has_both_flags_on(self):
        # ``self.tenant`` is created by ``DQTestBase.setUp()`` (via
        # FeatureFlagTestBase → DQAPITestBase → DQTestBase chain).
        # The flag values come straight from the model — assert
        # against the current DB row to catch any silent reversion.
        self.tenant.refresh_from_db()
        self.assertTrue(
            self.tenant.data_quality_enabled,
            "Phase 240.4.B audit-fix Gap 1: DQTestBase MUST default "
            "data_quality_enabled=True so 240.3.B basic-endpoint "
            "tests don't regress.",
        )
        self.assertTrue(
            self.tenant.data_quality_advanced_enabled,
            "Phase 240.4.B audit-fix Gap 1: DQTestBase MUST default "
            "data_quality_advanced_enabled=True so 240.3.B "
            "advanced-endpoint tests don't regress to 403.",
        )

    def test_default_test_tenant_can_hit_advanced_endpoints(self):
        """End-to-end regression — without the Gap 1 fix, this would
        return 403 from the conjunctive flag gate."""
        # Assert against an advanced endpoint via the test client
        # (no ``_set_flags`` call — relies on the base-class defaults).
        r = self.client.get("/api/v1/dq/quality/anomalies/")
        self.assertEqual(
            r.status_code, status.HTTP_200_OK,
            f"Phase 240.4.B audit-fix Gap 1: with default fixtures, "
            f"DQQualityViewSet must return 200 (got {r.status_code} "
            f"body={r.content!r}).  If this fails with 403 + "
            f"DATA_QUALITY_ADVANCED_DISABLED, the test base lost its "
            f"default-on flag override.",
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 240.4.B audit-fix — deprecated /api/v1/quality/ alias gate.
# ─────────────────────────────────────────────────────────────────────


class TestDeprecatedAliasInheritsGate(FeatureFlagTestBase):
    """The deprecated ``/api/v1/quality/`` alias mounts (Phase
    240.3.B.3 + Phase 240.3.E.1) MUST inherit the DQ feature-flag
    gate — the alias is purely a URL surface, not a permissions
    side-channel.  ``DeprecatedDQRunViewSet(DeprecationHeadersMixin,
    DQRunViewSet)`` and ``DeprecatedDQQualityViewSet(DeprecationHeadersMixin,
    DQQualityViewSet)`` get the gate via MRO inheritance from
    ``DQFeatureFlagMixin`` on the canonical viewsets — this test
    pins that wiring."""

    def test_deprecated_runs_alias_403s_when_base_flag_off(self):
        self._set_flags(base=False, advanced=True)
        r = self.client.get("/api/v1/quality/runs/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            r.json().get("error_code"), "DATA_QUALITY_DISABLED",
            "Deprecated /api/v1/quality/runs/ MUST inherit the base "
            "flag gate via MRO.  If this 200s, the alias has dropped "
            "the gate.",
        )

    def test_deprecated_quality_alias_403s_when_advanced_flag_off(self):
        self._set_flags(base=True, advanced=False)
        r = self.client.get("/api/v1/quality/anomalies/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            r.json().get("error_code"), "DATA_QUALITY_ADVANCED_DISABLED",
            "Deprecated /api/v1/quality/anomalies/ MUST inherit the "
            "advanced flag gate (conjunctive) via MRO.",
        )
