"""
Phase 63 — CSP Report Endpoint Tests

Tests for POST /api/csp-report/ which accepts browser CSP violation reports.
The endpoint is intentionally unauthenticated (browsers send reports before
page scripts run) and always returns 204 No Content.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from hub.apps.security.views import csp_report_view


class _CSPTestBase(TestCase):
    """Shared base for CSP report tests — provides a RequestFactory."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.factory = RequestFactory()


class CSPReportAcceptsValidPayloadTest(_CSPTestBase):
    """POST valid CSP2 violation JSON → 204."""

    def test_csp_report_accepts_valid_payload(self):
        payload = {
            "csp-report": {
                "document-uri": "https://app.example.com/dashboard",
                "violated-directive": "script-src 'self'",
                "blocked-uri": "https://evil.example.com/inject.js",
                "source-file": "https://app.example.com/app.js",
                "line-number": 42,
                "column-number": 13,
                "status-code": 200,
            }
        }
        request = self.factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportNoAuthRequiredTest(_CSPTestBase):
    """POST without Authorization header → 204 (RFC 7034)."""

    def test_csp_report_no_auth_required(self):
        payload = {"csp-report": {"violated-directive": "img-src"}}
        request = self.factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        # No request.user, no Authorization header
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportEmptyBodyTest(_CSPTestBase):
    """POST with empty body → 204 (graceful, not 400)."""

    def test_csp_report_empty_body_returns_204(self):
        """The endpoint returns 204 even for empty bodies to avoid
        leaking information and to prevent browsers from stopping reports."""
        request = self.factory.post(
            "/api/csp-report/",
            data=b"",
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        # Implementation returns 204 for all cases (RFC guidance: don't
        # return errors that could cause browsers to stop sending reports)
        self.assertEqual(response.status_code, 204)


class CSPReportInvalidJSONTest(_CSPTestBase):
    """POST with non-JSON content → 204 (graceful)."""

    def test_csp_report_invalid_json_returns_204(self):
        request = self.factory.post(
            "/api/csp-report/",
            data=b"not json at all {{{",
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportMetricIncrementTest(_CSPTestBase):
    """POST valid payload → OTel counter incremented."""

    @patch("hub.apps.security.views._CSP_VIOLATIONS")
    def test_csp_report_increments_prometheus_counter(self, mock_counter):
        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        payload = {
            "csp-report": {
                "violated-directive": "script-src 'self'",
                "document-uri": "https://app.example.com/login",
            }
        }
        request = self.factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        response = csp_report_view(request)

        self.assertEqual(response.status_code, 204)
        mock_counter.labels.assert_called_once_with(
            violated_directive="script-src",
            document_uri_path="/login",
        )
        mock_labels.inc.assert_called_once()


class CSPReportLegacyFormatTest(_CSPTestBase):
    """POST with CSP2 csp-report wrapper → 204."""

    def test_csp_report_legacy_format(self):
        payload = {
            "csp-report": {
                "violated-directive": "style-src 'self'",
                "document-uri": "https://app.example.com/",
                "blocked-uri": "inline",
            }
        }
        request = self.factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportModernFormatTest(_CSPTestBase):
    """POST with Reporting API v1 body array → 204."""

    def test_csp_report_modern_format(self):
        # Reporting API v1: array of report objects with "body" sub-object
        payload = [
            {
                "type": "csp-violation",
                "url": "https://app.example.com/dashboard",
                "body": {
                    "effectiveDirective": "connect-src",
                    "blockedURL": "https://evil.example.com/api",
                    "documentURL": "https://app.example.com/dashboard",
                },
            }
        ]
        request = self.factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/reports+json",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)
