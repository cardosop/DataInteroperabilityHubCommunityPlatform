"""
Tests for the compliance results endpoint detailed field mapping.

Validates score breakdown math, severity thresholds, remediation generation,
risk assessment severity counts, and metering risk_score passthrough.
"""
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class ResultsEndpointDetailedTest(TestCase):
    """Detailed tests for GET /api/v1/compliance/runs/{id}/results/"""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"asset-{uid}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _create_job(self):
        return create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(uuid.uuid4()),
            details_json={"scan_mode": "internal"},
            timeout_seconds=300,
            executed_by_prefect=True,
        )

    def _create_run(self, **overrides):
        defaults = {
            "tenant": self.tenant,
            "asset": self.asset,
            "job": self._create_job(),
            "status": ComplianceRunStatus.SUCCEEDED,
            "overall_status": "PASS",
            "risk_level": "NONE",
            "allowed_to_store": True,
            "column_findings_json": [],
            "detected_categories_json": [],
            "regulation_mapping_json": {},
            "regulations": [],
            "started_at": timezone.now(),
            "completed_at": timezone.now(),
        }
        defaults.update(overrides)
        return ComplianceRun.objects.create(**defaults)

    def _get_results(self, run):
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return resp.data

    # ----------------------------------------------------------------
    # 1. Multiple columns, correct violation count
    # ----------------------------------------------------------------

    def test_multiple_columns_correct_violation_count(self):
        """3 columns with 2 PII types each produce 6 violations."""
        findings = [
            {
                "column": f"col_{i}",
                "categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                "match_ratio": 0.8,
            }
            for i in range(3)
        ]
        run = self._create_run(column_findings_json=findings)
        data = self._get_results(run)

        self.assertEqual(len(data["violations"]), 6)

    # ----------------------------------------------------------------
    # 2. Score breakdown math
    # ----------------------------------------------------------------

    def test_score_breakdown_math(self):
        """5 column findings, 2 with categories: rate=0.4, penalty=20, score=80."""
        findings = [
            {"column": "email", "categories": ["PII_DIRECT_EMAIL"], "match_ratio": 0.9},
            {"column": "phone", "categories": ["PII_DIRECT_PHONE"], "match_ratio": 0.7},
            {"column": "id", "categories": [], "match_ratio": 0.0},
            {"column": "name", "categories": [], "match_ratio": 0.0},
            {"column": "status", "categories": [], "match_ratio": 0.0},
        ]
        run = self._create_run(column_findings_json=findings)
        data = self._get_results(run)

        breakdown = data["score_breakdown"]
        self.assertEqual(breakdown["total_columns"], 5)
        self.assertEqual(breakdown["columns_with_pii"], 2)
        self.assertAlmostEqual(breakdown["pii_detection_rate"], 0.4)
        self.assertAlmostEqual(breakdown["pii_penalty"], 20.0)
        self.assertAlmostEqual(breakdown["final_score"], 80.0)

    # ----------------------------------------------------------------
    # 3. Severity thresholds
    # ----------------------------------------------------------------

    def test_severity_thresholds(self):
        """match_ratio > 0.7 -> HIGH, > 0.4 -> MEDIUM, else LOW."""
        findings = [
            {"column": "col_high", "categories": ["PII_DIRECT_EMAIL"], "match_ratio": 0.8},
            {"column": "col_med", "categories": ["PII_DIRECT_PHONE"], "match_ratio": 0.5},
            {"column": "col_low", "categories": ["PII_DIRECT_SSN"], "match_ratio": 0.2},
        ]
        run = self._create_run(column_findings_json=findings)
        data = self._get_results(run)

        violations = data["violations"]
        severity_by_col = {v["column"]: v["severity"] for v in violations}
        self.assertEqual(severity_by_col["col_high"], "HIGH")
        self.assertEqual(severity_by_col["col_med"], "MEDIUM")
        self.assertEqual(severity_by_col["col_low"], "LOW")

    # ----------------------------------------------------------------
    # 4. Remediation for SSN
    # ----------------------------------------------------------------

    def test_remediation_for_ssn(self):
        """Finding with PII_DIRECT_SSN produces a remediation suggestion."""
        findings = [
            {"column": "ssn_col", "categories": ["PII_DIRECT_SSN"], "match_ratio": 0.9},
        ]
        run = self._create_run(column_findings_json=findings)
        data = self._get_results(run)

        suggestions = data["remediation_suggestions"]
        self.assertGreater(len(suggestions), 0)
        self.assertEqual(suggestions[0]["pii_type"], "PII_DIRECT_SSN")
        self.assertIn("ssn_col", suggestions[0]["suggestion"])

    # ----------------------------------------------------------------
    # 5. Risk assessment severity counts
    # ----------------------------------------------------------------

    def test_risk_assessment_severity_counts(self):
        """Mix of HIGH/MEDIUM/LOW violations yields correct severity counts."""
        findings = [
            {"column": "c1", "categories": ["PII_DIRECT_EMAIL"], "match_ratio": 0.9},   # HIGH
            {"column": "c2", "categories": ["PII_DIRECT_PHONE"], "match_ratio": 0.8},   # HIGH
            {"column": "c3", "categories": ["PII_DIRECT_SSN"], "match_ratio": 0.5},     # MEDIUM
            {"column": "c4", "categories": ["LOCATION_PRECISE"], "match_ratio": 0.2},   # LOW
        ]
        run = self._create_run(column_findings_json=findings)
        data = self._get_results(run)

        ra = data["risk_assessment"]
        self.assertEqual(ra["high_severity_violations"], 2)
        self.assertEqual(ra["medium_severity_violations"], 1)
        self.assertEqual(ra["low_severity_violations"], 1)
        self.assertEqual(ra["total_violations"], 4)

    # ----------------------------------------------------------------
    # 6. Risk assessment uses metering risk_score
    # ----------------------------------------------------------------

    def test_risk_assessment_uses_metering_risk_score(self):
        """risk_assessment.risk_score comes from metering.risk_score in regulation_mapping_json."""
        run = self._create_run(
            regulation_mapping_json={
                "metering": {"risk_score": 42.5},
            }
        )
        data = self._get_results(run)

        self.assertEqual(data["risk_assessment"]["risk_score"], 42.5)
