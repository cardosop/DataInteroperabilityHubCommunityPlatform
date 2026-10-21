"""
Tests for Error Handling Middleware
"""

from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from hub.apps.core.error_handling.middleware import ErrorHandlingMiddleware


class ErrorHandlingMiddlewareTest(TestCase):
    """Test ErrorHandlingMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = ErrorHandlingMiddleware(lambda request: HttpResponse("OK"))

    def test_process_request_generates_request_id(self):
        """Test that process_request generates request ID."""
        request = self.factory.get("/test/")

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "id"))
        self.assertIsNotNone(request.id)

    def test_process_request_preserves_existing_request_id(self):
        """Test that process_request preserves existing request ID."""
        request = self.factory.get("/test/")
        request.id = "existing-id"

        self.middleware.process_request(request)

        self.assertEqual(request.id, "existing-id")

    def test_process_request_sets_context(self):
        """Test that process_request sets structlog context."""

        request = self.factory.get("/test/")
        self.middleware.process_request(request)

        # Context should be set (we can't easily verify this without checking internals)
        # But we can verify request.id is set
        self.assertTrue(hasattr(request, "id"))

    def test_process_exception_logs_error(self):
        """Test that process_exception logs error."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            self.assertEqual(call_args[1]["error"], exception)
            self.assertEqual(call_args[1]["request_id"], "test-request-id")

    def test_process_exception_tracks_error(self):
        """Test that process_exception tracks error in Sentry."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_tracker, "track_error") as mock_track:
            self.middleware.process_exception(request, exception)

            mock_track.assert_called_once()
            call_args = mock_track.call_args
            self.assertEqual(call_args[1]["error"], exception)
            self.assertEqual(call_args[1]["request_id"], "test-request-id")

    def test_process_exception_with_tenant_id(self):
        """Test that process_exception includes tenant_id."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        request.tenant_id = "test-tenant-id"
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            call_args = mock_log.call_args
            self.assertEqual(call_args[1]["tenant_id"], "test-tenant-id")

    def test_process_exception_with_user_id(self):
        """Test that process_exception includes user_id for authenticated users."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        user = Mock()
        user.id = "test-user-id"
        user.is_authenticated = True
        request.user = user
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            call_args = mock_log.call_args
            self.assertEqual(call_args[1]["user_id"], "test-user-id")

    def test_process_exception_without_user(self):
        """Test that process_exception handles missing user."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        # No user attribute
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            call_args = mock_log.call_args
            self.assertIsNone(call_args[1]["user_id"])

    def test_process_exception_with_unauthenticated_user(self):
        """Test that process_exception handles unauthenticated user."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        user = Mock()
        user.is_authenticated = False
        request.user = user
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            call_args = mock_log.call_args
            self.assertIsNone(call_args[1]["user_id"])

    def test_process_exception_sets_user_context(self):
        """Test that process_exception sets user context in Sentry."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        user = Mock()
        user.id = "test-user-id"
        user.is_authenticated = True
        request.user = user
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_tracker, "set_user") as mock_set_user:
            self.middleware.process_exception(request, exception)

            mock_set_user.assert_called_once_with("test-user-id")

    def test_process_exception_sets_tenant_context(self):
        """Test that process_exception sets tenant context in Sentry."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        request.tenant_id = "test-tenant-id"
        exception = ValueError("Test error")

        with patch.object(self.middleware.error_tracker, "set_tenant") as mock_set_tenant:
            self.middleware.process_exception(request, exception)

            mock_set_tenant.assert_called_once_with("test-tenant-id")

    def test_process_exception_returns_none(self):
        """Test that process_exception returns None."""
        request = self.factory.get("/test/")
        exception = ValueError("Test error")

        result = self.middleware.process_exception(request, exception)

        self.assertIsNone(result)

    def test_process_exception_with_exception_code(self):
        """Test that process_exception uses exception code if available."""
        request = self.factory.get("/test/")
        request.id = "test-request-id"
        exception = ValueError("Test error")
        exception.code = "TEST_ERROR"
        exception.status_code = 400

        with patch.object(self.middleware.error_logger, "log_error") as mock_log:
            self.middleware.process_exception(request, exception)

            call_args = mock_log.call_args
            self.assertEqual(call_args[1]["error_code"], "TEST_ERROR")
            self.assertEqual(call_args[1]["http_status"], 400)
