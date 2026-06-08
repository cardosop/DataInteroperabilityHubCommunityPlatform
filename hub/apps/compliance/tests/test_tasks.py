"""
Phase 86.5 — compliance/tasks.py tests.

Tests poll_compliance_job: terminal guard, timeout fail-closed,
service polling, and re-enqueue logic.
Patches at source modules since imports are inside the function body.
"""
import uuid
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

_MODELS = "hub.apps.compliance.models"
_CLIENT = "hub.apps.compliance.service_client"
_SVC = "hub.apps.compliance.services"


class PollComplianceJobTest(TestCase):

    def _make_run(self, status="RUNNING", job_id="remote-1",
                  started_at=None):
        run = MagicMock()
        run.id = uuid.uuid4()
        run.status = status
        run.metadata_json = {"job_id": job_id} if job_id else {}
        run.started_at = started_at or timezone.now()
        run.created_at = run.started_at
        run.risk_level = None
        run.allowed_to_store = None
        run.error_message = None
        run.regulation_mapping_json = None
        return run

    @patch("hub.apps.compliance.tasks._reenqueue")
    @patch(f"{_CLIENT}.ComplianceServiceClient")
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_completed_result_persisted(
        self, mock_qs, mock_client_cls, mock_reenq,
    ):
        run = self._make_run()
        mock_qs.select_related.return_value.get.return_value = run
        mock_client = MagicMock()
        mock_client.get_scan_result.return_value = {
            "status": "COMPLETED",
            "result": {"risk": "LOW"},
        }
        mock_client_cls.return_value = mock_client

        with patch(f"{_SVC}.ComplianceService") as mock_svc:
            from hub.apps.compliance.tasks import poll_compliance_job
            poll_compliance_job(str(run.id))
            mock_svc._persist_result.assert_called_once()

    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_terminal_status_exits_early(self, mock_qs):
        run = self._make_run(status="SUCCEEDED")
        mock_qs.select_related.return_value.get.return_value = run
        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))
        run.save.assert_not_called()

    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_missing_job_id_marks_failed(self, mock_qs):
        run = self._make_run(job_id=None)
        mock_qs.select_related.return_value.get.return_value = run
        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))
        run.save.assert_called_once()
        self.assertEqual(run.status, "FAILED")

    @override_settings(COMPLIANCE_POLL_MAX_SECONDS=0)
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_timeout_marks_failed_fail_closed(self, mock_qs):
        old = timezone.now() - timedelta(seconds=1)
        run = self._make_run(started_at=old)
        mock_qs.select_related.return_value.get.return_value = run
        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))
        self.assertEqual(run.status, "FAILED")
        self.assertEqual(run.risk_level, "UNKNOWN")
        self.assertFalse(run.allowed_to_store)

    @patch("hub.apps.compliance.tasks._reenqueue")
    @patch(f"{_CLIENT}.ComplianceServiceClient")
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_running_status_reenqueues(
        self, mock_qs, mock_client_cls, mock_reenq,
    ):
        run = self._make_run()
        mock_qs.select_related.return_value.get.return_value = run
        mock_client = MagicMock()
        mock_client.get_scan_result.return_value = {
            "status": "RUNNING",
        }
        mock_client_cls.return_value = mock_client
        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))
        mock_reenq.assert_called_once()

    # ----------------------------------------------------------------
    # Phase 213.G.6 — FAILED branch must persist error_detail and
    # error_type so the error is reachable to API consumers, not just
    # to the Django logs.
    # ----------------------------------------------------------------
    @patch(f"{_CLIENT}.ComplianceServiceClient")
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_remote_failed_persists_error_detail_and_type(
        self, mock_qs, mock_client_cls,
    ):
        run = self._make_run()
        mock_qs.select_related.return_value.get.return_value = run
        mock_client = MagicMock()
        mock_client.get_scan_result.return_value = {
            "status": "FAILED",
            "error": "scan worker crashed: KeyError 'tenant_id'",
        }
        mock_client_cls.return_value = mock_client

        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))

        self.assertEqual(run.status, "FAILED")
        self.assertIsNotNone(run.regulation_mapping_json)
        self.assertEqual(
            run.regulation_mapping_json["error"],
            "scan worker crashed: KeyError 'tenant_id'",
        )
        self.assertEqual(run.regulation_mapping_json["error_type"], "REMOTE_FAILURE")
        # Save must include regulation_mapping_json so the error reaches DB.
        save_kwargs = run.save.call_args.kwargs
        self.assertIn("regulation_mapping_json", save_kwargs["update_fields"])

    @patch(f"{_CLIENT}.ComplianceServiceClient")
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_remote_failed_preserves_existing_mapping_keys(
        self, mock_qs, mock_client_cls,
    ):
        run = self._make_run()
        run.regulation_mapping_json = {"GDPR": {"articles": ["Art. 6"]}}
        mock_qs.select_related.return_value.get.return_value = run
        mock_client = MagicMock()
        mock_client.get_scan_result.return_value = {
            "status": "FAILED",
            "detail": "boom",
        }
        mock_client_cls.return_value = mock_client

        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))

        # Pre-existing keys are preserved.
        self.assertEqual(run.regulation_mapping_json["GDPR"], {"articles": ["Art. 6"]})
        # And error fields are added on top.
        self.assertEqual(run.regulation_mapping_json["error"], "boom")
        self.assertEqual(run.regulation_mapping_json["error_type"], "REMOTE_FAILURE")

    @patch("hub.apps.compliance.tasks._reenqueue")
    @patch(f"{_CLIENT}.ComplianceServiceClient")
    @patch(f"{_MODELS}.ComplianceRun.objects")
    def test_client_error_reenqueues(
        self, mock_qs, mock_client_cls, mock_reenq,
    ):
        run = self._make_run()
        mock_qs.select_related.return_value.get.return_value = run
        mock_client = MagicMock()
        mock_client.get_scan_result.side_effect = ConnectionError("down")
        mock_client_cls.return_value = mock_client
        from hub.apps.compliance.tasks import poll_compliance_job
        poll_compliance_job(str(run.id))
        mock_reenq.assert_called_once()
