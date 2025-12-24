"""
ODPS $ref Resolver Security Logging and Monitoring

Provides structured logging and monitoring for ODPS $ref resolution security events,
including security violations, audit trails, and alert generation.

Security Event Types:
- PATH_TRAVERSAL: Attempted path traversal attack
- URL_DENIED: External URL denied by denylist
- URL_NOT_ALLOWED: External URL not in allowlist
- RATE_LIMIT_EXCEEDED: Rate limit exceeded
- SIZE_LIMIT_EXCEEDED: File size limit exceeded
- TIMEOUT: Request timeout
- INVALID_URL: Invalid URL format
- INVALID_FILE_TYPE: Invalid file type/extension for local $ref
- SUSPICIOUS_PATTERN: Suspicious activity pattern detected
"""
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import structlog

logger = structlog.get_logger(__name__)


class SecurityEventType(str, Enum):
    """Security event types for ODPS $ref resolution"""
    PATH_TRAVERSAL = "PATH_TRAVERSAL"
    URL_DENIED = "URL_DENIED"
    URL_NOT_ALLOWED = "URL_NOT_ALLOWED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SIZE_LIMIT_EXCEEDED = "SIZE_LIMIT_EXCEEDED"
    TIMEOUT = "TIMEOUT"
    INVALID_URL = "INVALID_URL"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    SUSPICIOUS_PATTERN = "SUSPICIOUS_PATTERN"


