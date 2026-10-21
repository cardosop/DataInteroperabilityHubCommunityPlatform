# ODPS $ref Resolver Security Logging and Monitoring

This document describes the security logging and monitoring implementation for ODPS $ref resolution.

## Overview

The security logging system provides:
- **Structured security violation logging** with security tags for filtering
- **Complete audit trails** for all $ref resolution operations
- **Alert rules** for detecting suspicious patterns
- **Integration** with existing structlog infrastructure

## Security Violation Log Format

Security violations are logged using structured logs with consistent format:

```python
{
    "security_event": true,
    "security_type": "PATH_TRAVERSAL",
    "security_severity": "HIGH",
    "event_type": "PATH_TRAVERSAL",
    "severity": "HIGH",
    "timestamp": "2025-12-19T17:00:00.000000+00:00",
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "660e8400-e29b-41d4-a716-446655440001",
    "contract_id": "770e8400-e29b-41d4-a716-446655440002",
    "violation_type": "Path Traversal Attempt",
    "description": "Attempted to access file outside allowed directories",
    "attempted_path": "../../../etc/passwd",
    "allowed_dirs": ["./contracts/refs", "./odps-refs"],
    "request_id": "req-12345",
    "ip_address": "192.168.1.100"
}
```

### Security Event Types

- `PATH_TRAVERSAL`: Attempted path traversal attack
- `URL_DENIED`: External URL denied by denylist
- `URL_NOT_ALLOWED`: External URL not in allowlist
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `SIZE_LIMIT_EXCEEDED`: File size limit exceeded
- `TIMEOUT`: Request timeout
- `INVALID_URL`: Invalid URL format
- `SUSPICIOUS_PATTERN`: Suspicious activity pattern detected

### Security Severity Levels

- `LOW`: Informational security events
- `MEDIUM`: Moderate security concerns
- `HIGH`: High-priority security violations
- `CRITICAL`: Critical security threats requiring immediate attention

### Log Levels

Security violations are logged at different levels based on severity:
- `CRITICAL` → `logger.error()`
- `HIGH` → `logger.warning()`
- `MEDIUM` → `logger.warning()`
- `LOW` → `logger.info()`

## Audit Trail Format

All $ref resolution operations are logged in audit trail format:

```python
{
    "audit_event": true,
    "audit_type": "ref_resolution",
    "operation_id": "op-12345",
    "timestamp": "2025-12-19T17:00:00.000000+00:00",
    "duration_ms": 125.5,
    "tenant_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "660e8400-e29b-41d4-a716-446655440001",
    "contract_id": "770e8400-e29b-41d4-a716-446655440002",
    "ref_type": "external",
    "ref_path": "https://example.com/schema.yaml",
    "resolved_path": "https://example.com/schema.yaml",
    "success": true,
    "security_checks_passed": true,
    "size_bytes": 1024,
    "cache_hit": false
}
```

### Audit Trail Fields

- `operation_id`: Unique identifier for the operation
- `timestamp`: ISO 8601 timestamp with timezone
- `duration_ms`: Operation duration in milliseconds
- `ref_type`: Type of reference ("internal", "local", or "external")
- `ref_path`: The $ref path/value
- `resolved_path`: Resolved path/URL (if successful)
- `success`: Whether resolution succeeded
- `error_type`: Error type if failed
- `error_message`: Error message if failed
- `security_checks_passed`: Whether security checks passed
- `security_violations`: List of security violations (if any)
- `size_bytes`: Size of resolved content
- `cache_hit`: Whether result came from cache

## Alert Rules

Alert rules define patterns that trigger alerts when matched within a time window.

### Default Alert Rules

1. **Multiple Path Traversals**
   - Pattern: `event_type:PATH_TRAVERSAL`
   - Threshold: 5 events
   - Window: 5 minutes
   - Severity: HIGH
   - Description: Multiple path traversal attempts within short time window

2. **Rate Limit Abuse**
   - Pattern: `event_type:RATE_LIMIT_EXCEEDED`
   - Threshold: 10 events
   - Window: 1 hour
   - Severity: MEDIUM
   - Description: Repeated rate limit violations

3. **Suspicious URL Patterns**
   - Pattern: `event_type:URL_DENIED`
   - Threshold: 3 events
   - Window: 10 minutes
   - Severity: HIGH
   - Description: Multiple attempts to access denied URLs

4. **Tenant Security Issues**
   - Pattern: `event_type:PATH_TRAVERSAL,tenant_id:*`
   - Threshold: 10 events
   - Window: 1 hour
   - Severity: CRITICAL
   - Description: High number of security violations from a single tenant

### Alert Rule Pattern Format

Patterns use key-value pairs separated by commas:
- `event_type:EVENT_TYPE` - Match specific event type
- `tenant_id:TENANT_ID` - Match specific tenant
- `user_id:USER_ID` - Match specific user
- `*` - Wildcard (matches any value)

## Usage

### Logging Security Violations

