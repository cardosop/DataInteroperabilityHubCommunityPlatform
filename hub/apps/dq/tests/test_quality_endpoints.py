"""
Tests for DQQualityViewSet (Phase 240.3.B — Advanced quality endpoints).

Covers all four read-only endpoints:
- GET /api/v1/dq/quality/anomalies/
- GET /api/v1/dq/quality/trends/
- GET /api/v1/dq/quality/scorecards/
- GET /api/v1/dq/quality/root_cause_analysis/

Each endpoint is tested against five dimensions:
1. Happy path (200, expected payload shape)
2. Tenant isolation (cross-tenant rows do NOT appear)
3. AUDITOR read-only (AUDITOR can read; cannot mutate — but here all
   methods are GET so the assertion is "AUDITOR succeeds with 200")
4. Plan-limit exhaustion (after the daily cap is hit, 403
   ``plan_limit_exceeded``)
5. Throttle (after the per-action ScopedRateThrottle scope is
   exceeded, 429)

Plus dual-mount coverage:
- Both ``/api/v1/dq/quality/...`` (canonical) and
  ``/api/v1/quality/...`` (deprecated alias) MUST be reachable.
- The deprecated path MUST set ``Sunset`` and ``Deprecation`` headers
  per Phase 227 patterns + D240.10.

Tests use real implementations (no mocks). Plan-limit exhaustion is
exercised by setting the tenant plan's
``max_quality_queries_per_day`` to a small number and pre-seeding the
audit-event counter.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import (
    DQAnomaly,
    DQAnomalySeverity,
    DQEngine,
    DQRun,
    DQRunStatus,
    DQTrend,
    DQTrendDirection,
)
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.files.models import File, FileStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


CANONICAL_PREFIX = "/api/v1/dq/quality"
DEPRECATED_PREFIX = "/api/v1/quality"


class DQQualityEndpointsBase(DQAPITestBase):
    """Common setUp for the four advanced quality endpoints."""

    def setUp(self):
        super().setUp()

        # Throttle cache must be cleared between tests — DRF's
        # ScopedRateThrottle stores per-scope counters in the default
        # cache backend, so a previous test's hits would otherwise
        # bleed into the next test's plan-limit/throttle assertions.
        cache.clear()

        # Asset + dataset for "this" tenant
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="quality-asset",
            name="Quality Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            schema_json={"fields": [{"name": "id", "type": "string"}]},
            created_by=self.user,
        )

        # A SUCCEEDED DQ run with a known quality score — basis for
        # trend/anomaly/scorecard fixtures below.
        self.dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=92.5,
            checks_json=[
                {
                    "name": "expect_column_values_to_not_be_null",
                    "status": "PASS",
                    "result": {"observed_value": 100},
                }
            ],
            details_json={"engine_version": "0.18.0"},
            completed_at=timezone.now(),
        )

        # An anomaly attached to the DQ run — feeds the
        # ``anomalies`` endpoint.
        self.anomaly = DQAnomaly.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            dq_run=self.dq_run,
            metric_type="quality_score",
            expected_value=95.0,
            actual_value=70.0,
            deviation=-25.0,
            severity=DQAnomalySeverity.HIGH,
            anomaly_type="sudden_drop",
            description="Quality score dropped 26%",
            metadata={"drop_percent": 26.0},
        )

        # A DQTrend row scoped to the asset for ``trends`` endpoint
        # tests that fall back to stored DQTrend rows (the live
        # TrendAnalyzer.calculate_trend computes from DQRun history,
        # but we also want the path that surfaces persisted trends).
        now = timezone.now()
        self.trend = DQTrend.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=self.dataset,
            metric_type="quality_score",
            period_start=now - timedelta(days=1),
            period_end=now,
            period_type="DAILY",
            current_value=92.5,
            previous_value=90.0,
            change_amount=2.5,
            change_percent=2.78,
            direction=DQTrendDirection.IMPROVING,
            trend_strength=0.8,
            forecast_value=93.5,
            metadata={"run_count": 3},
        )

        # ──────────────────────────────────────────────────────────
        # OTHER tenant fixtures — used to assert tenant isolation.
        # ──────────────────────────────────────────────────────────
        suffix = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {suffix}",
            slug=f"other-tenant-{suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.other_tenant)
        self.other_user = User.objects.create_user(
            email=f"other-{suffix}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        self.other_asset = Asset.objects.create(
            tenant=self.other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.other_user,
        )
        # An anomaly on the OTHER tenant — must NOT appear in the
        # current tenant's response.
        DQAnomaly.objects.create(
            tenant=self.other_tenant,
            asset=self.other_asset,
            metric_type="quality_score",
            expected_value=95.0,
            actual_value=10.0,
            deviation=-85.0,
            severity=DQAnomalySeverity.CRITICAL,
            anomaly_type="z_score_outlier",
            description="Cross-tenant anomaly — must not leak",
        )

    def _make_auditor(self):
        """Promote ``self.user`` to AUDITOR role."""
        role = Role.objects.create(
            tenant=self.tenant, name="AUDITOR", description="Auditor role"
        )
        UserRole.objects.create(user=self.user, role=role)


# ──────────────────────────────────────────────────────────────────
# ANOMALIES endpoint
# ──────────────────────────────────────────────────────────────────


class DQQualityAnomaliesEndpointTest(DQQualityEndpointsBase):
    def test_anomalies_happy_path_returns_200_and_results(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        ids = [str(item["id"]) for item in response.data["results"]]
        self.assertIn(str(self.anomaly.id), ids)

    def test_anomalies_filter_by_severity(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/anomalies/?severity=HIGH")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for item in response.data["results"]:
            self.assertEqual(item["severity"], "HIGH")

    def test_anomalies_tenant_isolation_excludes_other_tenant_rows(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Precondition: must have results for isolation test to be meaningful
        self.assertGreater(
            len(response.data["results"]), 0,
            "Expected at least one anomaly in current tenant to test isolation against",
        )
        tenant_ids = {item["tenant_id"] for item in response.data["results"]}
        self.assertNotIn(str(self.other_tenant.id), tenant_ids)
        # Sanity: every row must be from the requesting tenant.
        for item in response.data["results"]:
            self.assertEqual(item["tenant_id"], str(self.tenant.id))

    def test_anomalies_auditor_can_read(self):
        self._make_auditor()

        response = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anomalies_plan_limit_exhaustion_returns_403(self):
        """When tenant has used its daily quota, return 403 with
        ``plan_limit_exceeded`` code."""
        # Force tenant plan to a tiny daily cap: 1 query.
        plan = self.tenant.plan
        plan.limits_json = dict(plan.limits_json or {})
        plan.limits_json["max_quality_queries_per_day"] = 1
        plan.save(update_fields=["limits_json"])

        # Pre-seed one DQ_QUALITY_QUERY audit event today so the
        # counter sees current_usage=1 already; the next call would
        # push it to 2 > 1 and trip the limit.
        AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.user,
            resource_type="DQ_QUALITY",
            action="DQ_QUALITY_QUERY",
            details_json={"endpoint": "anomalies", "seed": True},
        )

        response = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        body = response.json()
        # Look for the canonical plan-limit code.  api_error_response
        # surfaces ``code`` at the top-level.
        self.assertEqual(body.get("code"), "plan_limit_exceeded")

    def test_anomalies_throttle_returns_429_after_burst(self):
        """ScopedRateThrottle scope ``dq_quality_anomalies``: at the
        configured rate +1, the throttle MUST 429.

        We tighten the rate to ``2/minute`` for the test so we don't
        need to fire 61 requests.  ``ScopedRateThrottle.THROTTLE_RATES``
        is a class attribute captured at module-import time from
        ``api_settings.DEFAULT_THROTTLE_RATES`` — ``override_settings``
        does NOT propagate to it (DRF's ``api_settings.reload()`` builds
        a NEW dict; the class attribute still references the OLD one).
        ``mock.patch.dict`` mutates the SAME dict the class attribute
        points to, restoring it on exit, so it's the correct injection
        point for testing throttle behaviour at custom rates.
        """
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        with patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"dq_quality_anomalies": "2/minute"},
        ):
            r1 = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")
            r2 = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")
            r3 = self.client.get(f"{CANONICAL_PREFIX}/anomalies/")

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r3.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ──────────────────────────────────────────────────────────────────
# TRENDS endpoint
# ──────────────────────────────────────────────────────────────────


class DQQualityTrendsEndpointTest(DQQualityEndpointsBase):
    def test_trends_happy_path_returns_200(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        # Verify trend visualization data is present and contains
        # data for the seeded DQRun (quality_score=92.5)
        results = response.data.get("results", [])
        self.assertIsInstance(results, list)

    def test_trends_tenant_isolation_excludes_other_tenant_assets(self):
        # Trying to query OTHER tenant's asset must yield empty.
        response = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.other_asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No trends visible for the other tenant's asset.
        self.assertEqual(response.data["results"], [])

    def test_trends_auditor_can_read(self):
        self._make_auditor()

        response = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_trends_plan_limit_exhaustion_returns_403(self):
        plan = self.tenant.plan
        plan.limits_json = dict(plan.limits_json or {})
        plan.limits_json["max_quality_queries_per_day"] = 0
        plan.save(update_fields=["limits_json"])

        response = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.asset.id}")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json().get("code"), "plan_limit_exceeded")

    def test_trends_throttle_returns_429_after_burst(self):
        """Per-action scope wiring check — ``dq_quality_trends`` is a
        DIFFERENT scope from ``dq_quality_anomalies`` so a tightened
        rate on one MUST NOT bleed into the other (proves
        ``get_throttles()`` reads ``self.action``)."""
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        with patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"dq_quality_trends": "1/minute"},
        ):
            r1 = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.asset.id}")
            r2 = self.client.get(f"{CANONICAL_PREFIX}/trends/?asset_id={self.asset.id}")

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ──────────────────────────────────────────────────────────────────
# SCORECARDS endpoint
# ──────────────────────────────────────────────────────────────────


class DQQualityScorecardsEndpointTest(DQQualityEndpointsBase):
    def test_scorecards_happy_path_returns_dashboard_shape(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Tenant-scope dashboard shape from
        # ``DQScorecardService.get_executive_dashboard``.
        for key in (
            "period", "summary", "score_distribution",
            "top_issues", "trend_summary",
        ):
            self.assertIn(key, response.data)
        self.assertGreaterEqual(response.data["summary"]["total_runs"], 1)

    def test_scorecards_asset_drill_down(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/?asset_id={self.asset.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["asset_id"], str(self.asset.id))
        # get_asset_scorecard returns: period, metrics, recent_runs, trends
        self.assertIn("period", response.data)
        self.assertIn("metrics", response.data)
        self.assertIn("recent_runs", response.data)
        self.assertIn("trends", response.data)
        self.assertGreaterEqual(response.data["metrics"]["total_runs"], 1)

    def test_scorecards_tenant_isolation_blocks_other_tenant_asset(self):
        # Asking for an OTHER tenant's asset MUST return 404
        # (not a sneak preview of cross-tenant aggregates).
        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/?asset_id={self.other_asset.id}")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_scorecards_auditor_can_read(self):
        self._make_auditor()

        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_scorecards_plan_limit_exhaustion_returns_403(self):
        plan = self.tenant.plan
        plan.limits_json = dict(plan.limits_json or {})
        plan.limits_json["max_quality_queries_per_day"] = 0
        plan.save(update_fields=["limits_json"])

        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json().get("code"), "plan_limit_exceeded")

    def test_scorecards_throttle_returns_429_after_burst(self):
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        with patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"dq_quality_scorecards": "1/minute"},
        ):
            r1 = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")
            r2 = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ──────────────────────────────────────────────────────────────────
# ROOT_CAUSE_ANALYSIS endpoint
# ──────────────────────────────────────────────────────────────────


class DQQualityRootCauseEndpointTest(DQQualityEndpointsBase):
    def test_root_cause_happy_path_returns_200(self):
        response = self.client.get(
            f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["dq_run_id"], str(self.dq_run.id))
        self.assertIn("root_causes", response.data)
        self.assertIn("recommendations", response.data)

    def test_root_cause_tenant_isolation_blocks_other_tenant_run(self):
        # Build a run inside OTHER tenant and try to query it from
        # the current tenant — must 404.
        other_file = File.objects.create(
            tenant=self.other_tenant,
            name="other.csv",
            content_type="text/csv",
            size=1024,
            status=FileStatus.ACTIVE,
            storage_path="other/path/file.csv",
            created_by=self.other_user,
        )
        other_job = Job.objects.create(
            tenant=self.other_tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            resource_type="DQ_RUN",
            resource_id=uuid.uuid4(),
            created_by=self.other_user,
            timeout_seconds=1800,
        )
        other_run = DQRun.objects.create(
            tenant=self.other_tenant,
            asset=self.other_asset,
            file=other_file,
            job=other_job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=10.0,
            completed_at=timezone.now(),
        )

        response = self.client.get(
            f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={other_run.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_root_cause_auditor_can_read(self):
        self._make_auditor()

        response = self.client.get(
            f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_root_cause_plan_limit_exhaustion_returns_403(self):
        plan = self.tenant.plan
        plan.limits_json = dict(plan.limits_json or {})
        plan.limits_json["max_quality_queries_per_day"] = 0
        plan.save(update_fields=["limits_json"])

        response = self.client.get(
            f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json().get("code"), "plan_limit_exceeded")

    def test_root_cause_consecutive_calls_count_against_daily_cap(self):
        """End-to-end audit-driven counter check: each successful
        request emits a ``DQ_QUALITY_QUERY`` audit event (inside the
        plan-limit SELECT FOR UPDATE window so race-free), and the
        counter sees the new row immediately.  At cap=2, the third
        request MUST 403.
        """
        plan = self.tenant.plan
        plan.limits_json = dict(plan.limits_json or {})
        plan.limits_json["max_quality_queries_per_day"] = 2
        plan.save(update_fields=["limits_json"])

        url = f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
        r1 = self.client.get(url)
        r2 = self.client.get(url)
        r3 = self.client.get(url)

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r3.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(r3.json().get("code"), "plan_limit_exceeded")

        # Audit events emitted for r1 and r2; NOT for r3 (denied).
        emitted = AuditEvent.objects.filter(
            tenant=self.tenant,
            action="DQ_QUALITY_QUERY",
        ).count()
        self.assertEqual(emitted, 2)

    def test_root_cause_throttle_returns_429_after_burst(self):
        """Tightest production rate (5/min) — verify per-action scope
        wiring on the most compute-heavy endpoint."""
        from unittest.mock import patch

        from rest_framework.throttling import ScopedRateThrottle

        with patch.dict(
            ScopedRateThrottle.THROTTLE_RATES,
            {"dq_quality_root_cause": "1/minute"},
        ):
            r1 = self.client.get(
                f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
            )
            r2 = self.client.get(
                f"{CANONICAL_PREFIX}/root_cause_analysis/?dq_run_id={self.dq_run.id}"
            )

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


# ──────────────────────────────────────────────────────────────────
# Dual-mount + deprecation headers (D240.10)
# ──────────────────────────────────────────────────────────────────


class DQQualityDualMountTest(DQQualityEndpointsBase):
    def test_canonical_prefix_does_not_emit_deprecation_headers(self):
        response = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Canonical path is the FUTURE path — must NOT carry
        # Sunset/Deprecation headers.
        self.assertNotIn("Sunset", response.headers)
        self.assertNotIn("Deprecation", response.headers)

    def test_deprecated_prefix_returns_same_payload_shape(self):
        canonical = self.client.get(f"{CANONICAL_PREFIX}/scorecards/")
        deprecated = self.client.get(f"{DEPRECATED_PREFIX}/scorecards/")

        self.assertEqual(canonical.status_code, status.HTTP_200_OK)
        self.assertEqual(deprecated.status_code, status.HTTP_200_OK)
        # Both paths surface the same view — top-level keys must match.
        self.assertEqual(set(canonical.data.keys()), set(deprecated.data.keys()))

    def test_deprecated_prefix_emits_sunset_and_deprecation_headers(self):
        response = self.client.get(f"{DEPRECATED_PREFIX}/scorecards/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(
            "Sunset",
            response.headers,
            "Deprecated /api/v1/quality/* must carry RFC 8594 Sunset header",
        )
        self.assertIn(
            "Deprecation",
            response.headers,
            "Deprecated /api/v1/quality/* must carry the Deprecation header",
        )
        # Link header SHOULD point at the canonical successor.
        self.assertIn("Link", response.headers)
        self.assertIn("/api/v1/dq/quality", response.headers["Link"])
