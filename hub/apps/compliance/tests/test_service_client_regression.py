"""
Regression tests for ComplianceServiceClient.

Validates fix for Bug 5: sync scan_file() missing legal_basis parameter.
Uses real ComplianceServiceClient with mocked HTTP transport to verify
the POST data sent to the compliance microservice.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.compliance.service_client import ComplianceServiceClient

pytestmark = pytest.mark.django_db(transaction=True)


class ScanFileLegalBasisTest(TestCase):
    """Tests that sync scan_file() forwards legal_basis to the microservice."""

    @override_settings(COMPLIANCE_SERVICE_URL="http://localhost:19999")
    def test_sync_scan_file_passes_legal_basis(self):
        """POST data includes legal_basis when provided."""
        client = ComplianceServiceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "risk_level": "NONE",
            "allowed_to_store": True,
            "detected_categories": [],
            "column_findings": [],
            "regulation_mapping": {},
            "applicable_regulations": [],
            "issues": [],
            "metadata": {},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request_with_retry", return_value=mock_response) as mock_req:
            with patch.object(client._circuit_breaker, "call", side_effect=lambda fn, **kw: fn()):
                client.scan_file(
                    file_content=b"id,name\n1,test",
                    file_format="csv",
                    legal_basis="consent",
                    tenant_id="test-tenant",
                )

            # Verify the POST call included legal_basis in data
            call_args = mock_req.call_args
            post_data = call_args.kwargs.get("data") or call_args[1].get("data", {})
            self.assertIn("legal_basis", post_data)
            self.assertEqual(post_data["legal_basis"], "consent")

    @override_settings(COMPLIANCE_SERVICE_URL="http://localhost:19999")
    def test_sync_scan_file_omits_legal_basis_when_none(self):
        """POST data does NOT include legal_basis when None."""
        client = ComplianceServiceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "risk_level": "NONE",
            "allowed_to_store": True,
            "detected_categories": [],
            "column_findings": [],
            "regulation_mapping": {},
            "applicable_regulations": [],
            "issues": [],
            "metadata": {},
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_request_with_retry", return_value=mock_response) as mock_req:
            with patch.object(client._circuit_breaker, "call", side_effect=lambda fn, **kw: fn()):
                client.scan_file(
                    file_content=b"id,name\n1,test",
                    file_format="csv",
                    legal_basis=None,
                    tenant_id="test-tenant",
                )

            call_args = mock_req.call_args
            post_data = call_args.kwargs.get("data") or call_args[1].get("data", {})
            self.assertNotIn("legal_basis", post_data)

    @override_settings(COMPLIANCE_SERVICE_URL="http://localhost:19999")
    def test_circuit_breaker_call_is_invoked(self):
        """scan_file routes through the circuit breaker, not raw HTTP."""
        client = ComplianceServiceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"overall_status": "PASS"}

        with patch.object(
            client, "_request_with_retry", return_value=mock_response,
        ):
            with patch.object(
                client._circuit_breaker, "call",
                side_effect=lambda fn, fallback=None: fn(),
            ) as mock_cb_call:
                client.scan_file(
                    file_content=b"x", file_format="csv",
                )
                mock_cb_call.assert_called_once()
