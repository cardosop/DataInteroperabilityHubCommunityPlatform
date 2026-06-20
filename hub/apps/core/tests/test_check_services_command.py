"""
Phase 83.11 — check_services management command tests.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

_CMD = "hub.apps.core.management.commands.check_services"


class CheckServicesCommandTest(TestCase):
    @patch(f"{_CMD}.check_all_services")
    def test_all_healthy_exit_zero(self, mock_check):
        mock_check.return_value = {
            "dq-service": (True, None),
            "compliance-service": (True, None),
        }
        out = StringIO()
        call_command("check_services", stdout=out)
        assert "2/2" in out.getvalue()

    @patch(f"{_CMD}.check_all_services")
    def test_one_down_shown(self, mock_check):
        mock_check.return_value = {
            "dq-service": (True, None),
            "compliance-service": (False, "Connection refused"),
        }
        out = StringIO()
        call_command("check_services", stdout=out)
        assert "1/2" in out.getvalue()
        assert "compliance-service" in out.getvalue()

    @patch(f"{_CMD}.get_all_service_configs")
    @patch(f"{_CMD}.check_service_availability")
    def test_single_service_mode(self, mock_check, mock_configs):
        mock_configs.return_value = {
            "dq-service": {
                "url": "http://dq:8000",
                "health_path": "/health",
                "timeout": 5,
            },
        }
        mock_check.return_value = (True, None)
        out = StringIO()
        call_command(
            "check_services",
            "--service=dq-service",
            stdout=out,
        )
        mock_check.assert_called_once()

    @patch(f"{_CMD}.get_all_service_configs")
    def test_unknown_service_shown(self, mock_configs):
        mock_configs.return_value = {
            "dq-service": {"url": "http://dq:8000"},
        }
        out = StringIO()
        call_command(
            "check_services",
            "--service=nonexistent",
            stdout=out,
        )
        assert "Unknown service" in out.getvalue()
