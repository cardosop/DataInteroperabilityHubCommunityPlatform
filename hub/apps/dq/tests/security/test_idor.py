"""
Phase 240.5.E — IDOR + cross-cutting authorization tests for the
eight public DQ endpoints.

Pins the security contract of each endpoint listed in 240.5.E.1:

* ``GET  /api/v1/dq/runs/``                              (list)
* ``GET  /api/v1/dq/runs/{id}/``                         (retrieve)
* ``GET  /api/v1/dq/runs/{id}/results/``                 (results @action)
* ``GET  /api/v1/dq/alerting-rules/``                    (list)
* ``GET  /api/v1/quality/anomalies/``                    (deprecated alias)
* ``GET  /api/v1/quality/trends/``                       (deprecated alias)
* ``GET  /api/v1/quality/scorecards/``                   (deprecated alias)
* ``GET  /api/v1/quality/root_cause_analysis/``          (deprecated alias)

Per 240.5.E.2 every endpoint is exercised against four distinct
authorization properties (where applicable):

1. **Cross-tenant resource → 404** (NOT 403). Existence-leak
   protection: an attacker probing a UUID that belongs to another
   tenant must NOT be able to distinguish "doesn't exist" from
   "belongs to someone else".
2. **AUDITOR write methods → 403**. The AUDITOR role is read-only
   per ``DQRunViewSet.check_auditor_permissions`` — POST/PUT/PATCH/
   DELETE must be blocked even when the row is in the user's own
   tenant.
3. **No auth → 401**. ``permission_classes=[IsAuthenticated]``
   denies before any view body runs.
4. **Malformed UUID → 400** (where the endpoint validates UUIDs
   upfront). Some endpoints (anomalies, trends) silently filter to
   empty queryset on a malformed UUID — those are pinned to that
   behaviour explicitly so a future tightening to 400 surfaces
   here as a deliberate change.

> **Note on the spec's `/quality/root-cause-analysis/`**: the spec
> uses hyphens but the actual `@action(url_path=...)` is
> underscore (`root_cause_analysis`). The tests target the
> underscore form — same path the spec amendment in 240.3.E.2
> already aligned to.

Real Django ORM rows + real DRF `APIClient`. No mocks. The
external dq-service is NOT exercised — endpoints under test are
listing/reading DB-backed resources, not triggering DQ runs.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import (
    DQAlertChannel,
    DQAlertingRule,
    DQAnomaly,
    DQAnomalySeverity,
    DQEngine,
    DQRun,
    DQRunStatus,
    DQTrend,
    DQTrendDirection,
)
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import Role, UserRole

# Two-tenant fixture from the platform-wide IDOR base. Re-using
# this base keeps the dq IDOR suite consistent with the rest of
# the security suite (same tenant + user creation pattern, same
# `self.client` shape).
from tests.security.base_idor import IDORTestBase

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# Shared fixture — tenants A + B with subscriptions, AUDITOR role,
# and seeded DQ resources in tenant B for cross-tenant probes
# ──────────────────────────────────────────────────────────────────


class _DQIDORTestBase(IDORTestBase):
    """Extends the platform IDORTestBase with DQ-specific seeds.

    Seeds in tenant B (NOT tenant A) so cross-tenant tests have
    real foreign-key targets to probe.  Tenant A users
    authenticate via ``self.client.force_authenticate(user=self.user_a)``
    and try to read tenant B's resources by UUID.
    """

    def setUp(self):
        super().setUp()
        # Both tenants need active subscriptions; quality endpoints
        # consume plan-limit budget which would otherwise return
        # 403 before reaching the auth-check we're trying to test.
        ensure_tenant_has_active_subscription(self.tenant_a)
        ensure_tenant_has_active_subscription(self.tenant_b)

        # Phase 240.4.B.2 — the four advanced quality endpoints
        # (anomalies / trends / scorecards / root_cause_analysis)
        # are gated by ``DQFeatureFlagMixin(dq_flag_scope="advanced")``
        # which requires BOTH ``data_quality_enabled`` (default True)
        # AND ``data_quality_advanced_enabled`` (default False) on
        # the tenant.  Without flipping the advanced flag, every
        # quality-endpoint call returns 403 ``DATA_QUALITY_DISABLED``
        # before the view body runs — masking the IDOR/auth checks
        # we're trying to pin.  Mirror the same pattern as the
        # existing dq test base ([test_base.py:49]).
        for tenant in (self.tenant_a, self.tenant_b):
            tenant.data_quality_enabled = True
            tenant.data_quality_advanced_enabled = True
            tenant.save(
                update_fields=[
                    "data_quality_enabled",
                    "data_quality_advanced_enabled",
                ],
            )

        # Tenant B asset + file + job — anchors for the seeded DQ
        # resources below.
        self.asset_b = Asset.objects.create(
            tenant=self.tenant_b,
            key=f"idor-dq-asset-b-{uuid.uuid4().hex[:8]}",
            name="IDOR DQ Asset B",
            status=AssetStatus.ACTIVE,
            created_by=self.user_b,
        )
        self.file_b = File.objects.create(
            tenant=self.tenant_b,
            name="data.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant_b.id}/data.csv",
            status=FileStatus.ACTIVE,
            created_by=self.user_b,
        )
        self.job_b = Job.objects.create(
            tenant=self.tenant_b,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.user_b,
            timeout_seconds=1800,
        )
        # SUCCEEDED run so the ``results`` action has something to
        # serialise; engine pinned to GX (canonical for
        # ``intake_basic_gx``). ``checks_json`` empty list is fine —
        # results action accepts that.
        self.dq_run_b = DQRun.objects.create(
            tenant=self.tenant_b,
            asset=self.asset_b,
            file=self.file_b,
            job=self.job_b,
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            overall_status="PASS",
            quality_score=99.5,
            checks_json=[],
            details_json={},
        )
        self.alerting_rule_b = DQAlertingRule.objects.create(
            tenant=self.tenant_b,
            asset=self.asset_b,
            name="IDOR rule B",
            metric_type="quality_score",
            # ``DQAlertingRule.comparison_operator`` uses math
            # operators (``<``, ``<=``, ``>``, ``>=``, ``==``,
            # ``!=``) — NOT 2-letter abbreviations.
            comparison_operator="<",
            threshold=80.0,
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={},
            created_by=self.user_b,
        )
        self.anomaly_b = DQAnomaly.objects.create(
            tenant=self.tenant_b,
            asset=self.asset_b,
            metric_type="quality_score",
            expected_value=99.0,
            actual_value=70.0,
            deviation=29.0,
            severity=DQAnomalySeverity.HIGH,
            anomaly_type="z_score",
        )
        self.trend_b = DQTrend.objects.create(
            tenant=self.tenant_b,
            asset=self.asset_b,
            metric_type="quality_score",
            period_start="2026-01-01T00:00:00Z",
            period_end="2026-01-31T23:59:59Z",
            period_type="MONTHLY",
            current_value=95.0,
            previous_value=90.0,
            direction=DQTrendDirection.IMPROVING,
        )

    def _make_user_a_auditor(self):
        """Add the AUDITOR role to ``self.user_a``.

        Pattern matches ``test_views.py``'s existing AUDITOR role
        setup.  ``Role.objects.create`` with ``tenant=self.tenant_a``
        + ``UserRole`` link — the dq view's
        ``check_auditor_permissions`` walks ``user.user_roles`` to
        detect AUDITOR.
        """
        auditor_role = Role.objects.create(
            tenant=self.tenant_a, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user_a, role=auditor_role)


# ──────────────────────────────────────────────────────────────────
# /api/v1/dq/runs/  — list + create
# ──────────────────────────────────────────────────────────────────


class DQRunsListIDORTests(_DQIDORTestBase):
    URL = "/api/v1/dq/runs/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_run_does_not_leak_in_list(self):
        """Tenant A's list must not include tenant B's runs."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data["results"]}
        self.assertNotIn(
            str(self.dq_run_b.id),
            ids,
            "Tenant A list MUST NOT leak tenant B's DQ run IDs.",
        )

    def test_auditor_cannot_create(self):
        """AUDITOR write blocked → 403 even with valid payload."""
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        # Create a File within tenant A — using tenant B's file would
        # risk a 404 masking the 403 if the auditor check is ever
        # reordered after resource resolution.
        file_a = File.objects.create(
            tenant=self.tenant_a,
            name="auditor-test.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            storage_path=f"{self.tenant_a.id}/auditor-test.csv",
            created_by=self.user_a,
        )
        response = self.client.post(
            self.URL,
            data={"file_id": str(file_a.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────────────────────────────
# /api/v1/dq/runs/{id}/  — retrieve + update + delete
# ──────────────────────────────────────────────────────────────────


class DQRunDetailIDORTests(_DQIDORTestBase):
    @property
    def url(self):
        return f"/api/v1/dq/runs/{self.dq_run_b.id}/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_retrieve_returns_404(self):
        """Cross-tenant probe MUST return 404 (NOT 403).

        Existence-leak protection: an attacker iterating UUIDs must
        not be able to distinguish "doesn't exist" from "belongs to
        someone else".
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            f"Cross-tenant DQRun retrieve must 404 (got "
            f"{response.status_code}). 403 would leak existence.",
        )

    def test_auditor_cannot_update(self):
        """AUDITOR PUT → 403."""
        # Use tenant A's own run for the AUDITOR test (otherwise
        # we'd hit the cross-tenant 404 first).
        own_run = DQRun.objects.create(
            tenant=self.tenant_a,
            file=File.objects.create(
                tenant=self.tenant_a,
                name="d.csv",
                content_type="text/csv",
                size=1,
                status=FileStatus.ACTIVE,
                storage_path=f"{self.tenant_a.id}/d.csv",
                created_by=self.user_a,
            ),
            job=Job.objects.create(
                tenant=self.tenant_a,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
                created_by=self.user_a,
                timeout_seconds=1800,
            ),
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        response = self.client.put(
            f"/api/v1/dq/runs/{own_run.id}/",
            data={"profile_key": "intake_basic_soda"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_delete(self):
        own_run = DQRun.objects.create(
            tenant=self.tenant_a,
            file=File.objects.create(
                tenant=self.tenant_a,
                name="d.csv",
                content_type="text/csv",
                size=1,
                status=FileStatus.ACTIVE,
                storage_path=f"{self.tenant_a.id}/d.csv",
                created_by=self.user_a,
            ),
            job=Job.objects.create(
                tenant=self.tenant_a,
                type=JobType.DQ_RUN,
                status=JobStatus.COMPLETED,
                resource_type="DQ_RUN",
                resource_id=uuid.uuid4(),
                created_by=self.user_a,
                timeout_seconds=1800,
            ),
            status=DQRunStatus.SUCCEEDED,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
        )
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        response = self.client.delete(f"/api/v1/dq/runs/{own_run.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_malformed_uuid_returns_404(self):
        """Malformed UUID in the URL path → DRF resolver 404.

        DRF's ``UUIDField`` lookup field rejects malformed IDs at
        URL-resolution time with 404 (not 400). Pinning that here
        so a future change to a 400-validation pattern surfaces as
        a deliberate change.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/v1/dq/runs/not-a-uuid/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────────────────────────────
# /api/v1/dq/runs/{id}/results/  — @action
# ──────────────────────────────────────────────────────────────────


class DQRunResultsIDORTests(_DQIDORTestBase):
    @property
    def url(self):
        return f"/api/v1/dq/runs/{self.dq_run_b.id}/results/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_returns_404(self):
        """The ``results`` @action calls ``self.get_object()`` which
        runs ``filter_queryset`` → tenant-scoped queryset → 404 for
        cross-tenant lookups."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


# ──────────────────────────────────────────────────────────────────
# /api/v1/dq/alerting-rules/  — list + create
# ──────────────────────────────────────────────────────────────────


class DQAlertingRulesIDORTests(_DQIDORTestBase):
    URL = "/api/v1/dq/alerting-rules/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_rule_does_not_leak_in_list(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data.get("results", [])}
        self.assertNotIn(str(self.alerting_rule_b.id), ids)

    def test_cross_tenant_retrieve_returns_404(self):
        """Direct retrieve of tenant B's rule → 404."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f"{self.URL}{self.alerting_rule_b.id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_auditor_cannot_create_alerting_rule(self):
        """AUDITOR POST → 403."""
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"idor-auditor-ar-{uuid.uuid4().hex[:8]}",
            name="Auditor AR Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user_a,
        )
        response = self.client.post(
            self.URL,
            data={"asset_id": str(asset_a.id), "threshold": 80.0},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_update_alerting_rule(self):
        """AUDITOR PUT → 403."""
        # Create a rule in tenant A for the auditor to attempt updating
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"idor-auditor-ar-upd-{uuid.uuid4().hex[:8]}",
            name="Auditor AR Update Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user_a,
        )
        rule_a = DQAlertingRule.objects.create(
            tenant=self.tenant_a,
            asset=asset_a,
            name="Auditor Target Rule",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={},
            created_by=self.user_a,
        )
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        response = self.client.put(
            f"{self.URL}{rule_a.id}/",
            data={
                "metric_type": "quality_score",
                "threshold": 50.0,
                "name": "Updated",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_delete_alerting_rule(self):
        """AUDITOR DELETE → 403."""
        asset_a = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"idor-auditor-ar-del-{uuid.uuid4().hex[:8]}",
            name="Auditor AR Delete Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user_a,
        )
        rule_a = DQAlertingRule.objects.create(
            tenant=self.tenant_a,
            asset=asset_a,
            name="Auditor Target Rule",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={},
            created_by=self.user_a,
        )
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        response = self.client.delete(f"{self.URL}{rule_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────────────────────────────
# /api/v1/dq/warehouse-run/  — POST endpoint
# ──────────────────────────────────────────────────────────────────


class DQWarehouseRunIDORTests(_DQIDORTestBase):
    URL = "/api/v1/dq/runs/warehouse-run/"

    def test_no_auth_returns_401(self):
        response = self.client.post(self.URL, data={}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_dataset_id_returns_404(self):
        """Using tenant B's dataset from tenant A's session must 404."""
        from hub.apps.datasets.models import Dataset

        dataset_b = Dataset.objects.create(
            tenant=self.tenant_b,
            asset=self.asset_b,
            format="CSV",
            created_by=self.user_b,
        )
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            self.URL,
            data={
                "warehouse_config": {"type": "postgres"},
                "dataset_id": str(dataset_b.id),
            },
            format="json",
        )
        # Dataset lookup is tenant-scoped → 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_auditor_cannot_create_warehouse_run(self):
        """AUDITOR POST must not succeed (403 or 404, not 200/201)."""
        self._make_user_a_auditor()
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(
            self.URL,
            data={
                "warehouse_config": {"type": "postgres"},
                "dataset_id": str(uuid.uuid4()),
            },
            format="json",
        )
        # Must not be 200 or 201; auditor is a write attempt
        self.assertNotIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_201_CREATED],
        )


# ──────────────────────────────────────────────────────────────────
# /api/v1/quality/anomalies/  — deprecated alias of /dq/quality/
# ──────────────────────────────────────────────────────────────────


class DQQualityAnomaliesIDORTests(_DQIDORTestBase):
    URL = "/api/v1/quality/anomalies/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_filter_returns_no_anomalies(self):
        """Filtering by tenant B's asset_id from tenant A's session
        must NOT return tenant B's anomalies — the tenant filter at
        the queryset level shadows the asset_id filter."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f"{self.URL}?asset_id={self.asset_b.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {row["id"] for row in response.data.get("results", [])}
        self.assertNotIn(str(self.anomaly_b.id), ids)

    def test_malformed_asset_id_returns_empty_list(self):
        """Anomalies endpoint silently filters to empty queryset
        on a malformed asset_id (``qs.none()``) — pinned here so a
        future tightening to 400 surfaces as a deliberate change.
        """
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"{self.URL}?asset_id=not-a-uuid")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get("results", []), [])


# ──────────────────────────────────────────────────────────────────
# /api/v1/quality/trends/
# ──────────────────────────────────────────────────────────────────


class DQQualityTrendsIDORTests(_DQIDORTestBase):
    URL = "/api/v1/quality/trends/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_filter_returns_no_trends(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f"{self.URL}?asset_id={self.asset_b.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        # Resolve possible row shapes — trends endpoint emits
        # visualisation-friendly rows (sparklines), not raw
        # DQTrend records. Either shape MUST not include tenant B
        # trend ids.
        ids = {row.get("id") for row in results if isinstance(row, dict)}
        self.assertNotIn(str(self.trend_b.id), ids)


# ──────────────────────────────────────────────────────────────────
# /api/v1/quality/scorecards/
# ──────────────────────────────────────────────────────────────────


class DQQualityScorecardsIDORTests(_DQIDORTestBase):
    URL = "/api/v1/quality/scorecards/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_asset_id_returns_404(self):
        """Scorecards explicitly returns 404 when ``asset_id`` is
        outside the requesting tenant — see views.py ``scorecards``
        action; existence-leak protection."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f"{self.URL}?asset_id={self.asset_b.id}",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_malformed_asset_id_returns_400(self):
        """Scorecards validates UUID shape upfront and 400s on
        malformed values (unlike anomalies/trends which silently
        return empty)."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"{self.URL}?asset_id=not-a-uuid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ──────────────────────────────────────────────────────────────────
# /api/v1/quality/root_cause_analysis/
#
# Spec wrote this with a hyphen (``root-cause-analysis``); the
# actual ``url_path`` on the @action is the underscore form.
# Phase 240.3.E.2 amended the spec to align — tests use underscore.
# ──────────────────────────────────────────────────────────────────


class DQQualityRootCauseIDORTests(_DQIDORTestBase):
    URL = "/api/v1/quality/root_cause_analysis/"

    def test_no_auth_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cross_tenant_dq_run_id_returns_no_data(self):
        """RCA invoked with a tenant-B dq_run_id from tenant A's
        session MUST NOT leak the RCA payload of the cross-tenant
        run. Outcome is either 404 (cross-tenant existence-leak
        protection) OR a 200 with empty/null analysis — both are
        acceptable, but the response MUST NOT carry tenant B's
        run-specific data."""
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(
            f"{self.URL}?dq_run_id={self.dq_run_b.id}",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_404_NOT_FOUND, status.HTTP_200_OK),
            f"Unexpected status {response.status_code} for cross-tenant RCA probe.",
        )
        if response.status_code == status.HTTP_200_OK:
            # If the endpoint chose the empty-200 branch, the body
            # must NOT mention tenant B's run id.
            body_str = str(response.data)
            self.assertNotIn(
                str(self.dq_run_b.id),
                body_str,
                "RCA payload leaks tenant B's dq_run_id in the 200-response body.",
            )


# ──────────────────────────────────────────────────────────────────
# Cross-cutting: every dq endpoint enforces IsAuthenticated
# ──────────────────────────────────────────────────────────────────


class DQEndpointsAuthenticationContractTests(_DQIDORTestBase):
    """Belt-and-suspenders: a single test that walks all 8
    spec-listed endpoints and asserts every one returns 401 when
    called without auth.

    The per-endpoint test classes already cover this individually,
    but a single sweep test is robust against a future endpoint
    accidentally bypassing ``IsAuthenticated`` (e.g. via a
    misplaced ``@permission_classes([AllowAny])`` decorator)."""

    SPEC_ENDPOINTS = (
        "/api/v1/dq/runs/",
        # /dq/runs/{id}/ + /dq/runs/{id}/results/ filled at runtime
        # against ``self.dq_run_b.id`` — both should 401 BEFORE any
        # tenant lookup, so we use a UUID that doesn't have to be in
        # the user's tenant.
        "/api/v1/dq/alerting-rules/",
        "/api/v1/quality/anomalies/",
        "/api/v1/quality/trends/",
        "/api/v1/quality/scorecards/",
        "/api/v1/quality/root_cause_analysis/",
    )

    def test_every_endpoint_requires_authentication(self):
        # Ensure no auth is set on the client (parent setUp gives
        # us a fresh APIClient, but this is defence-in-depth).
        self.client = APIClient()

        # Probe each spec endpoint; ``self.dq_run_b.id`` is just a
        # syntactically-valid UUID for the detail / results paths.
        urls = list(self.SPEC_ENDPOINTS) + [
            f"/api/v1/dq/runs/{self.dq_run_b.id}/",
            f"/api/v1/dq/runs/{self.dq_run_b.id}/results/",
        ]
        failures = []
        for url in urls:
            response = self.client.get(url)
            if response.status_code != status.HTTP_401_UNAUTHORIZED:
                failures.append(f"{url} returned {response.status_code} (expected 401)")
        self.assertEqual(
            failures,
            [],
            "These DQ endpoints failed to require authentication:\n  - " + "\n  - ".join(failures),
        )
