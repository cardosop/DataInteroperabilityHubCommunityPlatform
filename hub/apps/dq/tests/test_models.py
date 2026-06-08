"""
Unit tests for DQ models: DQRun, DQAnomaly, DQAlertingRule.

Tests cover:
- Model creation (success scenarios)
- Model validation (failure scenarios)
- Edge cases (missing fields, invalid values)
- Error handling (constraint violations)
- Encryption logic (DQAlertingRule.channel_config)
"""

import pytest
from django.core.exceptions import ValidationError

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.dq.models import (
    DQAlertChannel,
    DQAlertingRule,
    DQAnomaly,
    DQAnomalySeverity,
    DQEngine,
    DQRun,
    DQRunStatus,
)
from hub.apps.dq.tests.test_base import DQTestBase
from hub.apps.jobs.models import Job, JobStatus, JobType

pytestmark = pytest.mark.django_db(transaction=True)


class DQRunModelTest(DQTestBase):
    """Test DQRun model"""

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

    def test_create_dq_run_success(self):
        """Test DQ run creation with valid data"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            job=self.job,
            file=self.file,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.tenant, self.tenant)
        self.assertEqual(dq_run.asset, self.asset)
        self.assertEqual(dq_run.job, self.job)
        self.assertEqual(dq_run.file, self.file)
        self.assertEqual(dq_run.engine, DQEngine.GREAT_EXPECTATIONS)
        self.assertEqual(dq_run.profile_key, "intake_basic_gx")
        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

    def test_create_dq_run_with_dataset(self):
        """Test DQ run creation with dataset"""
        from hub.apps.datasets.models import Dataset

        dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            dataset=dataset,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.dataset, dataset)

    def test_create_dq_run_without_asset(self):
        """Test DQ run creation without asset (edge case)"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertIsNone(dq_run.asset)

    def test_dq_run_status_transitions(self):
        """Test DQ run status transitions"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        self.assertEqual(dq_run.status, DQRunStatus.PENDING)

        # Transition to RUNNING
        dq_run.status = DQRunStatus.RUNNING
        dq_run.save()
        self.assertEqual(dq_run.status, DQRunStatus.RUNNING)

        # Transition to SUCCEEDED
        dq_run.status = DQRunStatus.SUCCEEDED
        dq_run.overall_status = "PASS"
        dq_run.quality_score = 95.5
        dq_run.save()
        self.assertEqual(dq_run.status, DQRunStatus.SUCCEEDED)
        self.assertEqual(dq_run.overall_status, "PASS")
        self.assertEqual(dq_run.quality_score, 95.5)

    def test_dq_run_status_failure(self):
        """Test DQ run status failure scenario"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )

        # Transition to FAILED
        dq_run.status = DQRunStatus.FAILED
        dq_run.details_json = {"error": "Test error", "error_type": "ValueError"}
        dq_run.save()

        self.assertEqual(dq_run.status, DQRunStatus.FAILED)
        self.assertIn("error", dq_run.details_json)

    def test_dq_run_quality_score_range(self):
        """Test DQ run quality score range (edge case)"""
        dq_run = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=0.0,  # Minimum score
        )

        self.assertEqual(dq_run.quality_score, 0.0)

        dq_run.quality_score = 100.0  # Maximum score
        dq_run.save()
        self.assertEqual(dq_run.quality_score, 100.0)

    # ------------------------------------------------------------------
    # H6: DQRun overall_status mapping (moved from test_dq_result_structure.py)
    # ------------------------------------------------------------------
    def test_dq_result_overall_status_mapping(self):
        """DQRun overall_status values: PASS, FAIL, WARN."""
        dq_run_pass = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="PASS",
            quality_score=100.0,
        )
        dq_run_fail = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="FAIL",
            quality_score=50.0,
        )
        dq_run_warn = DQRun.objects.create(
            tenant=self.tenant,
            file=self.file,
            job=self.job,
            profile_key="intake_basic_gx",
            engine=DQEngine.GREAT_EXPECTATIONS,
            status=DQRunStatus.SUCCEEDED,
            overall_status="WARN",
            quality_score=80.0,
        )

        self.assertEqual(dq_run_pass.overall_status, "PASS")
        self.assertEqual(dq_run_fail.overall_status, "FAIL")
        self.assertEqual(dq_run_warn.overall_status, "WARN")

    # ------------------------------------------------------------------
    # C7: DQRun.clean() validation — at least one of asset/dataset/file
    # ------------------------------------------------------------------
    def test_clean_requires_asset_or_dataset_or_file(self):
        """DQRun.clean() raises ValidationError when all three are None."""
        dq_run = DQRun(
            tenant=self.tenant,
            job=self.job,
            asset=None,
            dataset=None,
            file=None,
            engine=DQEngine.GREAT_EXPECTATIONS,
            profile_key="intake_basic_gx",
            status=DQRunStatus.PENDING,
        )
        with self.assertRaises(ValidationError) as ctx:
            dq_run.clean()
        self.assertIn("asset", str(ctx.exception).lower())


