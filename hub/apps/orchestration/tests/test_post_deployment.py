"""
Tests for post-deployment metrics collector and report (Task 5.3).

Uses real DB and workflow instances; no mocks.
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.models import (
    StepStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from hub.apps.orchestration.post_deployment import (
    PostDeploymentMetricsCollector,
    PostDeploymentReport,
    _is_validation_failure,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


class PostDeploymentValidationFailureHelperTests(TestCase):
    """Test _is_validation_failure helper."""

    def test_validation_in_error_message(self):
        self.assertTrue(_is_validation_failure("Validation failed for step", None))

    def test_workflow_execution_error(self):
        self.assertTrue(_is_validation_failure("WorkflowExecutionError: validate_workflow", None))

    def test_business_rules_in_message(self):
        self.assertTrue(_is_validation_failure("business rules validation failed", None))

    def test_validation_in_error_details_message(self):
        self.assertTrue(
            _is_validation_failure(None, {"error_message": "Step input validation failed"})
        )

    def test_validation_errors_key(self):
        self.assertTrue(_is_validation_failure(None, {"validation_errors": ["err1"]}))

    def test_not_validation_failure(self):
        self.assertFalse(_is_validation_failure("Connection timeout", None))
        self.assertFalse(_is_validation_failure(None, {"error_message": "Network error"}))


class PostDeploymentMetricsCollectorTests(TestCase):
    """Integration tests for PostDeploymentMetricsCollector using real DB."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {self.uid}", slug=f"test-tenant-{self.uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"postdeploy-{self.uid}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        # Unique workflow name per test run to avoid stale data with --reuse-db
        self.wf_name = f"post_deploy_workflow_{self.uid}"
        self.workflow_def = WorkflowDefinition.objects.create(
            name=self.wf_name,
            version="1.0.0",
            dsl_json={
                "version": "1.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test.task"},
                ],
            },
            is_active=True,
        )
        self.now = timezone.now()
        self.window_minutes = 60
        self.window_start = self.now - timedelta(minutes=self.window_minutes)

    def _get_our_stats(self, report):
        """Get workflow stats for our unique workflow name, ignoring stale data."""
        return [ws for ws in report.workflow_stats if ws.workflow_name == self.wf_name]

    def test_collect_empty_window(self):
        """Collect with no activity in window returns no stats for our workflow."""
        collector = PostDeploymentMetricsCollector(time_window_minutes=self.window_minutes)
        report = collector.collect()
        self.assertIsInstance(report, PostDeploymentReport)
        self.assertEqual(report.window_minutes, self.window_minutes)
        # Filter to our unique workflow; stale workflows from --reuse-db may exist
        our_stats = self._get_our_stats(report)
        self.assertEqual(len(our_stats), 0)
        self.assertGreater(len(report.recommendations), 0)

    def test_collect_tracks_workflow_success_failure_rates(self):
        """Collect tracks workflow success/failure rates from DB (5.3.2)."""
        # Use started_at well inside the window (2+ min after start) so collector's
        # window boundary (computed at collect time) does not exclude any instance.
        base = self.window_start + timedelta(minutes=2)
        for i in range(3):
            WorkflowInstance.objects.create(
                workflow_definition=self.workflow_def,
                workflow_name=self.wf_name,
                workflow_version="1.0.0",
                tenant=self.tenant,
                status=WorkflowStatus.COMPLETED,
                started_at=base + timedelta(minutes=i * 3),
                completed_at=base + timedelta(minutes=i * 3, seconds=10),
            )
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.wf_name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            started_at=base + timedelta(minutes=9),
            completed_at=base + timedelta(minutes=9, seconds=5),
            error_message="Some error",
        )

        collector = PostDeploymentMetricsCollector(time_window_minutes=self.window_minutes)
        report = collector.collect()

        our_stats = self._get_our_stats(report)
        self.assertEqual(len(our_stats), 1)
        ws = our_stats[0]
        self.assertEqual(ws.workflow_name, self.wf_name)
        self.assertEqual(ws.started_count, 4)
        self.assertEqual(ws.completed_count, 3)
        self.assertEqual(ws.failed_count, 1)
        self.assertIsNotNone(ws.success_rate)
        self.assertEqual(ws.success_rate, Decimal("0.75"))
        self.assertEqual(ws.failure_rate, Decimal("0.25"))

    def test_collect_tracks_validation_failure_count(self):
        """Collect tracks validation-related failures (5.3.1)."""
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.wf_name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            started_at=self.window_start + timedelta(minutes=1),
            completed_at=self.window_start + timedelta(minutes=1, seconds=2),
            error_message="WorkflowExecutionError: validation failed",
            error_details={"validation_errors": ["step_input invalid"]},
        )
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.wf_name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            started_at=self.window_start + timedelta(minutes=2),
            completed_at=self.window_start + timedelta(minutes=2, seconds=1),
            error_message="Connection timeout",
        )

        collector = PostDeploymentMetricsCollector(time_window_minutes=self.window_minutes)
        report = collector.collect()

        our_stats = self._get_our_stats(report)
        self.assertEqual(len(our_stats), 1)
        ws = our_stats[0]
        self.assertEqual(ws.started_count, 2)
        self.assertEqual(ws.failed_count, 2)
        self.assertEqual(ws.validation_failure_count, 1)

    def test_recommendations_when_success_rate_below_target(self):
        """Recommendations include message when success rate below DoD-5.5 target."""
        # 1 completed, 2 failed -> success rate 1/3 < 0.95
        for i in range(2):
            WorkflowInstance.objects.create(
                workflow_definition=self.workflow_def,
                workflow_name=self.wf_name,
                workflow_version="1.0.0",
                tenant=self.tenant,
                status=WorkflowStatus.FAILED,
                started_at=self.window_start + timedelta(minutes=i),
                completed_at=self.window_start + timedelta(minutes=i, seconds=1),
            )
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name=self.wf_name,
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.COMPLETED,
            started_at=self.window_start + timedelta(minutes=5),
            completed_at=self.window_start + timedelta(minutes=5, seconds=10),
        )

        collector = PostDeploymentMetricsCollector(time_window_minutes=self.window_minutes)
        report = collector.collect()

        self.assertTrue(
            any(
                "success rate" in rec and self.wf_name in rec
                for rec in report.recommendations
            ),
            report.recommendations,
        )


