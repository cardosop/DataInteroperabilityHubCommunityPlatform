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
- EXTERNAL_REF_FETCH: External $ref fetch (successful)
- CACHE_HIT: Cache hit
- CACHE_MISS: Cache miss
- CACHE_EVICTION: Cache eviction
- SECURITY_VIOLATION: General security violation
"""
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import structlog

logger = structlog.get_logger(__name__)

# Lazy import to avoid circular dependencies
try:
    from django.contrib.auth import get_user_model
    from hub.apps.contracts.models import SecurityAuditLog
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    SecurityAuditLog = None
    get_user_model = None


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
    EXTERNAL_REF_FETCH = "EXTERNAL_REF_FETCH"
    CACHE_HIT = "CACHE_HIT"
    CACHE_MISS = "CACHE_MISS"
    CACHE_EVICTION = "CACHE_EVICTION"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


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

    Also persists security events to the database for compliance and querying.
    """

    def __init__(self):
        """Initialize security logger"""
        self.logger = structlog.get_logger(__name__)
        self._persist_to_db = DJANGO_AVAILABLE and SecurityAuditLog is not None

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

        # Persist to database
        self._persist_security_violation(violation_log)

        # Detect security incidents
        try:
            incident_detector = get_incident_detector()
            incident = incident_detector.detect_incidents_from_violation(violation_log)
            if incident:
                self.logger.info(
                    "odps_security_incident_created",
                    incident_id=str(incident.id),
                    event_type=violation_log.event_type,
                    severity=incident.severity,
                    message="Security incident created from violation"
                )
        except Exception as e:
            # Don't fail on incident detection errors - logging is more important
            self.logger.warning(
                "odps_security_incident_detection_failed",
                error=str(e),
                event_type=violation_log.event_type,
                message="Failed to detect security incident (non-critical)"
            )

        return violation_log

    def _persist_security_violation(self, violation_log: SecurityViolationLog) -> None:
        """Persist security violation to database."""
        if not self._persist_to_db:
            return

        try:
            from django.db import transaction

            with transaction.atomic():
                self._persist_security_violation_inner(violation_log)
        except Exception as e:
            logger.warning(
                "odps_security_audit_persistence_failed",
                error=str(e),
                event_type=violation_log.event_type,
                message="Failed to persist security violation to database (non-critical)"
            )

    def _persist_security_violation_inner(self, violation_log: SecurityViolationLog) -> None:
        """Inner persistence logic; runs inside savepoint."""
        from hub.apps.tenants.models import Tenant

        tenant = None
        if violation_log.tenant_id:
            try:
                tenant = Tenant.objects.get(id=violation_log.tenant_id)
            except (Tenant.DoesNotExist, Exception):
                pass

        user = None
        if violation_log.user_id and get_user_model:
            try:
                User = get_user_model()
                user = User.objects.get(id=violation_log.user_id)
            except Exception:
                pass

        SecurityAuditLog.objects.create(
            event_type=violation_log.event_type,
            severity=violation_log.severity,
            tenant=tenant,
            user=user,
            ref_path=violation_log.attempted_path or violation_log.attempted_url,
            attempted_path=violation_log.attempted_path,
            attempted_url=violation_log.attempted_url,
            violation_type=violation_log.violation_type,
            description=violation_log.description,
            request_id=violation_log.request_id,
            ip_address=violation_log.ip_address,
            user_agent=violation_log.user_agent,
            metadata_json=violation_log.metadata or {},
        )

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

        # Persist to database
        self._persist_ref_resolution_audit(audit_log)

        return audit_log

    def _persist_ref_resolution_audit(self, audit_log: RefResolutionAuditLog) -> None:
        """Persist ref resolution audit to database."""
        if not self._persist_to_db:
            return

        try:
            from django.db import transaction

            with transaction.atomic():
                self._persist_ref_resolution_audit_inner(audit_log)
        except Exception as e:
            logger.warning(
                "odps_ref_resolution_audit_persistence_failed",
                error=str(e),
                operation_id=audit_log.operation_id,
                message="Failed to persist ref resolution audit to database (non-critical)"
            )

    def _persist_ref_resolution_audit_inner(self, audit_log: RefResolutionAuditLog) -> None:
        """Inner ref resolution audit persistence; runs inside savepoint."""
        from hub.apps.tenants.models import Tenant

        tenant = None
        if audit_log.tenant_id:
            try:
                tenant = Tenant.objects.get(id=audit_log.tenant_id)
            except (Tenant.DoesNotExist, Exception):
                pass

        user = None
        if audit_log.user_id and get_user_model:
            try:
                User = get_user_model()
                user = User.objects.get(id=audit_log.user_id)
            except Exception:
                pass

        SecurityAuditLog.objects.create(
            event_type="REF_RESOLUTION_AUDIT",
            tenant=tenant,
            user=user,
            ref_type=audit_log.ref_type,
            ref_path=audit_log.ref_path,
            resolved_path=audit_log.resolved_path,
            description=f"Ref resolution: {audit_log.ref_type} - {'success' if audit_log.success else 'failure'}",
            metadata_json={
                "operation_id": audit_log.operation_id,
                "success": audit_log.success,
                "duration_ms": audit_log.duration_ms,
                "error_type": audit_log.error_type,
                "error_message": audit_log.error_message,
                "security_checks_passed": audit_log.security_checks_passed,
                "security_violations": audit_log.security_violations,
                "size_bytes": audit_log.size_bytes,
                "cache_hit": audit_log.cache_hit,
                **(audit_log.metadata or {}),
            },
        )

    def log_external_ref_fetch(
        self,
        ref_path: str,
        success: bool,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        contract_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        size_bytes: Optional[int] = None,
        cache_hit: Optional[bool] = None,
        error_message: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log external $ref fetch event.

        Args:
            ref_path: External $ref URL
            success: Whether fetch succeeded
            tenant_id: Tenant ID
            user_id: User ID
            contract_id: Contract ID
            duration_ms: Fetch duration in milliseconds
            size_bytes: Size of fetched content
            cache_hit: Whether result came from cache
            error_message: Error message if failed
            request_id: Request ID for tracing
            ip_address: IP address
            user_agent: User agent string
            metadata: Additional metadata
        """
        # Log to structured logs
        self.logger.info(
            "odps_external_ref_fetch",
            ref_path=ref_path,
            success=success,
            tenant_id=tenant_id,
            user_id=user_id,
            cache_hit=cache_hit,
            duration_ms=duration_ms,
            size_bytes=size_bytes,
        )

        # Persist to database
        if not self._persist_to_db:
            return

        try:
            from hub.apps.tenants.models import Tenant

            tenant = None
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                except (User.DoesNotExist, Exception):
                    pass

            SecurityAuditLog.objects.create(
                event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
                tenant=tenant,
                user=user,
                ref_type="external",
                ref_path=ref_path,
                resolved_path=ref_path if success else None,
                description=f"External $ref fetch: {'success' if success else 'failed'} - {ref_path}",
                metadata_json={
                    "success": success,
                    "duration_ms": duration_ms,
                    "size_bytes": size_bytes,
                    "cache_hit": cache_hit,
                    "error_message": error_message,
                    **(metadata or {}),
                },
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.warning(
                "odps_external_ref_fetch_persistence_failed",
                error=str(e),
                ref_path=ref_path,
                message="Failed to persist external ref fetch to database (non-critical)"
            )

    def log_rate_limit_violation(
        self,
        level: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ref_path: Optional[str] = None,
        retry_after: Optional[float] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log rate limit violation event.

        Args:
            level: Rate limit level (global, tenant, user)
            tenant_id: Tenant ID
            user_id: User ID
            ref_path: $ref path that triggered violation
            retry_after: Retry after timestamp
            request_id: Request ID for tracing
            ip_address: IP address
            user_agent: User agent string
            metadata: Additional metadata
        """
        # Log to structured logs (also logged via log_security_violation, but this is explicit)
        self.logger.warning(
            "odps_rate_limit_violation",
            level=level,
            tenant_id=tenant_id,
            user_id=user_id,
            ref_path=ref_path,
            retry_after=retry_after,
        )

        # Persist to database
        if not self._persist_to_db:
            return

        try:
            from hub.apps.tenants.models import Tenant

            tenant = None
            if tenant_id:
                try:
                    tenant = Tenant.objects.get(id=tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=user_id)
                except (User.DoesNotExist, Exception):
                    pass

            SecurityAuditLog.objects.create(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                severity=SecuritySeverity.MEDIUM.value,
                tenant=tenant,
                user=user,
                ref_path=ref_path,
                rate_limit_level=level,
                description=f"Rate limit exceeded at {level} level",
                metadata_json={
                    "retry_after": retry_after,
                    **(metadata or {}),
                },
                request_id=request_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.warning(
                "odps_rate_limit_violation_persistence_failed",
                error=str(e),
                level=level,
                message="Failed to persist rate limit violation to database (non-critical)"
            )

    def log_cache_operation(
        self,
        operation: str,  # "hit", "miss", "eviction"
        ref_path: Optional[str] = None,
        cache_key: Optional[str] = None,
        eviction_reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log cache operation event.

        Args:
            operation: Cache operation type (hit, miss, eviction)
            ref_path: $ref path
            cache_key: Cache key
            eviction_reason: Eviction reason (for evictions)
            tenant_id: Tenant ID
            user_id: User ID
            metadata: Additional metadata
        """
        # Map operation to event type
        event_type_map = {
            "hit": SecurityEventType.CACHE_HIT,
            "miss": SecurityEventType.CACHE_MISS,
            "eviction": SecurityEventType.CACHE_EVICTION,
        }
        event_type = event_type_map.get(operation.lower())
        if not event_type:
            return

        # Log to structured logs
        self.logger.debug(
            "odps_cache_operation",
            operation=operation,
            ref_path=ref_path,
            cache_key=cache_key,
            eviction_reason=eviction_reason,
        )

        # Persist to database (savepoint isolates failures from caller's transaction)
        if not self._persist_to_db:
            return

        try:
            from django.db import transaction

            with transaction.atomic():
                self._persist_cache_operation_inner(
                    event_type, tenant_id, user_id, ref_path,
                    operation, cache_key, eviction_reason, metadata
                )
        except Exception as e:
            logger.warning(
                "odps_cache_operation_persistence_failed",
                error=str(e),
                operation=operation,
                message="Failed to persist cache operation to database (non-critical)"
            )

    def _persist_cache_operation_inner(
        self, event_type, tenant_id, user_id, ref_path,
        operation, cache_key, eviction_reason, metadata
    ) -> None:
        """Inner cache operation persistence; runs inside savepoint."""
        from hub.apps.tenants.models import Tenant

        tenant = None
        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except (Tenant.DoesNotExist, Exception):
                pass

        user = None
        if user_id and get_user_model:
            try:
                User = get_user_model()
                user = User.objects.get(id=user_id)
            except Exception:
                pass

        SecurityAuditLog.objects.create(
            event_type=event_type.value,
            tenant=tenant,
            user=user,
            ref_path=ref_path,
            cache_operation=operation.lower(),
            cache_key=cache_key,
            eviction_reason=eviction_reason,
            description=f"Cache {operation}: {ref_path or cache_key}",
            metadata_json=metadata or {},
        )


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


def _scope_audit_query_by_participants(query, tenant_obj: Optional[Any], user_obj: Optional[Any]):
    """Restrict SecurityAuditLog aggregation to the same tenant/user bucket.

    If we only filter when tenant/user is set, violations with NULL tenant/user
    count *every* row of that event_type in the database — including unrelated
    tenants and other tests — which mis-triggers incidents.
    Match NULL explicitly when the violation is unscoped.
    """
    if tenant_obj is not None:
        query = query.filter(tenant=tenant_obj)
    else:
        query = query.filter(tenant__isnull=True)
    if user_obj is not None:
        query = query.filter(user=user_obj)
    else:
        query = query.filter(user__isnull=True)
    return query


def _scope_incident_query_by_participants(query, tenant_obj: Optional[Any], user_obj: Optional[Any]):
    """Same participant scoping for SecurityIncident lookups."""
    if tenant_obj is not None:
        query = query.filter(tenant=tenant_obj)
    else:
        query = query.filter(tenant__isnull=True)
    if user_obj is not None:
        query = query.filter(user=user_obj)
    else:
        query = query.filter(user__isnull=True)
    return query


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


class SecurityIncidentDetector:
    """
    Detects security incidents from security violations and suspicious patterns.

    Analyzes security audit logs to identify patterns that indicate security incidents
    requiring investigation and response.
    """

    def __init__(self):
        """Initialize security incident detector"""
        self.logger = structlog.get_logger(__name__)

    def detect_incidents_from_violation(
        self,
        violation_log: SecurityViolationLog
    ) -> Optional[Any]:
        """
        Detect security incidents from a security violation log.

        Args:
            violation_log: Security violation log to analyze

        Returns:
            SecurityIncident instance if incident detected, None otherwise
        """
        if not DJANGO_AVAILABLE:
            return None

        try:
            from hub.apps.contracts.models import SecurityIncident, SecurityAuditLog
            from django.utils import timezone
            from datetime import timedelta

            # Check for suspicious patterns
            incident = None

            # Pattern 1: Excessive rate limit violations
            if violation_log.event_type == SecurityEventType.RATE_LIMIT_EXCEEDED.value:
                incident = self._detect_rate_limit_abuse(violation_log)

            # Pattern 2: Path traversal attempts
            elif violation_log.event_type == SecurityEventType.PATH_TRAVERSAL.value:
                incident = self._detect_path_traversal_pattern(violation_log)

            # Pattern 3: URL validation failures
            elif violation_log.event_type in [
                SecurityEventType.URL_DENIED.value,
                SecurityEventType.URL_NOT_ALLOWED.value,
                SecurityEventType.INVALID_URL.value
            ]:
                incident = self._detect_url_violation_pattern(violation_log)

            # Pattern 4: High severity violations
            elif violation_log.severity in [SecuritySeverity.HIGH.value, SecuritySeverity.CRITICAL.value]:
                incident = self._detect_high_severity_violation(violation_log)

            if incident:
                # Link related audit log if available
                try:
                    from hub.apps.tenants.models import Tenant
                    query = SecurityAuditLog.objects.filter(
                        event_type=violation_log.event_type,
                        timestamp__gte=timezone.now() - timedelta(minutes=5)
                    )
                    if violation_log.tenant_id:
                        try:
                            tenant = Tenant.objects.get(id=violation_log.tenant_id)
                            query = query.filter(tenant=tenant)
                        except Tenant.DoesNotExist:
                            pass
                    if violation_log.user_id and get_user_model:
                        try:
                            User = get_user_model()
                            user = User.objects.get(id=violation_log.user_id)
                            query = query.filter(user=user)
                        except Exception:
                            pass
                    audit_log = query.order_by('-timestamp').first()
                    if audit_log:
                        incident.related_audit_logs.add(audit_log)
                except Exception as e:
                    self.logger.warning(
                        "odps_security_incident_link_failed",
                        error=str(e),
                        incident_id=str(incident.id),
                        message="Failed to link audit log to incident"
                    )

            return incident

        except Exception as e:
            self.logger.warning(
                "odps_security_incident_detection_failed",
                error=str(e),
                event_type=violation_log.event_type,
                message="Failed to detect security incident"
            )
            return None

    def _detect_rate_limit_abuse(self, violation_log: SecurityViolationLog) -> Optional[Any]:
        """Detect rate limit abuse pattern."""
        if not DJANGO_AVAILABLE:
            return None

        try:
            from hub.apps.contracts.models import SecurityIncident, SecurityAuditLog
            from hub.apps.tenants.models import Tenant
            from django.utils import timezone
            from datetime import timedelta

            # Get tenant and user objects
            tenant = None
            if violation_log.tenant_id:
                try:
                    tenant = Tenant.objects.get(id=violation_log.tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if violation_log.user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=violation_log.user_id)
                except Exception:
                    pass

            # Check for excessive rate limit violations in last hour
            window_start = timezone.now() - timedelta(hours=1)
            query = SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                timestamp__gte=window_start
            )
            query = _scope_audit_query_by_participants(query, tenant, user)
            violation_count = query.count()

            # Threshold: 10 violations per hour
            if violation_count >= 10:
                # Check if incident already exists
                existing_query = SecurityIncident.objects.filter(
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                    status__in=["OPEN", "INVESTIGATING"],
                    first_detected_at__gte=window_start
                )
                existing_query = _scope_incident_query_by_participants(
                    existing_query, tenant, user
                )
                existing_incident = existing_query.first()

                if existing_incident:
                    # Update existing incident
                    existing_incident.violation_count = violation_count
                    existing_incident.last_updated_at = timezone.now()
                    existing_incident.save()
                    return existing_incident

                # Create new incident
                severity = SecuritySeverity.CRITICAL if violation_count >= 50 else SecuritySeverity.HIGH
                incident = SecurityIncident.objects.create(
                    title=f"Excessive Rate Limit Violations - {tenant.name if tenant else 'System'}",
                    description=f"Detected {violation_count} rate limit violations in the last hour. "
                              f"Level: {violation_log.metadata.get('level', 'unknown') if violation_log.metadata else 'unknown'}",
                    severity=severity.value,
                    status="OPEN",
                    tenant=tenant,
                    user=user,
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                    violation_count=violation_count,
                    metadata_json={
                        "level": violation_log.metadata.get('level', 'unknown') if violation_log.metadata else 'unknown',
                        "window_hours": 1,
                        "threshold": 10
                    }
                )

                self.logger.warning(
                    "odps_security_incident_detected",
                    incident_id=str(incident.id),
                    event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                    severity=severity.value,
                    violation_count=violation_count,
                    message="Security incident detected: excessive rate limit violations"
                )

                return incident

        except Exception as e:
            self.logger.warning(
                "odps_security_incident_detection_error",
                error=str(e),
                pattern="rate_limit_abuse",
                message="Failed to detect rate limit abuse pattern"
            )

        return None

    def _detect_path_traversal_pattern(self, violation_log: SecurityViolationLog) -> Optional[Any]:
        """Detect path traversal attack pattern."""
        if not DJANGO_AVAILABLE:
            return None

        try:
            from hub.apps.contracts.models import SecurityIncident, SecurityAuditLog
            from hub.apps.tenants.models import Tenant
            from django.utils import timezone
            from datetime import timedelta

            # Get tenant and user objects
            tenant = None
            if violation_log.tenant_id:
                try:
                    tenant = Tenant.objects.get(id=violation_log.tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if violation_log.user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=violation_log.user_id)
                except Exception:
                    pass

            # Check for multiple path traversal attempts in last 5 minutes
            window_start = timezone.now() - timedelta(minutes=5)
            query = SecurityAuditLog.objects.filter(
                event_type=SecurityEventType.PATH_TRAVERSAL.value,
                timestamp__gte=window_start
            )
            query = _scope_audit_query_by_participants(query, tenant, user)
            violation_count = query.count()

            # Threshold: 5 path traversal attempts in 5 minutes
            if violation_count >= 5:
                existing_query = SecurityIncident.objects.filter(
                    event_type=SecurityEventType.PATH_TRAVERSAL.value,
                    status__in=["OPEN", "INVESTIGATING"],
                    first_detected_at__gte=window_start
                )
                existing_query = _scope_incident_query_by_participants(
                    existing_query, tenant, user
                )
                existing_incident = existing_query.first()

                if existing_incident:
                    existing_incident.violation_count = violation_count
                    existing_incident.last_updated_at = timezone.now()
                    existing_incident.save()
                    return existing_incident

                incident = SecurityIncident.objects.create(
                    title=f"Path Traversal Attack Attempt - {tenant.name if tenant else 'System'}",
                    description=f"Detected {violation_count} path traversal attempts in the last 5 minutes. "
                              f"Attempted path: {violation_log.attempted_path}",
                    severity=SecuritySeverity.HIGH.value,
                    status="OPEN",
                    tenant=tenant,
                    user=user,
                    event_type=SecurityEventType.PATH_TRAVERSAL.value,
                    violation_count=violation_count,
                    metadata_json={
                        "attempted_path": violation_log.attempted_path,
                        "window_minutes": 5,
                        "threshold": 5
                    }
                )

                self.logger.warning(
                    "odps_security_incident_detected",
                    incident_id=str(incident.id),
                    event_type=SecurityEventType.PATH_TRAVERSAL.value,
                    severity=SecuritySeverity.HIGH.value,
                    violation_count=violation_count,
                    message="Security incident detected: path traversal attack pattern"
                )

                return incident

        except Exception as e:
            self.logger.warning(
                "odps_security_incident_detection_error",
                error=str(e),
                pattern="path_traversal",
                message="Failed to detect path traversal pattern"
            )

        return None

    def _detect_url_violation_pattern(self, violation_log: SecurityViolationLog) -> Optional[Any]:
        """Detect URL violation pattern."""
        if not DJANGO_AVAILABLE:
            return None

        # LOW = format / validation noise; pattern-based incidents target repeat abuse
        # (MEDIUM+). Skipping avoids false positives when many anonymous LOW rows exist
        # in shared environments and matches observability intent for this detector.
        if violation_log.severity == SecuritySeverity.LOW.value:
            return None

        try:
            from hub.apps.contracts.models import SecurityIncident, SecurityAuditLog
            from hub.apps.tenants.models import Tenant
            from django.utils import timezone
            from datetime import timedelta

            # Get tenant and user objects
            tenant = None
            if violation_log.tenant_id:
                try:
                    tenant = Tenant.objects.get(id=violation_log.tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if violation_log.user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=violation_log.user_id)
                except Exception:
                    pass

            # Check for multiple URL violations in last 10 minutes.
            # Omit LOW from the rolling count: format-validation noise should not
            # share the same incident threshold as MEDIUM/HIGH URL abuse, and test
            # DBs accumulate many unscoped LOW rows without tenant context.
            window_start = timezone.now() - timedelta(minutes=10)
            query = SecurityAuditLog.objects.filter(
                event_type=violation_log.event_type,
                timestamp__gte=window_start,
            ).exclude(severity=SecuritySeverity.LOW.value)
            query = _scope_audit_query_by_participants(query, tenant, user)
            violation_count = query.count()

            # Threshold: 3 non-LOW URL violations in 10 minutes
            if violation_count >= 3:
                existing_query = SecurityIncident.objects.filter(
                    event_type=violation_log.event_type,
                    status__in=["OPEN", "INVESTIGATING"],
                    first_detected_at__gte=window_start
                )
                existing_query = _scope_incident_query_by_participants(
                    existing_query, tenant, user
                )
                existing_incident = existing_query.first()

                if existing_incident:
                    existing_incident.violation_count = violation_count
                    existing_incident.last_updated_at = timezone.now()
                    existing_incident.save()
                    return existing_incident

                incident = SecurityIncident.objects.create(
                    title=f"URL Validation Violations - {tenant.name if tenant else 'System'}",
                    description=f"Detected {violation_count} URL validation violations in the last 10 minutes. "
                              f"Type: {violation_log.event_type}, Attempted URL: {violation_log.attempted_url}",
                    severity=SecuritySeverity.HIGH.value,
                    status="OPEN",
                    tenant=tenant,
                    user=user,
                    event_type=violation_log.event_type,
                    violation_count=violation_count,
                    metadata_json={
                        "attempted_url": violation_log.attempted_url,
                        "window_minutes": 10,
                        "threshold": 3
                    }
                )

                self.logger.warning(
                    "odps_security_incident_detected",
                    incident_id=str(incident.id),
                    event_type=violation_log.event_type,
                    severity=SecuritySeverity.HIGH.value,
                    violation_count=violation_count,
                    message="Security incident detected: URL validation violation pattern"
                )

                return incident

        except Exception as e:
            self.logger.warning(
                "odps_security_incident_detection_error",
                error=str(e),
                pattern="url_violation",
                message="Failed to detect URL violation pattern"
            )

        return None

    def _detect_high_severity_violation(self, violation_log: SecurityViolationLog) -> Optional[Any]:
        """Detect high severity violation pattern."""
        if not DJANGO_AVAILABLE:
            return None

        try:
            from hub.apps.contracts.models import SecurityIncident, SecurityAuditLog
            from hub.apps.tenants.models import Tenant
            from django.utils import timezone
            from datetime import timedelta

            # Get tenant and user objects
            tenant = None
            if violation_log.tenant_id:
                try:
                    tenant = Tenant.objects.get(id=violation_log.tenant_id)
                except Tenant.DoesNotExist:
                    pass

            user = None
            if violation_log.user_id and get_user_model:
                try:
                    User = get_user_model()
                    user = User.objects.get(id=violation_log.user_id)
                except Exception:
                    pass

            # Check for multiple high severity violations in last hour
            window_start = timezone.now() - timedelta(hours=1)
            query = SecurityAuditLog.objects.filter(
                severity__in=[SecuritySeverity.HIGH.value, SecuritySeverity.CRITICAL.value],
                timestamp__gte=window_start
            )
            query = _scope_audit_query_by_participants(query, tenant, user)
            violation_count = query.count()

            # Threshold: 10 high severity violations per hour
            if violation_count >= 10:
                existing_query = SecurityIncident.objects.filter(
                    severity__in=[SecuritySeverity.HIGH.value, SecuritySeverity.CRITICAL.value],
                    status__in=["OPEN", "INVESTIGATING"],
                    first_detected_at__gte=window_start
                )
                existing_query = _scope_incident_query_by_participants(
                    existing_query, tenant, user
                )
                existing_incident = existing_query.first()

                if existing_incident:
                    existing_incident.violation_count = violation_count
                    existing_incident.last_updated_at = timezone.now()
                    existing_incident.save()
                    return existing_incident

                incident = SecurityIncident.objects.create(
                    title=f"Multiple High Severity Violations - {tenant.name if tenant else 'System'}",
                    description=f"Detected {violation_count} high severity security violations in the last hour. "
                              f"Event type: {violation_log.event_type}",
                    severity=SecuritySeverity.CRITICAL.value,
                    status="OPEN",
                    tenant=tenant,
                    user=user,
                    event_type=violation_log.event_type,
                    violation_count=violation_count,
                    metadata_json={
                        "window_hours": 1,
                        "threshold": 10
                    }
                )

                self.logger.warning(
                    "odps_security_incident_detected",
                    incident_id=str(incident.id),
                    event_type=violation_log.event_type,
                    severity=SecuritySeverity.CRITICAL.value,
                    violation_count=violation_count,
                    message="Security incident detected: multiple high severity violations"
                )

                return incident

        except Exception as e:
            self.logger.warning(
                "odps_security_incident_detection_error",
                error=str(e),
                pattern="high_severity",
                message="Failed to detect high severity violation pattern"
            )

        return None


# Global incident detector instance
_incident_detector: Optional[SecurityIncidentDetector] = None


def get_incident_detector() -> SecurityIncidentDetector:
    """
    Get the global security incident detector instance.

    Returns:
        SecurityIncidentDetector instance
    """
    global _incident_detector
    if _incident_detector is None:
        _incident_detector = SecurityIncidentDetector()
    return _incident_detector