```python
from hub.apps.contracts.odps_security_logging import (
    get_security_logger,
    SecurityEventType,
    SecuritySeverity
)

security_logger = get_security_logger()

# Log a path traversal attempt
security_logger.log_security_violation(
    event_type=SecurityEventType.PATH_TRAVERSAL,
    severity=SecuritySeverity.HIGH,
    violation_type="Path Traversal Attempt",
    description="Attempted to access file outside allowed directories",
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    user_id="660e8400-e29b-41d4-a716-446655440001",
    attempted_path="../../../etc/passwd",
    allowed_dirs=["./contracts/refs", "./odps-refs"],
    ip_address="192.168.1.100"
)

# Log a URL denial
security_logger.log_security_violation(
    event_type=SecurityEventType.URL_DENIED,
    severity=SecuritySeverity.MEDIUM,
    violation_type="URL Denied by Denylist",
    description="Attempted to access URL that is in denylist",
    attempted_url="https://malicious.com/schema.yaml",
    url_pattern="https://*.malicious.com"
)
```

### Logging Audit Trails

```python
from hub.apps.contracts.odps_security_logging import get_security_logger
import uuid
import time

security_logger = get_security_logger()

# Log successful resolution
start_time = time.time()
# ... perform resolution ...
duration_ms = (time.time() - start_time) * 1000

security_logger.log_ref_resolution_audit(
    operation_id=str(uuid.uuid4()),
    ref_type="external",
    ref_path="https://example.com/schema.yaml",
    success=True,
    duration_ms=duration_ms,
    tenant_id="550e8400-e29b-41d4-a716-446655440000",
    user_id="660e8400-e29b-41d4-a716-446655440001",
    resolved_path="https://example.com/schema.yaml",
    size_bytes=1024,
    cache_hit=False
)

# Log failed resolution
security_logger.log_ref_resolution_audit(
    operation_id=str(uuid.uuid4()),
    ref_type="local",
    ref_path="./schema.yaml",
    success=False,
    duration_ms=50.0,
    error_type="FileNotFoundError",
    error_message="File not found: ./schema.yaml",
    security_checks_passed=True
)
```

### Using Alert Rules

```python
from hub.apps.contracts.odps_security_logging import (
    SecurityAlertRule,
    SecuritySeverity,
    SecurityViolationLog,
    SecurityEventType
)

# Create custom alert rule
custom_rule = SecurityAlertRule(
    name="custom_suspicious_pattern",
    pattern="event_type:URL_DENIED,tenant_id:550e8400-e29b-41d4-a716-446655440000",
    threshold=5,
    window_seconds=300,
    severity=SecuritySeverity.HIGH,
    description="Multiple denied URLs from specific tenant"
)

# Check if event matches rule
violation_log = SecurityViolationLog(
    event_type=SecurityEventType.URL_DENIED.value,
    severity=SecuritySeverity.MEDIUM.value,
    timestamp="2025-12-19T17:00:00.000000+00:00",
    violation_type="URL Denied",
    description="Test",
    tenant_id="550e8400-e29b-41d4-a716-446655440000"
)

if custom_rule.matches(violation_log):
    # Trigger alert
    pass
```

## Integration with Monitoring Systems

### Log Filtering

Security events can be filtered using the security tags:

```python
# Filter for all security events
security_events = filter(lambda log: log.get('security_event') == True, logs)

# Filter for critical security events
critical_events = filter(
    lambda log: log.get('security_severity') == 'CRITICAL',
    logs
)

# Filter for path traversal events
path_traversal_events = filter(
    lambda log: log.get('security_type') == 'PATH_TRAVERSAL',
    logs
)
```

### Audit Trail Queries

Audit trails can be queried for compliance and debugging:

```python
# Filter for all audit events
audit_events = filter(lambda log: log.get('audit_event') == True, logs)

# Filter for failed resolutions
failed_resolutions = filter(
    lambda log: log.get('audit_type') == 'ref_resolution' and log.get('success') == False,
    logs
)

# Filter for external ref resolutions
external_refs = filter(
    lambda log: log.get('ref_type') == 'external',
    logs
)
```

## Best Practices

1. **Always log security violations** - Even if the violation is blocked, log it for monitoring
2. **Include context** - Provide tenant_id, user_id, and request_id when available
3. **Use appropriate severity** - Match severity to the actual threat level
4. **Monitor alert rules** - Set up monitoring for alert rule triggers
5. **Review audit trails regularly** - Use audit trails for compliance and debugging
6. **Protect sensitive data** - Don't log sensitive content, only metadata

## Security Considerations

- **Log retention**: Security logs should be retained according to compliance requirements
- **Log access**: Limit access to security logs to authorized personnel only
- **Log integrity**: Ensure logs cannot be tampered with
- **PII handling**: Be careful not to log personally identifiable information unnecessarily
- **Rate limiting**: Consider rate limiting log generation to prevent log flooding

## Troubleshooting

### Logs Not Appearing

1. Check structlog configuration
2. Verify logger is initialized correctly
3. Check log level settings
4. Verify security logger instance is being used

### Alert Rules Not Triggering

1. Verify rule patterns match event format
2. Check threshold and window settings
3. Ensure events are being logged correctly
4. Verify alert rule matching logic

### Performance Impact

1. Security logging is designed to be lightweight
2. Use async logging if available
3. Consider batching logs for high-volume scenarios
4. Monitor logging performance metrics