class ReportWorkflowPostDeploymentMetricsCommandTests(TestCase):
    """Tests for report_workflow_post_deployment_metrics management command."""

    def setUp(self):
        self.uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Cmd Tenant {self.uid}", slug=f"cmd-tenant-{self.uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"cmd-{self.uid}@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.workflow_def = WorkflowDefinition.objects.create(
            name=f"cmd_workflow_{self.uid}",
            version="1.0.0",
            dsl_json={
                "version": "1.0",
                "steps": [{"name": "s1", "type": "task", "task": "t1"}],
            },
            is_active=True,
        )

    def test_command_exits_successfully(self):
        """Command runs without error (empty window)."""
        out = StringIO()
        call_command("report_workflow_post_deployment_metrics", "--window", "60", stdout=out)
        self.assertIn("Post-Deployment Metrics", out.getvalue())
        self.assertIn("Recommendations", out.getvalue())

    def test_command_json_output(self):
        """Command --json outputs valid JSON."""
        out = StringIO()
        call_command(
            "report_workflow_post_deployment_metrics",
            "--window",
            "60",
            "--json",
            stdout=out,
        )
        import json

        data = json.loads(out.getvalue())
        self.assertIn("window_minutes", data)
        self.assertIn("workflow_stats", data)
        self.assertIn("step_stats", data)
        self.assertIn("recommendations", data)
        self.assertEqual(data["window_minutes"], 60)
