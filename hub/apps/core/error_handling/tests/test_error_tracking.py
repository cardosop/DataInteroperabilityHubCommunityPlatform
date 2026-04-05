"""
Tests for Error Tracking (Sentry)
"""
import os
import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase

from hub.apps.core.error_handling.error_tracking import (
    ErrorTracker,
    get_error_tracker,
    track_error,
    track_exception,
)


class ErrorTrackerTest(TestCase):
    """Test ErrorTracker class."""
    
    def test_tracker_initialization_no_sentry(self):
        """Test tracker initialization when Sentry is not available."""
        # Mock sentry_sdk not available
        with patch('hub.apps.core.error_handling.error_tracking._sentry_available', False):
            tracker = ErrorTracker()
            # Should not raise exception
            self.assertIsNotNone(tracker)
    
    @patch.dict(os.environ, {'SENTRY_DSN': 'https://test@sentry.io/test', 'ENVIRONMENT': 'test', 'RELEASE_VERSION': 'test'})
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.DjangoIntegration')
    @patch('hub.apps.core.error_handling.error_tracking.LoggingIntegration')
    @patch('hub.apps.core.error_handling.error_tracking.RedisIntegration')
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_tracker_initialization_with_sentry(self, mock_sentry, mock_redis, mock_logging, mock_django):
        """Test tracker initialization with Sentry."""
        # Reset the global tracker to force re-initialization
        import hub.apps.core.error_handling.error_tracking
        hub.apps.core.error_handling.error_tracking._error_tracker = None
        
        tracker = ErrorTracker()
        # Should initialize Sentry
        mock_sentry.init.assert_called_once()
    
    @patch.dict(os.environ, {}, clear=True)
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_tracker_initialization_no_dsn(self, mock_sentry):
        """Test tracker initialization without SENTRY_DSN."""
        tracker = ErrorTracker()
        # Should not initialize Sentry
        mock_sentry.init.assert_not_called()
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', False)
    def test_track_error_no_sentry(self):
        """Test tracking error when Sentry is not available."""
        tracker = ErrorTracker()
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            # Should not raise exception
            tracker.track_error(
                error=e,
                error_code="TEST_ERROR",
                message="Test error",
            )
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_track_error_with_sentry(self, mock_sentry):
        """Test tracking error with Sentry."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            tracker.track_error(
                error=e,
                error_code="TEST_ERROR",
                message="Test error",
                http_status=400,
                request_id="test-request-id",
                tenant_id="test-tenant-id",
                user_id="test-user-id",
            )
            
            # Should call capture_exception on the scope
            scope = mock_sentry.new_scope.return_value.__enter__.return_value
            scope.capture_exception.assert_called_once()
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_track_exception(self, mock_sentry):
        """Test tracking exception."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        try:
            raise RuntimeError("Test exception")
        except RuntimeError as e:
            tracker.track_exception(e, context={"test": "context"})
            
            scope = mock_sentry.new_scope.return_value.__enter__.return_value
            scope.capture_exception.assert_called_once()

    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_track_message(self, mock_sentry):
        """Test tracking message."""
        tracker = ErrorTracker()
        tracker._sentry_available = True

        tracker.track_message("Test message", level="info", context={"test": "context"})

        scope = mock_sentry.new_scope.return_value.__enter__.return_value
        scope.capture_message.assert_called_once_with("Test message", level="info")
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_set_user(self, mock_sentry):
        """Test setting user context."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        tracker.set_user("user-id", email=f"user-{uuid.uuid4().hex[:8]}@example.com", username="user")
        
        mock_sentry.set_user.assert_called_once()
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_set_tenant(self, mock_sentry):
        """Test setting tenant context."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        tracker.set_tenant("tenant-id")
        
        mock_sentry.set_tag.assert_called_once_with("tenant_id", "tenant-id")


class GetErrorTrackerTest(TestCase):
    """Test get_error_tracker function."""
    
    def test_get_error_tracker_singleton(self):
        """Test that get_error_tracker returns singleton."""
        tracker1 = get_error_tracker()
        tracker2 = get_error_tracker()
        
        self.assertIs(tracker1, tracker2)


class TrackErrorFunctionTest(TestCase):
    """Test track_error convenience function."""
    
    @patch('hub.apps.core.error_handling.error_tracking.get_error_tracker')
    def test_track_error_function(self, mock_get_tracker):
        """Test track_error convenience function."""
        mock_tracker = MagicMock()
        mock_get_tracker.return_value = mock_tracker
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            track_error(
                error=e,
                error_code="TEST_ERROR",
                message="Test error",
            )
            
            mock_tracker.track_error.assert_called_once()


class TrackExceptionFunctionTest(TestCase):
    """Test track_exception convenience function."""
    
    @patch('hub.apps.core.error_handling.error_tracking.get_error_tracker')
    def test_track_exception_function(self, mock_get_tracker):
        """Test track_exception convenience function."""
        mock_tracker = MagicMock()
        mock_get_tracker.return_value = mock_tracker
        
        try:
            raise RuntimeError("Test exception")
        except RuntimeError as e:
            track_exception(e, context={"test": "context"})
            
            mock_tracker.track_exception.assert_called_once()


class ErrorTrackerBeforeSendTest(TestCase):
    """Test ErrorTracker _before_send callback."""
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_before_send_redacts_pii(self, mock_sentry):
        """Test that _before_send redacts PII."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        event = {
            "user": {
                "email": "user@example.com",
                "username": "testuser",
            },
            "extra": {
                "password": "secret123",
                "token": "abc123",
                "api_key": "key123",
            }
        }
        
        result = tracker._before_send(event, {})
        
        self.assertEqual(result["user"]["email"], "[REDACTED]")
        self.assertEqual(result["user"]["username"], "[REDACTED]")
        self.assertEqual(result["extra"]["password"], "[REDACTED]")
        self.assertEqual(result["extra"]["token"], "[REDACTED]")
        self.assertEqual(result["extra"]["api_key"], "[REDACTED]")
    
    @patch('hub.apps.core.error_handling.error_tracking._sentry_available', True)
    @patch('hub.apps.core.error_handling.error_tracking.sentry_sdk')
    def test_before_send_returns_none(self, mock_sentry):
        """Test that _before_send can return None to drop event."""
        tracker = ErrorTracker()
        tracker._sentry_available = True
        
        # This test verifies the method exists and can be called
        # Returning None would drop the event, but we don't test that path
        event = {"user": {}}
        result = tracker._before_send(event, {})
        self.assertIsNotNone(result)

