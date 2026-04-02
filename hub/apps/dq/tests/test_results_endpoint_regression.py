"""
Tests for the DQ results endpoint field mapping fixes (bugs DQ-1 through DQ-6).

Verifies that the GET /api/v1/dq/runs/{id}/results/ endpoint correctly maps
checks_json fields to the response payload: category grouping, recommendation
messages, check_details, and quality_score passthrough.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
from hub.apps.dq.tests.test_base import DQAPITestBase
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.jobs.utils import create_job
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TestResultsEndpointRegression(DQAPITestBase):
    """Regression tests for DQ results endpoint field mapping (DQ-1 .. DQ-6)."""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
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
        url = f"/api/v1/dq/runs/{run_id}/results/"
        return self.client.get(url)

    # ------------------------------------------------------------------
    # DQ-1: by_category must use the 'category' field from checks_json
    # ------------------------------------------------------------------
    def test_by_category_uses_category_field(self):
        """by_category groups on 'category', not on 'type'."""
        run = self._create_run(
            checks_json=[
                {"category": "COMPLETENESS", "status": "PASS", "name": "not_null_check"},
            ],
        )
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_cat = resp.data["score_breakdown"]["by_category"]
        self.assertIn("COMPLETENESS", by_cat)
        self.assertNotIn("unknown", by_cat)

    # ------------------------------------------------------------------
    # DQ-2: by_category counts per category
    # ------------------------------------------------------------------
    def test_by_category_groups_multiple(self):
        """3 COMPLETENESS + 2 VALIDITY checks yield correct counts."""
        checks = [
            {"category": "COMPLETENESS", "status": "PASS", "name": f"c{i}"}
            for i in range(3)
        ] + [
            {"category": "VALIDITY", "status": "FAIL", "name": f"v{i}"}
            for i in range(2)
        ]
        run = self._create_run(checks_json=checks, quality_score=60.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        by_cat = resp.data["score_breakdown"]["by_category"]
        self.assertEqual(by_cat["COMPLETENESS"]["total"], 3)
        self.assertEqual(by_cat["COMPLETENESS"]["passed"], 3)
        self.assertEqual(by_cat["VALIDITY"]["total"], 2)
        self.assertEqual(by_cat["VALIDITY"]["failed"], 2)

    # ------------------------------------------------------------------
    # DQ-3: recommendations carry the check-level message
    # ------------------------------------------------------------------
    def test_recommendations_have_message(self):
        """Failed check message propagates to recommendations[].issue."""
        run = self._create_run(
            checks_json=[
                {
                    "status": "FAIL",
                    "name": "null check",
                    "message": "3 null values",
                    "category": "COMPLETENESS",
                },
            ],
            quality_score=0.0,
            overall_status="FAIL",
        )
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        recs = resp.data["recommendations"]
        self.assertEqual(len(recs), 1)
        self.assertIn("3 null values", recs[0]["issue"])

    # ------------------------------------------------------------------
    # DQ-4: recommendations use category, not a hardcoded 'unknown'
    # ------------------------------------------------------------------
    def test_recommendations_use_category_not_type(self):
        """recommendation['check_type'] should be 'COMPLETENESS', not 'unknown'."""
        run = self._create_run(
            checks_json=[
                {
                    "status": "FAIL",
                    "name": "null check",
                    "message": "nulls found",
                    "category": "COMPLETENESS",
                },
            ],
            quality_score=0.0,
            overall_status="FAIL",
        )
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        rec = resp.data["recommendations"][0]
        self.assertEqual(rec["check_type"], "COMPLETENESS")

    # ------------------------------------------------------------------
    # DQ-5: empty checks_json yields clean response
    # ------------------------------------------------------------------
    def test_empty_checks_clean_response(self):
        """Empty checks_json → zero counts, zero recommendations."""
        run = self._create_run(checks_json=[], quality_score=100.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        breakdown = resp.data["score_breakdown"]
        self.assertEqual(breakdown["passed_checks"], 0)
        self.assertEqual(breakdown["failed_checks"], 0)
        self.assertEqual(len(resp.data["recommendations"]), 0)

    # ------------------------------------------------------------------
    # DQ-6: check_details reads 'details' key from each check
    # ------------------------------------------------------------------
    def test_check_details_reads_details_key(self):
        """check_details[0]['result'] surfaces the 'details' sub-dict."""
        run = self._create_run(
            checks_json=[
                {
                    "name": "null check",
                    "status": "FAIL",
                    "category": "COMPLETENESS",
                    "details": {"null_count": 5},
                },
            ],
            quality_score=80.0,
            overall_status="FAIL",
        )
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        detail = resp.data["check_details"][0]
        self.assertEqual(detail["result"]["null_count"], 5)

    # ------------------------------------------------------------------
    # quality_score passthrough
    # ------------------------------------------------------------------
    def test_quality_score_passthrough(self):
        """quality_score stored on the model is returned verbatim."""
        run = self._create_run(quality_score=85.5)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["quality_score"], 85.5)

    # ------------------------------------------------------------------
    # Overall status passthrough
    # ------------------------------------------------------------------
    def test_overall_status_passthrough(self):
        """overall_status stored on the model is returned verbatim."""
        run = self._create_run(overall_status="WARN", quality_score=70.0)
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["overall_status"], "WARN")

    # ------------------------------------------------------------------
    # Engine type passthrough
    # ------------------------------------------------------------------
    def test_engine_type_passthrough(self):
        """engine field is returned as engine_type in the response."""
        run = self._create_run()
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["engine_type"], DQEngine.GREAT_EXPECTATIONS)

    # ------------------------------------------------------------------
    # Profile key passthrough
    # ------------------------------------------------------------------
    def test_profile_key_passthrough(self):
        """profile_key is returned in the response."""
        run = self._create_run(profile_key="intake_basic_gx")
        resp = self._get_results(run.id)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["profile_key"], "intake_basic_gx")