class SecuritySeverity(str, Enum):
    """Security event severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class SecurityViolationLog:
    """
    Structured log format for security violations.

    This format ensures all security events are logged with consistent,
    machine-readable structure for monitoring and alerting systems.
    """
    # Event identification (required fields first)
    event_type: str  # SecurityEventType value
    severity: str  # SecuritySeverity value
    timestamp: str  # ISO 8601 timestamp with timezone
    violation_type: str  # Human-readable violation type
    description: str  # Detailed description of the violation

    # Context (optional fields)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    contract_id: Optional[str] = None

    # Security event details (optional)
    attempted_path: Optional[str] = None  # For path traversal
    attempted_url: Optional[str] = None  # For URL violations
    allowed_dirs: Optional[List[str]] = None  # For path traversal context
    url_pattern: Optional[str] = None  # For URL violations

    # Request context (optional)
    request_id: Optional[str] = None
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

    # Additional metadata (optional)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for structured logging"""
        result = asdict(self)
        # Remove None values for cleaner logs
        return {k: v for k, v in result.items() if v is not None}

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with security tags for logging"""
        log_dict = self.to_dict()
        # Add security tags for filtering
        log_dict['security_event'] = True
        log_dict['security_type'] = self.event_type
        log_dict['security_severity'] = self.severity
        return log_dict


@dataclass
class RefResolutionAuditLog:
    """
    Structured audit trail format for $ref resolution operations.

    Provides complete audit trail of all $ref resolution attempts,
    both successful and failed, for compliance and debugging.
    """
    # Operation identification (required fields first)
    operation_id: str  # Unique operation identifier
    timestamp: str  # ISO 8601 timestamp with timezone
    duration_ms: float  # Operation duration in milliseconds
    ref_type: str  # "internal", "local", or "external"
    ref_path: str  # The $ref path/value
    success: bool  # Whether resolution succeeded

    # Context (optional fields)
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    contract_id: Optional[str] = None

    # Reference details (optional)
    resolved_path: Optional[str] = None  # Resolved path/URL

    # Resolution result (optional)
    error_type: Optional[str] = None  # Error type if failed
    error_message: Optional[str] = None  # Error message if failed

    # Security checks (optional with defaults)
    security_checks_passed: bool = True
    security_violations: Optional[List[str]] = None  # List of security violations

    # Performance metrics (optional)
    size_bytes: Optional[int] = None  # Size of resolved content
    cache_hit: Optional[bool] = None  # Whether result came from cache

    # Additional metadata (optional)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for structured logging"""
        result = asdict(self)
        # Remove None values for cleaner logs
        return {k: v for k, v in result.items() if v is not None}

    def to_log_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with audit tags for logging"""
        log_dict = self.to_dict()
        # Add audit tags for filtering
        log_dict['audit_event'] = True
        log_dict['audit_type'] = 'ref_resolution'
        return log_dict


class SecurityLogger:
    """
    Security logging manager for ODPS $ref resolution.

    Provides methods for logging security violations and audit trails
    with structured, machine-readable format.
    """

    def __init__(self):
        """Initialize security logger"""
        self.logger = structlog.get_logger(__name__)

    def log_security_violation(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        violation_type: str,
        description: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        attempted_path: Optional[str] = None,
        attempted_url: Optional[str] = None,
        allowed_dirs: Optional[List[str]] = None,
        url_pattern: Optional[str] = None,
        request_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SecurityViolationLog:
        """
        Log a security violation event.

        Args:
            event_type: Type of security event
            severity: Severity level
            violation_type: Human-readable violation type
            description: Detailed description
            tenant_id: Tenant ID (if available)
            user_id: User ID (if available)
            contract_id: Contract ID (if available)
            attempted_path: Path that was attempted (for path traversal)
            attempted_url: URL that was attempted (for URL violations)
            allowed_dirs: Allowed directories (for path traversal context)
            url_pattern: URL pattern that matched (for URL violations)
            request_id: Request ID for tracing
            user_agent: User agent string
            ip_address: Client IP address
            metadata: Additional metadata

        Returns:
            SecurityViolationLog instance that was logged
        """
        violation_log = SecurityViolationLog(
            event_type=event_type.value,
            severity=severity.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tenant_id=tenant_id,
            user_id=user_id,
            contract_id=contract_id,
            violation_type=violation_type,
            description=description,
            attempted_path=attempted_path,
            attempted_url=attempted_url,
            allowed_dirs=allowed_dirs,
            url_pattern=url_pattern,
            request_id=request_id,
            user_agent=user_agent,
            ip_address=ip_address,
            metadata=metadata
        )

        # Log with appropriate level based on severity
        log_dict = violation_log.to_log_dict()

        if severity == SecuritySeverity.CRITICAL:
            self.logger.error("odps_security_violation", **log_dict)
        elif severity == SecuritySeverity.HIGH:
            self.logger.warning("odps_security_violation", **log_dict)
        elif severity == SecuritySeverity.MEDIUM:
            self.logger.warning("odps_security_violation", **log_dict)
        else:
            self.logger.info("odps_security_violation", **log_dict)

        return violation_log

    def log_ref_resolution_audit(
        self,
        operation_id: str,
        ref_type: str,
        ref_path: str,
        success: bool,
        duration_ms: float,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        resolved_path: Optional[str] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        security_checks_passed: bool = True,
        security_violations: Optional[List[str]] = None,
        size_bytes: Optional[int] = None,
        cache_hit: Optional[bool] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RefResolutionAuditLog:
        """
        Log a $ref resolution audit trail entry.

        Args:
            operation_id: Unique operation identifier
            ref_type: Type of reference ("internal", "local", or "external")
            ref_path: The $ref path/value
            success: Whether resolution succeeded
            duration_ms: Operation duration in milliseconds
            tenant_id: Tenant ID (if available)
            user_id: User ID (if available)
            contract_id: Contract ID (if available)
            resolved_path: Resolved path/URL
            error_type: Error type if failed
            error_message: Error message if failed
            security_checks_passed: Whether security checks passed
            security_violations: List of security violations
            size_bytes: Size of resolved content
            cache_hit: Whether result came from cache
            metadata: Additional metadata

        Returns:
            RefResolutionAuditLog instance that was logged
        """
        audit_log = RefResolutionAuditLog(
            operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            duration_ms=duration_ms,
            tenant_id=tenant_id,
            user_id=user_id,
            contract_id=contract_id,
            ref_type=ref_type,
            ref_path=ref_path,
            resolved_path=resolved_path,
            success=success,
            error_type=error_type,
            error_message=error_message,
            security_checks_passed=security_checks_passed,
            security_violations=security_violations,
            size_bytes=size_bytes,
            cache_hit=cache_hit,
            metadata=metadata
        )

        # Log audit trail
        log_dict = audit_log.to_log_dict()

        if success:
            self.logger.info("odps_ref_resolution_audit", **log_dict)
        else:
            self.logger.warning("odps_ref_resolution_audit", **log_dict)

        return audit_log


class SecurityAlertRule:
    """
    Alert rule for detecting suspicious patterns in security events.

    Alert rules define patterns that, when matched, should trigger alerts
    for security monitoring systems.
    """

    def __init__(
        self,
        name: str,
        pattern: str,
        threshold: int,
        window_seconds: int,
        severity: SecuritySeverity,
        description: str
    ):
        """
        Initialize alert rule.

        Args:
            name: Rule name/identifier
            pattern: Pattern to match (event type, tenant_id, user_id, etc.)
            threshold: Number of events to trigger alert
            window_seconds: Time window in seconds
            severity: Alert severity
            description: Rule description
        """
        self.name = name
        self.pattern = pattern
        self.threshold = threshold
        self.window_seconds = window_seconds
        self.severity = severity
        self.description = description

    def matches(self, event: SecurityViolationLog) -> bool:
        """
        Check if an event matches this rule's pattern.

        Args:
            event: Security violation log event

        Returns:
            True if event matches pattern
        """
        # Simple pattern matching - can be extended with regex or more complex logic
        # Pattern format: "event_type:EVENT_TYPE" or "event_type:EVENT_TYPE,tenant_id:TENANT_ID"
        pattern_parts = self.pattern.split(',')

        for part in pattern_parts:
            key, value = part.split(':', 1)
            if key == 'event_type':
                if event.event_type != value:
                    return False
            elif key == 'tenant_id':
                if event.tenant_id != value:
                    return False
            elif key == 'user_id':
                if event.user_id != value:
                    return False
            # Add more pattern matching as needed

        return True


# Default alert rules for common suspicious patterns
DEFAULT_ALERT_RULES = [
    SecurityAlertRule(
        name="multiple_path_traversals",
        pattern="event_type:PATH_TRAVERSAL",
        threshold=5,
        window_seconds=300,  # 5 minutes
        severity=SecuritySeverity.HIGH,
        description="Multiple path traversal attempts within short time window"
    ),
    SecurityAlertRule(
        name="rate_limit_abuse",
        pattern="event_type:RATE_LIMIT_EXCEEDED",
        threshold=10,
        window_seconds=3600,  # 1 hour
        severity=SecuritySeverity.MEDIUM,
        description="Repeated rate limit violations"
    ),
    SecurityAlertRule(
        name="suspicious_url_patterns",
        pattern="event_type:URL_DENIED",
        threshold=3,
        window_seconds=600,  # 10 minutes
        severity=SecuritySeverity.HIGH,
        description="Multiple attempts to access denied URLs"
    ),
    SecurityAlertRule(
        name="tenant_security_issues",
        pattern="event_type:PATH_TRAVERSAL,tenant_id:*",
        threshold=10,
        window_seconds=3600,  # 1 hour
        severity=SecuritySeverity.CRITICAL,
        description="High number of security violations from a single tenant"
    ),
]


# Global security logger instance
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """
    Get the global security logger instance.

    Returns:
        SecurityLogger instance
    """
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger

