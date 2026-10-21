"""
Comprehensive tests for Trace ID Propagation Middleware

Tests cover:
- Trace ID extraction from traceparent header (W3C Trace Context)
- Trace ID extraction from X-Trace-Id header (fallback)
- Trace ID generation when not present
- Trace ID in response headers (X-Trace-Id)
- Trace propagation to service clients
- W3C Trace Context format validation
"""

from django.http import HttpResponse, JsonResponse
from django.test import RequestFactory, TestCase

from hub.apps.api.middleware.trace_propagation import (
    get_current_request,
    get_trace_headers,
)
from hub.apps.api.middleware.tracing import (
    TraceIDMiddleware,
    extract_trace_id_from_request,
    format_traceparent,
    generate_span_id,
    generate_trace_id,
    parse_traceparent_header,
)


class TraceIDMiddlewareTest(TestCase):
    """Test trace ID middleware"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.middleware = TraceIDMiddleware(lambda request: HttpResponse())

    def test_extract_trace_id_from_traceparent(self):
        """Test trace ID extraction from traceparent header"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        parent_id = "00f067aa0ba902b7"
        traceparent = f"00-{trace_id}-{parent_id}-01"
        request.META["HTTP_TRACEPARENT"] = traceparent

        extracted_trace_id, extracted_parent_id, extracted_flags = extract_trace_id_from_request(
            request
        )

        self.assertEqual(extracted_trace_id, trace_id.lower())
        self.assertEqual(extracted_parent_id, parent_id.lower())
        self.assertEqual(extracted_flags, "01")

    def test_extract_trace_id_from_x_trace_id(self):
        """Test trace ID extraction from X-Trace-Id header"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        request.META["HTTP_X_TRACE_ID"] = trace_id

        extracted_trace_id, extracted_parent_id, extracted_flags = extract_trace_id_from_request(
            request
        )

        self.assertEqual(extracted_trace_id, trace_id.lower())
        self.assertIsNone(extracted_parent_id)
        self.assertIsNone(extracted_flags)

    def test_generate_trace_id_when_not_present(self):
        """Test trace ID generation when not present in headers"""
        request = self.factory.get("/api/v1/datasets/")

        extracted_trace_id, extracted_parent_id, extracted_flags = extract_trace_id_from_request(
            request
        )

        self.assertIsNotNone(extracted_trace_id)
        self.assertEqual(len(extracted_trace_id), 32)  # 32 hex characters
        self.assertIsNone(extracted_parent_id)
        self.assertIsNone(extracted_flags)

    def test_parse_traceparent_valid(self):
        """Test parsing valid traceparent header"""
        traceparent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        parsed = parse_traceparent_header(traceparent)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["version"], "00")
        self.assertEqual(parsed["trace_id"], "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(parsed["parent_id"], "00f067aa0ba902b7")
        self.assertEqual(parsed["flags"], "01")

    def test_parse_traceparent_invalid_format(self):
        """Test parsing invalid traceparent format"""
        traceparent = "invalid-format"
        parsed = parse_traceparent_header(traceparent)

        self.assertIsNone(parsed)

    def test_parse_traceparent_invalid_version(self):
        """Test parsing traceparent with unsupported version"""
        traceparent = "01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        parsed = parse_traceparent_header(traceparent)

        self.assertIsNone(parsed)

    def test_parse_traceparent_invalid_trace_id(self):
        """Test parsing traceparent with invalid trace ID"""
        traceparent = "00-invalid-trace-id-00f067aa0ba902b7-01"
        parsed = parse_traceparent_header(traceparent)

        self.assertIsNone(parsed)

    def test_generate_trace_id_format(self):
        """Test trace ID generation format"""
        trace_id = generate_trace_id()

        self.assertEqual(len(trace_id), 32)
        self.assertTrue(all(c in "0123456789abcdef" for c in trace_id))

    def test_generate_span_id_format(self):
        """Test span ID generation format"""
        span_id = generate_span_id()

        self.assertEqual(len(span_id), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in span_id))

    def test_format_traceparent(self):
        """Test traceparent formatting"""
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        parent_id = "00f067aa0ba902b7"
        flags = "01"

        traceparent = format_traceparent(trace_id, parent_id, flags)

        self.assertEqual(traceparent, f"00-{trace_id}-{parent_id}-{flags}")

    def test_middleware_extracts_trace_id(self):
        """Test middleware extracts trace ID from request"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        request.META["HTTP_X_TRACE_ID"] = trace_id

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "trace_id"))
        self.assertEqual(request.trace_id, trace_id.lower())
        self.assertTrue(hasattr(request, "span_id"))
        self.assertEqual(len(request.span_id), 16)

    def test_middleware_generates_trace_id(self):
        """Test middleware generates trace ID when not present"""
        request = self.factory.get("/api/v1/datasets/")

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "trace_id"))
        self.assertEqual(len(request.trace_id), 32)
        self.assertTrue(hasattr(request, "span_id"))
        self.assertEqual(len(request.span_id), 16)

    def test_middleware_adds_trace_id_to_response(self):
        """Test middleware adds trace ID to response headers"""
        request = self.factory.get("/api/v1/datasets/")
        response = JsonResponse({"ok": True})

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        self.assertIn("X-Trace-Id", processed_response)
        self.assertEqual(processed_response["X-Trace-Id"], request.trace_id)

    def test_middleware_skips_non_api_responses(self):
        """Test middleware skips non-API responses"""
        request = self.factory.get("/admin/")
        response = HttpResponse("OK")

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        # Trace ID should still be set in request
        self.assertTrue(hasattr(request, "trace_id"))
        # But not added to response headers for non-API paths
        self.assertNotIn("X-Trace-Id", processed_response)

    def test_middleware_creates_traceparent(self):
        """Test middleware creates traceparent for outgoing requests"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        request.META["HTTP_X_TRACE_ID"] = trace_id

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "traceparent"))
        self.assertTrue(request.traceparent.startswith("00-"))
        self.assertIn(trace_id.lower(), request.traceparent)

    def test_trace_propagation_get_trace_headers(self):
        """Test trace header generation for service clients"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        request.META["HTTP_X_TRACE_ID"] = trace_id

        self.middleware.process_request(request)

        headers = get_trace_headers()

        self.assertIn("traceparent", headers)
        self.assertIn("X-Trace-Id", headers)
        self.assertEqual(headers["X-Trace-Id"], trace_id.lower())

    def test_trace_propagation_without_request(self):
        """Test trace header generation without request"""
        # Clear context variable to ensure no request is stored
        from hub.apps.api.middleware.trace_propagation import _current_request

        _current_request.set(None)

        headers = get_trace_headers()

        self.assertEqual(headers, {})

    def test_trace_propagation_context_storage(self):
        """Test trace propagation context storage"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        request.META["HTTP_X_TRACE_ID"] = trace_id

        self.middleware.process_request(request)

        # Check context storage
        current_request = get_current_request()
        self.assertIsNotNone(current_request)
        self.assertEqual(current_request.trace_id, trace_id.lower())

    def test_traceparent_precedence_over_x_trace_id(self):
        """Test that traceparent takes precedence over X-Trace-Id"""
        request = self.factory.get("/api/v1/datasets/")
        traceparent_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        x_trace_id = "different-trace-id-1234567890123456"
        traceparent = f"00-{traceparent_trace_id}-00f067aa0ba902b7-01"
        request.META["HTTP_TRACEPARENT"] = traceparent
        request.META["HTTP_X_TRACE_ID"] = x_trace_id

        extracted_trace_id, _, _ = extract_trace_id_from_request(request)

        # Should use traceparent trace ID, not X-Trace-Id
        self.assertEqual(extracted_trace_id, traceparent_trace_id.lower())

    def test_trace_id_normalized_to_lowercase(self):
        """Test that trace IDs are normalized to lowercase"""
        request = self.factory.get("/api/v1/datasets/")
        trace_id = "4BF92F3577B34DA6A3CE929D0E0E4736"  # Uppercase
        request.META["HTTP_X_TRACE_ID"] = trace_id

        extracted_trace_id, _, _ = extract_trace_id_from_request(request)

        self.assertEqual(extracted_trace_id, trace_id.lower())
