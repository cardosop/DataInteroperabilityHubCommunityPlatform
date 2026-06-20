"""
E2E tests for Governance Features

End-to-end tests for compliance reporting, ABAC, and data masking workflows.
"""

import pytest

pytestmark = pytest.mark.slow
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus, RiskLevel
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.abac import ABACEngine
from hub.apps.governance.classification import DataClassifier
from hub.apps.governance.data_masking import DataMasker
from hub.apps.governance.models import (
    AccessPolicy,
    ClassificationCategory,
    FieldAccessPolicy,
)
from hub.apps.governance.report_scheduler import ReportScheduler
from hub.apps.jobs.models import Job, JobStatus, JobType

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


class GovernanceE2ETest(E2ETestBase):
    """E2E tests for governance features"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            schema_json={
                "fields": [
                    {"name": "email", "data_type": "string", "sample_values": ["user@example.com"]},
                    {"name": "ssn", "data_type": "string", "sample_values": ["123-45-6789"]},
                    {"name": "name", "data_type": "string", "sample_values": ["John Doe"]},
                ]
            },
            format="CSV",
            version=1,
            created_by=self.user,
        )

        self.job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.COMPLIANCE_RUN.value,
            status=JobStatus.COMPLETED.value,
            resource_type="DATASET",
            resource_id=self.dataset.id,
            created_by=self.user,
        )

    def test_complete_governance_workflow(self):
        """Test complete governance workflow: classification -> ABAC -> masking -> reporting"""
        # Step 1: Classify dataset
        classifications = DataClassifier.classify_dataset(
            tenant_id=str(self.tenant.id),
            dataset_id=str(self.dataset.id),
            user_id=str(self.user.id),
        )

        self.assertGreater(len(classifications), 0)

        # Step 2: Create compliance run
        ComplianceRun.objects.create(
            tenant=self.tenant,
            dataset=self.dataset,
            job=self.job,
            regulations=["GDPR", "HIPAA"],
            status=ComplianceRunStatus.SUCCEEDED.value,
            overall_status="PASS",
            risk_level=RiskLevel.LOW.value,
            detected_categories_json={"EMAIL": 1, "SSN": 1},
            completed_at=timezone.now(),
        )

        # Step 3: Create ABAC policy
        access_policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Allow PII Access with Masking",
            conditions={"resource": {"classification": ClassificationCategory.PII.value}},
            effect="ALLOW",
            priority=100,
            created_by=self.user,
        )

        # Step 4: Create field-level policies with masking
        FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=access_policy,
            dataset=self.dataset,
            field_name="email",
            access_type="READ",
            masking_strategy="FORMAT_PRESERVING",
            masking_config={"show_last": 4},
        )

        FieldAccessPolicy.objects.create(
            tenant=self.tenant,
            access_policy=access_policy,
            dataset=self.dataset,
            field_name="ssn",
            access_type="READ",
            masking_strategy="FORMAT_PRESERVING",
            masking_config={"show_last": 4},
        )

        # Step 5: Evaluate access
        result = ABACEngine.evaluate_access(
            user_id=str(self.user.id),
            tenant_id=str(self.tenant.id),
            resource_type="DATASET",
            resource_id=str(self.dataset.id),
            access_type="READ",
            field_name="email",
        )

        self.assertTrue(result.allowed)
        self.assertTrue(result.masking_required)

        # Step 6: Mask data
        row = {"email": "user@example.com", "ssn": "123-45-6789", "name": "John Doe"}

        masked_row = DataMasker.mask_dataset_row(
            row=row,
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            access_type="READ",
        )

        # Verify masking changed the sensitive fields
        self.assertNotEqual(masked_row["email"], row["email"], "Email should be masked")
        self.assertNotEqual(masked_row["ssn"], row["ssn"], "SSN should be masked")
        self.assertEqual(masked_row["name"], row["name"], "Name should NOT be masked (no policy)")
        # Verify masked values are not empty — masking should produce redacted output
        self.assertTrue(len(masked_row["email"]) > 0, "Masked email should not be empty")
        self.assertTrue(len(masked_row["ssn"]) > 0, "Masked SSN should not be empty")

        # Step 7: Generate compliance report
        report = ReportScheduler.generate_and_save_report(
            tenant_id=str(self.tenant.id), regulation="GDPR", user_id=str(self.user.id)
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.regulation, "GDPR")
        self.assertIn("compliance_runs", report.report_data)
        self.assertIn("pii_detection", report.report_data)

    def test_scheduled_report_workflow(self):
        """Test scheduled report generation and email delivery"""
        # Schedule report
        scheduled_report = ReportScheduler.schedule_report(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            schedule_frequency="WEEKLY",
            email_recipients=["admin@example.com"],
            user_id=str(self.user.id),
        )

        self.assertTrue(scheduled_report.scheduled)
        self.assertEqual(scheduled_report.schedule_frequency, "WEEKLY")

        # Generate scheduled reports (would be called by cron/scheduler)
        results = ReportScheduler.generate_scheduled_reports()

        self.assertIn("generated", results)
        self.assertIn("emailed", results)
        # Verify at least one report was generated (our scheduled report should trigger)
        self.assertGreaterEqual(
            results["generated"], 1, "At least one scheduled report should be generated"
        )
