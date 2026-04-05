"""
Error Tracking with Sentry

Provides Sentry integration for error tracking and monitoring.
"""
import os
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

# Try to import Sentry
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    _sentry_available = True
except ImportError:
    sentry_sdk = None
    DjangoIntegration = None
    LoggingIntegration = None
    RedisIntegration = None
    _sentry_available = False


class ErrorTracker:
    """Error tracker with Sentry integration."""
    
    def __init__(self):
        """Initialize error tracker."""
        self._sentry_available = _sentry_available
        if self._sentry_available:
            self._initialize_sentry()
    
    def _initialize_sentry(self) -> None:
        """Initialize Sentry SDK."""
        if not _sentry_available:
            return
        
        dsn = os.getenv("SENTRY_DSN")
        if not dsn:
            logger.warning("SENTRY_DSN not set, Sentry tracking disabled")
            return
        
        environment = os.getenv("ENVIRONMENT", "development")
        release = os.getenv("RELEASE_VERSION", "unknown")
        
        # Configure Sentry
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            release=release,
            integrations=[
                DjangoIntegration(),
                LoggingIntegration(level=None, event_level=None),
                RedisIntegration(),
            ],
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            send_default_pii=False,  # Don't send PII by default
            before_send=self._before_send,
        )
        
        logger.info("Sentry initialized", environment=environment, release=release)
    
    def _before_send(self, event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process event before sending to Sentry.
        
        Args:
            event: Sentry event
            hint: Event hint
            
        Returns:
            Modified event or None to drop event
        """
        # Redact PII from event
        if "user" in event:
            user = event["user"]
            if "email" in user:
                user["email"] = "[REDACTED]"
            if "username" in user:
                user["username"] = "[REDACTED]"
        
        # Redact sensitive data from extra
        if "extra" in event:
            sensitive_keys = ["password", "token", "api_key", "secret", "authorization"]
            for key in sensitive_keys:
                if key in event["extra"]:
                    event["extra"][key] = "[REDACTED]"
        
        return event
    
    def track_error(
        self,
        error: Exception,
        error_code: Optional[str] = None,
        message: Optional[str] = None,
        http_status: Optional[int] = None,
        request_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        level: str = "error",
    ) -> None:
        """
        Track an error in Sentry.
        
        Args:
            error: Exception instance
            error_code: Error code
            message: Error message
            http_status: HTTP status code
            request_id: Request ID
            tenant_id: Tenant ID
            user_id: User ID
            context: Additional context
            level: Error level
        """
        if not self._sentry_available:
            return
        
        # Set user context
        if user_id:
            sentry_sdk.set_user({"id": user_id})
        
        # Set tags
        tags = {}
        if error_code:
            tags["error_code"] = error_code
        if http_status:
            tags["http_status"] = str(http_status)
        if tenant_id:
            tags["tenant_id"] = tenant_id
        if request_id:
            tags["request_id"] = request_id
        
        # Set context
        contexts = {}
        if context:
            contexts["additional"] = context
        if message:
            contexts["message"] = message
        
        # Set tags and contexts
        with sentry_sdk.new_scope() as scope:
            for key, value in tags.items():
                scope.set_tag(key, value)
            for key, value in contexts.items():
                scope.set_context(key, value)

            # Capture exception
            scope.capture_exception(error, level=level)
    
    def track_exception(
        self,
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        level: str = "error",
    ) -> None:
        """
        Track an exception in Sentry.
        
        Args:
            exception: Exception instance
            context: Additional context
            level: Error level
        """
        self.track_error(
            error=exception,
            error_code=getattr(exception, "code", None),
            message=str(exception),
            context=context,
            level=level,
        )
    
    def track_message(
        self,
        message: str,
        level: str = "info",
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Track a message in Sentry.
        
        Args:
            message: Message to track
            level: Message level
            context: Additional context
        """
        if not self._sentry_available:
            return
        
        with sentry_sdk.new_scope() as scope:
            if context:
                scope.set_context("additional", context)
            scope.capture_message(message, level=level)
    
    def set_user(self, user_id: str, email: Optional[str] = None, username: Optional[str] = None) -> None:
        """
        Set user context for Sentry.
        
        Args:
            user_id: User ID
            email: User email (will be redacted)
            username: Username (will be redacted)
        """
        if not self._sentry_available:
            return
        
        sentry_sdk.set_user({
            "id": user_id,
            # Don't set email/username to avoid PII
        })
    
    def set_tenant(self, tenant_id: str) -> None:
        """
        Set tenant context for Sentry.
        
        Args:
            tenant_id: Tenant ID
        """
        if not self._sentry_available:
            return
        
        sentry_sdk.set_tag("tenant_id", tenant_id)


# Global error tracker instance
_error_tracker = None


def get_error_tracker() -> ErrorTracker:
    """Get global error tracker instance."""
    global _error_tracker
    if _error_tracker is None:
        _error_tracker = ErrorTracker()
    return _error_tracker


def track_error(
    error: Exception,
    error_code: Optional[str] = None,
    message: Optional[str] = None,
    http_status: Optional[int] = None,
    request_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> None:
    """
    Track an error in Sentry (convenience function).
    
    Args:
        error: Exception instance
        error_code: Error code
        message: Error message
        http_status: HTTP status code
        request_id: Request ID
        tenant_id: Tenant ID
        user_id: User ID
        context: Additional context
        level: Error level
    """
    tracker = get_error_tracker()
    tracker.track_error(
        error=error,
        error_code=error_code,
        message=message,
        http_status=http_status,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        context=context,
        level=level,
    )


def track_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error",
) -> None:
    """
    Track an exception in Sentry (convenience function).
    
    Args:
        exception: Exception instance
        context: Additional context
        level: Error level
    """
    tracker = get_error_tracker()
    tracker.track_exception(exception, context, level)

