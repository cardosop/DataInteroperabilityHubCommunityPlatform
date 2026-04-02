"""
Phase 63 — CSP Report Endpoint Tests

Tests for POST /api/csp-report/ which accepts browser CSP violation reports.
The endpoint is intentionally unauthenticated (browsers send reports before
page scripts run) and always returns 204 No Content.
"""

import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory

from hub.apps.security.views import csp_report_view


class CSPReportAcceptsValidPayloadTest(TestCase):
    """POST valid CSP2 violation JSON → 204."""

    def test_csp_report_accepts_valid_payload(self):
        factory = RequestFactory()
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
        request = factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportNoAuthRequiredTest(TestCase):
    """POST without Authorization header → 204 (RFC 7034)."""

    def test_csp_report_no_auth_required(self):
        factory = RequestFactory()
        payload = {"csp-report": {"violated-directive": "img-src"}}
        request = factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        # No request.user, no Authorization header
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportEmptyBodyTest(TestCase):
    """POST with empty body → 204 (graceful, not 400)."""

    def test_csp_report_empty_body_returns_204(self):
        """The endpoint returns 204 even for empty bodies to avoid
        leaking information and to prevent browsers from stopping reports."""
        factory = RequestFactory()
        request = factory.post(
            "/api/csp-report/",
            data=b"",
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        # Implementation returns 204 for all cases (RFC guidance: don't
        # return errors that could cause browsers to stop sending reports)
        self.assertEqual(response.status_code, 204)


class CSPReportInvalidJSONTest(TestCase):
    """POST with non-JSON content → 204 (graceful)."""

    def test_csp_report_invalid_json_returns_204(self):
        factory = RequestFactory()
        request = factory.post(
            "/api/csp-report/",
            data=b"not json at all {{{",
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportMetricIncrementTest(TestCase):
    """POST valid payload → OTel counter incremented."""

    @patch("hub.apps.security.views._CSP_VIOLATIONS")
    def test_csp_report_increments_prometheus_counter(self, mock_counter):
        mock_labels = MagicMock()
        mock_counter.labels.return_value = mock_labels

        factory = RequestFactory()
        payload = {
            "csp-report": {
                "violated-directive": "script-src 'self'",
                "document-uri": "https://app.example.com/login",
            }
        }
        request = factory.post(
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


class CSPReportLegacyFormatTest(TestCase):
    """POST with CSP2 csp-report wrapper → 204."""

    def test_csp_report_legacy_format(self):
        factory = RequestFactory()
        payload = {
            "csp-report": {
                "violated-directive": "style-src 'self'",
                "document-uri": "https://app.example.com/",
                "blocked-uri": "inline",
            }
        }
        request = factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/csp-report",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)


class CSPReportModernFormatTest(TestCase):
    """POST with Reporting API v1 body array → 204."""

    def test_csp_report_modern_format(self):
        factory = RequestFactory()
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
        request = factory.post(
            "/api/csp-report/",
            data=json.dumps(payload),
            content_type="application/reports+json",
        )
        response = csp_report_view(request)
        self.assertEqual(response.status_code, 204)
