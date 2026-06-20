"""
Regression tests for compliance results endpoint field mapping.

Validates fixes for:
- Bug 2: Hub reading wrong field names (column_name→column, pii_types→categories)
- Bug 4: Recommendations based on risk_level string alone
- Bug 8: columns_with_pii using wrong field name
- Bug 9: Remediation checking short names instead of PIICategory values
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

pytestmark = pytest.mark.django_db(transaction=True)

from django.contrib.auth import get_user_model

User = get_user_model()


class ResultsEndpointRegressionTest(TestCase):
    """Regression tests for /api/v1/compliance/runs/{id}/results/"""

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
        job = self._create_job()
        defaults = {
            "tenant": self.tenant,
            "asset": self.asset,
            "job": job,
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

    # ----------------------------------------------------------------
    # Bug 2: Field name mapping (column, categories, match_ratio)
    # ----------------------------------------------------------------

    def test_uses_column_field_not_column_name(self):
        """Results endpoint reads 'column' from compliance service findings."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email_addr",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                    "confidence": "HIGH",
                    "sample_matches": 90,
                    "total_sampled": 100,
                }
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        violations = resp.data["violations"]
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0]["column"], "email_addr")

    def test_uses_categories_field_not_pii_types(self):
        """Results endpoint reads 'categories' from compliance service findings."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                    "confidence": "HIGH",
                    "sample_matches": 90,
                    "total_sampled": 100,
                }
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        violations = resp.data["violations"]
        self.assertEqual(violations[0]["pii_type"], "PII_DIRECT_EMAIL")

    def test_violations_count_nonzero_with_findings(self):
        """Findings with PII produce violations."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                    "match_ratio": 0.5,
                    "confidence": "MEDIUM",
                    "sample_matches": 50,
                    "total_sampled": 100,
                }
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        violations = resp.data["violations"]
        # Two PII types in one column → 2 violations
        self.assertEqual(len(violations), 2)

    # ----------------------------------------------------------------
    # Bug 8: columns_with_pii uses wrong field name
    # ----------------------------------------------------------------

    def test_columns_with_pii_uses_categories(self):
        """Score breakdown correctly counts PII columns using 'categories' key."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                    "confidence": "HIGH",
                    "sample_matches": 90,
                    "total_sampled": 100,
                },
                {
                    "column": "name",
                    "categories": [],
                    "match_ratio": 0.0,
                    "confidence": "LOW",
                    "sample_matches": 0,
                    "total_sampled": 100,
                },
                {
                    "column": "phone",
                    "categories": ["PII_DIRECT_PHONE"],
                    "match_ratio": 0.6,
                    "confidence": "MEDIUM",
                    "sample_matches": 60,
                    "total_sampled": 100,
                },
                {
                    "column": "id",
                    "categories": [],
                    "match_ratio": 0.0,
                    "confidence": "LOW",
                    "sample_matches": 0,
                    "total_sampled": 100,
                },
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        breakdown = resp.data["score_breakdown"]
        self.assertEqual(breakdown["columns_with_pii"], 2)
        self.assertEqual(breakdown["columns_without_pii"], 2)
        self.assertAlmostEqual(breakdown["pii_detection_rate"], 0.5)
        self.assertLess(resp.data["compliance_score"], 100.0)

    def test_compliance_score_penalized_with_pii(self):
        """Compliance score < 100 when PII columns exist."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                    "confidence": "HIGH",
                    "sample_matches": 90,
                    "total_sampled": 100,
                },
                {
                    "column": "name",
                    "categories": [],
                    "match_ratio": 0.0,
                    "confidence": "LOW",
                    "sample_matches": 0,
                    "total_sampled": 100,
                },
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        # 1 PII column out of 2 → 50% → penalty = 25 → score = 75
        self.assertEqual(resp.data["compliance_score"], 75.0)

    # ----------------------------------------------------------------
    # Bug 4: Recommendations based on actual violations
    # ----------------------------------------------------------------

    def test_no_pii_recommendation_when_zero_violations(self):
        """No 'high-risk PII' recommendation when zero violations."""
        run = self._create_run(
            risk_level="CRITICAL",
            overall_status="FAIL",
            column_findings_json=[],
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        recs = resp.data["risk_assessment"]["recommendations"]
        for rec in recs:
            self.assertNotIn("high-risk PII", rec)

    def test_policy_recommendation_when_fail_no_violations(self):
        """Policy violation recommendation when FAIL status but zero violations."""
        run = self._create_run(
            overall_status="FAIL",
            risk_level="NONE",
            column_findings_json=[],
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        recs = resp.data["risk_assessment"]["recommendations"]
        self.assertTrue(
            any("policy violation" in r.lower() or "policy fail" in r.lower() for r in recs),
            f"Expected policy-violation recommendation, got: {recs}",
        )

    # ----------------------------------------------------------------
    # Bug 9: Remediation using correct PIICategory values
    # ----------------------------------------------------------------

    def test_remediation_for_pii_direct_email(self):
        """Remediation generated for PII_DIRECT_EMAIL (not 'EMAIL')."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "email",
                    "categories": ["PII_DIRECT_EMAIL"],
                    "match_ratio": 0.9,
                    "confidence": "HIGH",
                    "sample_matches": 90,
                    "total_sampled": 100,
                },
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        suggestions = resp.data["remediation_suggestions"]
        self.assertGreater(len(suggestions), 0)
        self.assertEqual(suggestions[0]["pii_type"], "PII_DIRECT_EMAIL")

    def test_remediation_for_payment_card(self):
        """Remediation generated for PAYMENT_CARD (not 'CREDIT_CARD')."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "card",
                    "categories": ["PAYMENT_CARD"],
                    "match_ratio": 0.8,
                    "confidence": "HIGH",
                    "sample_matches": 80,
                    "total_sampled": 100,
                },
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        suggestions = resp.data["remediation_suggestions"]
        self.assertGreater(len(suggestions), 0)
        self.assertEqual(
            suggestions[0]["pii_type"],
            "PAYMENT_CARD",
            "Remediation must identify the PII type as PAYMENT_CARD",
        )

    def test_no_remediation_for_location(self):
        """No remediation for LOCATION_PRECISE (not in known remediation list)."""
        run = self._create_run(
            column_findings_json=[
                {
                    "column": "coords",
                    "categories": ["LOCATION_PRECISE"],
                    "match_ratio": 0.7,
                    "confidence": "HIGH",
                    "sample_matches": 70,
                    "total_sampled": 100,
                },
            ]
        )
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        suggestions = resp.data["remediation_suggestions"]
        self.assertEqual(len(suggestions), 0)

    def test_empty_findings_clean_response(self):
        """Empty findings produce clean response: 0 violations, score 100."""
        run = self._create_run(column_findings_json=[])
        resp = self.client.get(f"/api/v1/compliance/runs/{run.id}/results/")
        self.assertEqual(len(resp.data["violations"]), 0)
        self.assertEqual(resp.data["compliance_score"], 100.0)
        self.assertEqual(resp.data["score_breakdown"]["columns_with_pii"], 0)
