"""
Detailed field mapping tests for the DQ results endpoint.

Verifies category grouping, message resolution (top-level vs details fallback),
severity mapping, trend analysis fields, and empty-checks edge case.
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus, DQTrend
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestDQResultsFieldMapping(DQAPITestBase):
    """Detailed field mapping tests for GET /api/v1/dq/runs/{id}/results/."""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _create_run(self, **overrides):
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={},
            timeout_seconds=300,
            executed_by_prefect=True,
        )
        defaults = {
            "tenant": self.tenant,
            "asset": self.asset,
            "job": job,
            "status": DQRunStatus.SUCCEEDED,
            "overall_status": "PASS",
            "quality_score": 100.0,
            "checks_json": [],
            "details_json": {},
            "profile_key": "intake_basic_gx",
            "engine": DQEngine.GREAT_EXPECTATIONS,
            "started_at": timezone.now(),
            "completed_at": timezone.now(),
        }
        defaults.update(overrides)
        return DQRun.objects.create(**defaults)

    def _get_results(self, run_id):
        return self.client.get(f"/api/v1/dq/runs/{run_id}/results/")

    # ------------------------------------------------------------------
    # 1. Category grouping: COMPLETENESS + VALIDITY
    # ------------------------------------------------------------------
    def test_category_grouping_completeness_validity(self):
        """Mix of COMPLETENESS and VALIDITY checks yields correct by_category keys and counts."""
        checks = [
            {"category": "COMPLETENESS", "status": "PASS", "name": "not_null"},
            {"category": "COMPLETENESS", "status": "FAIL", "name": "not_empty"},
            {"category": "VALIDITY", "status": "PASS", "name": "regex_match"},
        ]
        run = self._create_run(checks_json=checks, quality_score=66.7)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        by_cat = resp.data["score_breakdown"]["by_category"]
        self.assertIn("COMPLETENESS", by_cat)
        self.assertIn("VALIDITY", by_cat)
        self.assertEqual(by_cat["COMPLETENESS"]["total"], 2)
        self.assertEqual(by_cat["COMPLETENESS"]["passed"], 1)
        self.assertEqual(by_cat["COMPLETENESS"]["failed"], 1)
        self.assertEqual(by_cat["VALIDITY"]["total"], 1)
        self.assertEqual(by_cat["VALIDITY"]["passed"], 1)

    # ------------------------------------------------------------------
    # 2. Message from top-level 'message' key
    # ------------------------------------------------------------------
    def test_message_from_top_level(self):
        """Top-level 'message' on the check is used as the recommendation issue."""
        checks = [
            {
                "message": "Column x: 3 nulls",
                "status": "FAIL",
                "name": "null_check",
                "category": "COMPLETENESS",
            },
        ]
        run = self._create_run(checks_json=checks, overall_status="FAIL", quality_score=0.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["recommendations"][0]["issue"], "Column x: 3 nulls")

    # ------------------------------------------------------------------
    # 3. Message fallback to details.message
    # ------------------------------------------------------------------
    def test_message_fallback_to_details(self):
        """When top-level message is absent, details.message is used as fallback."""
        checks = [
            {
                "details": {"message": "fallback msg"},
                "status": "FAIL",
                "name": "range_check",
                "category": "VALIDITY",
            },
        ]
        run = self._create_run(checks_json=checks, overall_status="FAIL", quality_score=0.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["recommendations"][0]["issue"], "fallback msg")

    # ------------------------------------------------------------------
    # 4. Severity mapping: FAIL→HIGH, WARN→MEDIUM, PASS→LOW
    # ------------------------------------------------------------------
    def test_severity_mapping(self):
        """check_details severity: FAIL→HIGH, WARN→MEDIUM, PASS→LOW."""
        checks = [
            {"name": "fail_check", "status": "FAIL", "category": "COMPLETENESS"},
            {"name": "warn_check", "status": "WARN", "category": "VALIDITY"},
            {"name": "pass_check", "status": "PASS", "category": "COMPLETENESS"},
        ]
        run = self._create_run(checks_json=checks, quality_score=33.3)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        details_by_name = {d["name"]: d for d in resp.data["check_details"]}
        self.assertEqual(details_by_name["fail_check"]["severity"], "HIGH")
        self.assertEqual(details_by_name["warn_check"]["severity"], "MEDIUM")
        self.assertEqual(details_by_name["pass_check"]["severity"], "LOW")

    # ------------------------------------------------------------------
    # 5. Trend analysis uses correct fields
    # ------------------------------------------------------------------
    def test_trend_analysis_uses_correct_fields(self):
        """DQTrend with change_percent=5.0 and 30-day period → correct response fields."""
        now = timezone.now()
        DQTrend.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            metric_type="quality_score",
            period_start=now - timedelta(days=30),
            period_end=now,
            period_type="MONTHLY",
            current_value=85.0,
            previous_value=80.0,
            change_amount=5.0,
            change_percent=5.0,
            direction="IMPROVING",
        )

        run = self._create_run(quality_score=85.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        trend = resp.data["trend_analysis"]
        self.assertIsNotNone(trend)
        self.assertEqual(trend["change_percentage"], 5.0)
        self.assertEqual(trend["period_days"], 30)
        self.assertEqual(trend["direction"], "IMPROVING")

    # ------------------------------------------------------------------
    # 6. Empty checks → zero counts
    # ------------------------------------------------------------------
    def test_empty_checks_zero_counts(self):
        """checks_json=[] → passed_checks=0, failed_checks=0."""
        run = self._create_run(checks_json=[])
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        breakdown = resp.data["score_breakdown"]
        self.assertEqual(breakdown["passed_checks"], 0)
        self.assertEqual(breakdown["failed_checks"], 0)
