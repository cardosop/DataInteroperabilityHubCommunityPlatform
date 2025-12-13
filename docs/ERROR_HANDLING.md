# Error Handling Guide

Comprehensive guide for error handling including standardized error responses, enhanced error logging, Sentry integration, and error recovery mechanisms.

## Table of Contents

1. [Overview](#overview)
2. [Standardized Error Responses](#standardized-error-responses)
3. [Error Logging](#error-logging)
4. [Error Tracking (Sentry)](#error-tracking-sentry)
5. [Error Recovery](#error-recovery)
6. [Integration Examples](#integration-examples)
7. [Best Practices](#best-practices)

---

## Overview

The error handling module provides comprehensive tools for handling errors:

- **Standardized Error Responses**: Consistent error response format across all endpoints
- **Enhanced Error Logging**: Structured logging with full context
- **Error Tracking (Sentry)**: Automatic error tracking and monitoring
- **Error Recovery**: Retry logic and circuit breakers

### Module Location

All error handling functionality is in `hub.apps.core.error_handling`:

- `error_responses.py`: Standardized error response formatting
- `error_logging.py`: Enhanced error logging
- `error_tracking.py`: Sentry integration
- `error_recovery.py`: Retry logic and circuit breakers
- `middleware.py`: Error handling middleware

---

## Standardized Error Responses

### Overview

All error responses follow a consistent format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "http_status": 400,
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z",
    "details": {
      "field_errors": [
        {
          "field": "email",
          "message": "Invalid email format",
          "code": "VALIDATION_ERROR"
        }
      ]
    }
  }
}
```

### Usage

**ErrorResponse Class:**

```python
from hub.apps.core.error_handling.error_responses import ErrorResponse

error = ErrorResponse(
    code="VALIDATION_ERROR",
    message="Invalid input",
    http_status=400,
    details={"field": "email", "message": "Invalid email format"}
)

response = error.to_response()
return response
```

**ErrorResponseBuilder (Fluent Interface):**

```python
from hub.apps.core.error_handling.error_responses import ErrorResponseBuilder

error = (
    ErrorResponseBuilder()
    .code("VALIDATION_ERROR")
    .message("Validation failed")
    .http_status(400)
    .field_error("email", "Invalid email format")
    .field_error("password", "Password too short", "PASSWORD_TOO_SHORT")
    .request_id(request_id)
    .build()
)

return error.to_response()
```

**format_error_response Function:**

```python
from hub.apps.core.error_handling.error_responses import format_error_response

try:
    # Operation that might fail
    result = process_data(data)
except ValueError as e:
    return format_error_response(
        exception=e,
        code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
    )
```

**In DRF Views:**

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from hub.apps.core.error_handling.error_responses import format_error_response

class ContractViewSet(APIView):
    def create(self, request):
        try:
            contract = ContractService.create_contract(
                tenant_id=request.user.tenant_id,
                data=request.data
            )
            return Response({"id": str(contract.id)}, status=201)
        except ValidationError as e:
            return format_error_response(
                exception=e,
                code="VALIDATION_ERROR",
                http_status=400,
                request_id=request.id,
            )
```

### Error Codes

Standard error codes are defined in `hub.apps.api.standards.error_codes.StandardErrorCodes`:

- **Validation errors (400)**: `VALIDATION_ERROR`, `VALIDATION_FAILED`, `INVALID_INPUT`
- **Authentication errors (401)**: `AUTH_UNAUTHORIZED`, `AUTH_TOKEN_EXPIRED`
- **Authorization errors (403)**: `AUTH_FORBIDDEN`, `PERMISSION_DENIED`
- **Not found errors (404)**: `NOT_FOUND`, `RESOURCE_NOT_FOUND`
- **Conflict errors (409)**: `CONFLICT_ERROR`, `RESOURCE_CONFLICT`
- **Rate limiting (429)**: `RATE_LIMIT_EXCEEDED`
- **Server errors (500)**: `INTERNAL_ERROR`, `SERVER_ERROR`

---

## Error Logging

### Overview

Enhanced error logging provides structured logging with full context for debugging and monitoring.

### Usage

**ErrorLogger Class:**

```python
from hub.apps.core.error_handling.error_logging import ErrorLogger

logger = ErrorLogger()

try:
    # Operation that might fail
    result = process_data(data)
except ValueError as e:
    logger.log_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
        tenant_id=str(request.user.tenant_id),
        user_id=str(request.user.id),
        additional_context={
            "operation": "create_contract",
            "data_size": len(data),
        },
        level="error",
    )
```

**Convenience Functions:**

```python
from hub.apps.core.error_handling.error_logging import log_error, log_exception

try:
    result = process_data(data)
except ValueError as e:
    log_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
    )
```

**Specialized Logging Methods:**

```python
logger = ErrorLogger()

# Log validation error
logger.log_validation_error(
    field="email",
    message="Invalid email format",
    value="invalid-email",
    request_id=request.id,
    tenant_id=str(request.user.tenant_id),
)

# Log permission error
logger.log_permission_error(
    resource="asset",
    action="delete",
    user_id=str(request.user.id),
    tenant_id=str(request.user.tenant_id),
    request_id=request.id,
)

# Log not found error
logger.log_not_found_error(
    resource_type="asset",
    resource_id="asset-id",
    request_id=request.id,
    tenant_id=str(request.user.tenant_id),
)
```

### Log Context

All error logs include:
- **Error type**: Exception class name
- **Error code**: Machine-readable error code
- **Error message**: Human-readable message
- **Request ID**: Unique request identifier
- **Tenant ID**: Tenant identifier (if available)
- **User ID**: User identifier (if available)
- **Traceback**: Full stack trace (for errors)
- **Additional context**: Custom context fields

---

## Error Tracking (Sentry)

### Overview

Sentry integration provides automatic error tracking and monitoring with:
- Automatic exception capture
- User and tenant context
- PII redaction
- Performance monitoring
- Release tracking

### Setup

**1. Install Sentry SDK:**

```bash
pip install sentry-sdk
```

**2. Configure Environment Variables:**

```bash
export SENTRY_DSN="https://your-sentry-dsn@sentry.io/project-id"
export ENVIRONMENT="production"  # or "development", "staging"
export RELEASE_VERSION="1.0.0"  # Optional: release version
export SENTRY_TRACES_SAMPLE_RATE="0.1"  # Optional: trace sampling rate (0.0-1.0)
```

**3. Sentry is automatically initialized** when `ErrorTracker` is first used.

### Usage

**Automatic Tracking:**

Errors are automatically tracked in Sentry through:
- Exception handler integration (already configured)
- Error handling middleware (optional)

**Manual Tracking:**

```python
from hub.apps.core.error_handling.error_tracking import track_error, track_exception

try:
    result = process_data(data)
except ValueError as e:
    track_error(
        error=e,
        error_code="VALIDATION_ERROR",
        message="Invalid data",
        http_status=400,
        request_id=request.id,
        tenant_id=str(request.user.tenant_id),
        user_id=str(request.user.id),
        context={
            "operation": "create_contract",
            "data_size": len(data),
        },
    )
```

**Set User Context:**

```python
from hub.apps.core.error_handling.error_tracking import get_error_tracker

tracker = get_error_tracker()
tracker.set_user(user_id=str(request.user.id))
tracker.set_tenant(tenant_id=str(request.user.tenant_id))
```

**Track Messages:**

```python
from hub.apps.core.error_handling.error_tracking import get_error_tracker

tracker = get_error_tracker()
tracker.track_message(
    "Important event occurred",
    level="warning",
    context={"event_type": "data_quality_check"},
)
```

### PII Protection

Sentry automatically redacts PII:
- Email addresses
- Usernames
- Passwords
- Tokens
- API keys
- Other sensitive fields

### Configuration

Sentry is configured with:
- **Django Integration**: Automatic Django exception capture
- **Logging Integration**: Structured log capture
- **Redis Integration**: Redis error tracking
- **Trace Sampling**: Configurable performance monitoring
- **PII Redaction**: Automatic sensitive data removal

---

## Error Recovery

### Overview

Error recovery mechanisms provide resilience patterns:
- **Retry Logic**: Automatic retry with backoff strategies
- **Circuit Breakers**: Prevent cascading failures
- **Error Classification**: Determine if errors are retryable

### Retry Logic

**@with_retry Decorator:**

```python
from hub.apps.core.error_handling.error_recovery import (
    with_retry,
    RetryStrategy,
)

@with_retry(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=1.0,
    max_delay=60.0,
)
def fetch_external_data(url):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

**Retry Strategies:**

- **EXPONENTIAL_BACKOFF**: Delay = base_delay * (2 ^ attempt)
- **LINEAR_BACKOFF**: Delay = base_delay * (attempt + 1)
- **FIXED_DELAY**: Delay = base_delay (constant)
- **NO_RETRY**: No retry

**Custom Retryable Exceptions:**

```python
@with_retry(
    max_attempts=3,
    retryable_exceptions=[ConnectionError, TimeoutError],
    non_retryable_exceptions=[ValueError, TypeError],
)
def unreliable_operation():
    # Only retries on ConnectionError or TimeoutError
    pass
```

**Retry Callback:**

```python
def on_retry(exc, attempt):
    logger.warning(f"Retry attempt {attempt} after {exc}")

@with_retry(max_attempts=3, on_retry=on_retry)
def flaky_operation():
    pass
```

### Circuit Breakers

**@with_circuit_breaker Decorator:**

```python
from hub.apps.core.error_handling.error_recovery import with_circuit_breaker

@with_circuit_breaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
)
def call_external_service():
    # Automatically protected by circuit breaker
    response = requests.get("https://external-api.com/data")
    response.raise_for_status()
    return response.json()
```

**Circuit Breaker States:**

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures, requests rejected immediately
- **HALF_OPEN**: Testing if service recovered, allows limited requests

**Manual Circuit Breaker:**

```python
from hub.apps.core.error_handling.error_recovery import CircuitBreaker

cb = CircuitBreaker(
    failure_threshold=5,
    success_threshold=2,
    timeout=60.0,
    name="external_api",
)

def call_external_service():
    return cb.call(lambda: requests.get("https://external-api.com/data"))
```

**Circuit Breaker Behavior:**

1. **CLOSED**: Requests pass through, failures counted
2. **After threshold failures**: Transitions to OPEN
3. **OPEN**: Requests rejected with `CircuitBreakerOpenError`
4. **After timeout**: Transitions to HALF_OPEN
5. **HALF_OPEN**: Allows requests, counts successes/failures
6. **After success threshold**: Transitions to CLOSED
7. **On failure in HALF_OPEN**: Transitions back to OPEN

### Error Classification

**Determine if Error is Retryable:**

```python
from hub.apps.core.error_handling.error_recovery import ErrorRecovery

try:
    result = unreliable_operation()
except Exception as e:
    if ErrorRecovery.should_retry(e):
        # Retry logic
        pass
    else:
        # Don't retry
        raise
```

**Default Retryable Exceptions:**
- `ConnectionError`
- `TimeoutError`
- `OSError` (network errors)

**Default Non-Retryable Exceptions:**
- `ValueError`
- `TypeError`
- `AttributeError`

---

## Integration Examples

### Complete Example: API View with Error Handling

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from hub.apps.core.error_handling.error_responses import format_error_response
from hub.apps.core.error_handling.error_logging import log_error
from hub.apps.core.error_handling.error_tracking import track_error
from hub.apps.core.error_handling.error_recovery import with_retry, RetryStrategy

class ContractViewSet(APIView):
    @with_retry(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)
    def create(self, request):
        try:
            # Validate input
            validated_data = validate_contract_data(request.data)
            
            # Create contract
            contract = ContractService.create_contract(
                tenant_id=request.user.tenant_id,
                data=validated_data
            )
            
            return Response({"id": str(contract.id)}, status=201)
            
        except ValidationError as e:
            # Log and track error
            log_error(
                error=e,
                error_code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
            )
            
            track_error(
                error=e,
                error_code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
            )
            
            # Return standardized error response
            return format_error_response(
                exception=e,
                code="VALIDATION_ERROR",
                message="Contract validation failed",
                http_status=400,
                request_id=request.id,
            )
            
        except Exception as e:
            # Log and track unexpected errors
            log_error(
                error=e,
                error_code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
                level="critical",
            )
            
            track_error(
                error=e,
                error_code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
                tenant_id=str(request.user.tenant_id),
                user_id=str(request.user.id),
                level="critical",
            )
            
            # Return generic error (don't expose internal details)
            return format_error_response(
                code="INTERNAL_ERROR",
                message="Internal server error",
                http_status=500,
                request_id=request.id,
            )
```

### Example: Service with Circuit Breaker

```python
from hub.apps.core.error_handling.error_recovery import with_circuit_breaker
from hub.apps.core.error_handling.error_logging import log_error

class ExternalAPIService:
    @with_circuit_breaker(
        failure_threshold=5,
        success_threshold=2,
        timeout=60.0,
        name="external_api",
    )
    def fetch_data(self, url):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log_error(
                error=e,
                error_code="EXTERNAL_API_ERROR",
                message="External API request failed",
                context={"url": url},
            )
            raise
```

### Example: Background Job with Retry

```python
from hub.apps.core.error_handling.error_recovery import with_retry, RetryStrategy

@with_retry(
    max_attempts=5,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=2.0,
    max_delay=300.0,  # 5 minutes max
)
def process_background_job(job_id):
    job = Job.objects.get(id=job_id)
    
    try:
        # Process job
        result = process_job(job)
        job.status = JobStatus.SUCCEEDED
        job.save()
        return result
    except TransientError as e:
        # Transient errors are retryable
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save()
        raise
    except PermanentError as e:
        # Permanent errors are not retryable
        job.status = JobStatus.FAILED
        job.error_message = str(e)
        job.save()
        raise
```

---

## Best Practices

### 1. Error Response Standardization

- **Always use standardized format**: Use `ErrorResponse` or `format_error_response`
- **Include request_id**: Always include request ID for correlation
- **Provide clear messages**: Use user-friendly error messages
- **Include details**: Add field-level errors and context when helpful
- **Don't expose internals**: Never expose stack traces or internal details

### 2. Error Logging

- **Log all errors**: Log every error with full context
- **Use appropriate levels**: Use `error` for errors, `warning` for recoverable issues, `critical` for system failures
- **Include context**: Always include request_id, tenant_id, user_id when available
- **Don't log PII**: PII is automatically redacted, but avoid logging sensitive data
- **Structured logging**: Use structured logging with consistent fields

### 3. Error Tracking (Sentry)

- **Set SENTRY_DSN**: Configure Sentry DSN in environment
- **Set user context**: Always set user and tenant context
- **Monitor error rates**: Set up alerts for high error rates
- **Review errors regularly**: Review Sentry dashboard for patterns
- **Use releases**: Tag errors with release versions

### 4. Error Recovery

- **Use retry for transient errors**: Retry network errors, timeouts, temporary failures
- **Don't retry permanent errors**: Don't retry validation errors, permission errors
- **Use circuit breakers for external services**: Protect against cascading failures
- **Set appropriate thresholds**: Configure failure thresholds based on service reliability
- **Monitor circuit breaker state**: Log circuit breaker state changes

### 5. Error Handling Patterns

- **Try-except blocks**: Use try-except for error handling
- **Specific exceptions**: Catch specific exceptions, not generic Exception
- **Log before raising**: Log errors before re-raising
- **Track in Sentry**: Track errors in Sentry for monitoring
- **Return standardized responses**: Always return standardized error responses

### 6. Performance Considerations

- **Async error handling**: Use async error handling for async operations
- **Non-blocking logging**: Error logging should not block request processing
- **Efficient retry logic**: Use appropriate backoff strategies to avoid overwhelming services
- **Circuit breaker timeouts**: Set appropriate timeouts for circuit breakers

---

## Summary

Error handling ensures:

1. ✅ **Standardized Responses**: Consistent error format across all endpoints
2. ✅ **Comprehensive Logging**: Full context for debugging and monitoring
3. ✅ **Error Tracking**: Automatic error tracking with Sentry
4. ✅ **Error Recovery**: Retry logic and circuit breakers for resilience

By following these patterns, we ensure:
- **Consistency**: All errors follow the same format
- **Observability**: All errors are logged and tracked
- **Resilience**: Automatic recovery from transient failures
- **Debugging**: Full context for troubleshooting