# ------------------------------------------------------------------
# C7: DQAnomaly model tests (previously untested)
# ------------------------------------------------------------------
class DQAnomalyModelTest(DQTestBase):
    """Test DQAnomaly model"""

    def setUp(self):
        super().setUp()
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-anomaly",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_create_dq_anomaly_success(self):
        """DQAnomaly creation with valid fields."""
        anomaly = DQAnomaly.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            metric_type="quality_score",
            actual_value=40.0,
            expected_value=90.0,
            deviation=50.0,
            severity=DQAnomalySeverity.HIGH,
            anomaly_type="sudden_drop",
            description="Quality score dropped from 90 to 40",
        )
        self.assertEqual(anomaly.metric_type, "quality_score")
        self.assertEqual(anomaly.actual_value, 40.0)
        self.assertEqual(anomaly.expected_value, 90.0)
        self.assertEqual(anomaly.deviation, 50.0)
        self.assertEqual(anomaly.severity, DQAnomalySeverity.HIGH)
        self.assertEqual(anomaly.anomaly_type, "sudden_drop")
        self.assertFalse(anomaly.acknowledged)

    def test_create_dq_anomaly_minimal_fields(self):
        """DQAnomaly creation with only required fields."""
        anomaly = DQAnomaly.objects.create(
            tenant=self.tenant,
            metric_type="completeness",
            actual_value=0.75,
            deviation=0.25,
        )
        self.assertEqual(anomaly.tenant, self.tenant)
        self.assertEqual(anomaly.metric_type, "completeness")
        self.assertEqual(anomaly.actual_value, 0.75)
        self.assertEqual(anomaly.deviation, 0.25)
        self.assertIsNone(anomaly.asset)
        self.assertEqual(anomaly.severity, DQAnomalySeverity.MEDIUM)

    def test_dq_anomaly_defaults(self):
        """DQAnomaly defaults: severity=MEDIUM, acknowledged=False."""
        anomaly = DQAnomaly.objects.create(
            tenant=self.tenant,
            metric_type="accuracy",
            actual_value=80.0,
            deviation=20.0,
        )
        self.assertEqual(anomaly.severity, DQAnomalySeverity.MEDIUM)
        self.assertFalse(anomaly.acknowledged)
        self.assertEqual(anomaly.metadata, {})
        self.assertIsNotNone(anomaly.detected_at)


# ------------------------------------------------------------------
# C7: DQAlertingRule model tests (previously untested, has
#     encryption logic in save())
# ------------------------------------------------------------------
class DQAlertingRuleModelTest(DQTestBase):
    """Test DQAlertingRule model including channel_config encryption."""

    def setUp(self):
        super().setUp()

    def test_create_alerting_rule_email_channel(self):
        """DQAlertingRule with EMAIL channel validates and saves."""
        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            name="Quality score below 80%",
            metric_type="quality_score",
            threshold=80.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.HIGH,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={"emails": ["alerts@example.com"]},
            enabled=True,
        )
        self.assertEqual(rule.name, "Quality score below 80%")
        self.assertEqual(rule.metric_type, "quality_score")
        self.assertEqual(rule.threshold, 80.0)
        self.assertTrue(rule.enabled)
        # channel_config should be encrypted after save.
        self.assertIsNotNone(rule.channel_config)
        self.assertIn("_encrypted", rule.channel_config)
        # get_channel_config() decrypts back.
        decrypted = rule.get_channel_config()
        self.assertEqual(decrypted["emails"], ["alerts@example.com"])

    def test_create_alerting_rule_slack_channel(self):
        """DQAlertingRule with SLACK channel saves correctly."""
        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            name="Completeness alert",
            metric_type="completeness",
            threshold=0.95,
            comparison_operator="<=",
            severity=DQAnomalySeverity.CRITICAL,
            alert_channels=[DQAlertChannel.SLACK],
            channel_config={"webhook_url": "https://hooks.slack.com/x"},
        )
        self.assertEqual(len(rule.alert_channels), 1)
        self.assertEqual(rule.alert_channels[0], DQAlertChannel.SLACK)
        decrypted = rule.get_channel_config()
        self.assertEqual(decrypted["webhook_url"], "https://hooks.slack.com/x")

    def test_alerting_rule_requires_at_least_one_channel(self):
        """DQAlertingRule.clean() raises ValidationError with no channels."""
        rule = DQAlertingRule(
            tenant=self.tenant,
            name="No channels rule",
            metric_type="quality_score",
            threshold=70.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.MEDIUM,
            alert_channels=[],  # empty
        )
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_alerting_rule_email_requires_emails_config(self):
        """EMAIL channel without 'emails' in channel_config → ValidationError."""
        rule = DQAlertingRule(
            tenant=self.tenant,
            name="Bad email rule",
            metric_type="quality_score",
            threshold=70.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.MEDIUM,
            alert_channels=[DQAlertChannel.EMAIL],
            channel_config={"wrong_key": "value"},
        )
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_alerting_rule_webhook_requires_url_config(self):
        """WEBHOOK channel without 'url' in channel_config → ValidationError."""
        rule = DQAlertingRule(
            tenant=self.tenant,
            name="Bad webhook rule",
            metric_type="quality_score",
            threshold=70.0,
            comparison_operator="<",
            severity=DQAnomalySeverity.MEDIUM,
            alert_channels=[DQAlertChannel.WEBHOOK],
            channel_config={"wrong_key": "value"},
        )
        with self.assertRaises(ValidationError):
            rule.full_clean()

    def test_alerting_rule_disabled(self):
        """DQAlertingRule can be created with enabled=False."""
        rule = DQAlertingRule.objects.create(
            tenant=self.tenant,
            name="Disabled rule",
            metric_type="accuracy",
            threshold=0.9,
            comparison_operator="<",
            severity=DQAnomalySeverity.LOW,
            alert_channels=[DQAlertChannel.SLACK],
            enabled=False,
        )
        self.assertFalse(rule.enabled)
