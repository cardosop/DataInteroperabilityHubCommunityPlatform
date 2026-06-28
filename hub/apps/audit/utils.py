"""
Audit Logging Utilities

Helper functions for creating audit events with PII redaction.
"""

import hashlib
import os
import re
from typing import Any

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpRequest

from .models import AuditEvent

User = get_user_model()


def redact_pii(data: dict[str, Any], visited: set | None = None) -> dict[str, Any]:
    """
    Redact PII from a dictionary recursively.

    Redacts:
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - SSN
    - Passwords

    Args:
        data: Dictionary to redact
        visited: Set of object IDs already visited (for cycle detection)

    Returns:
        New dictionary with PII redacted.
    """
    if not isinstance(data, dict):
        return data

    # Initialize visited set for cycle detection
    if visited is None:
        visited = set()

    # Check for circular reference
    data_id = id(data)
    if data_id in visited:
        return "[CIRCULAR_REFERENCE]"
    visited.add(data_id)

    try:
        redacted = {}

        # Patterns for PII detection
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
        re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\+?\d{10,15}\b")
        re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b")
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

        # Fields that should always be redacted
        pii_fields = [
            "password",
            "password_hash",
            "api_key",
            "token",
            "secret",
            "ssn",
            "social_security_number",
        ]

        for key, value in data.items():
            key_lower = key.lower()

            # Always redact known PII fields
            if any(pii_field in key_lower for pii_field in pii_fields):
                redacted[key] = "[REDACTED]"
                continue

            # Handle different value types
            if value is None:
                # Preserve None values
                redacted[key] = None
            elif isinstance(value, dict):
                # Recursively process nested dictionaries with cycle detection
                redacted[key] = redact_pii(value, visited)
            elif isinstance(value, list):
                # Process list items
                redacted_list = []
                for item in value:
                    if isinstance(item, dict):
                        redacted_list.append(redact_pii(item, visited))
                    else:
                        # Convert non-dict items to string safely
                        try:
                            redacted_list.append(redact_string(str(item)))
                        except (RecursionError, ValueError, TypeError):
                            redacted_list.append("[COMPLEX_OBJECT]")
                redacted[key] = redacted_list
            elif isinstance(value, str):
                redacted[key] = redact_string(value)
            elif isinstance(value, (int, float, bool)):
                # Preserve numeric and boolean types (they're not PII and JSON-safe)
                redacted[key] = value
            else:
                # For complex objects (models, etc.), convert to string representation
                # but avoid recursion by not processing their internal structure
                try:
                    # Try to get a simple string representation
                    if hasattr(value, "__dict__"):
                        # For objects with __dict__, just use the type name
                        redacted[key] = f"[{type(value).__name__}]"
                    else:
                        redacted[key] = str(value)
                except (RecursionError, ValueError, TypeError):
                    redacted[key] = "[COMPLEX_OBJECT]"

        return redacted
    finally:
        # Remove from visited set when done processing this level
        visited.discard(data_id)


# UUID pattern (8-4-4-4-12 hex) so we can preserve UUIDs and avoid redacting them as phone.
_UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def redact_string(value: str) -> str:
    """
    Redact PII from a string.

    Returns redacted string with PII replaced by [REDACTED] or hashed values.
    UUIDs are preserved so they are not partially redacted as phone numbers.
    """
    if not isinstance(value, str):
        return value

    # Preserve UUIDs: replace with placeholders so digit segments are not redacted as phone
    placeholders = []

    def save_uuid(match):
        placeholders.append(match.group(0))
        return f"__UUID_PLACEHOLDER_{len(placeholders) - 1}__"

    value = _UUID_PATTERN.sub(save_uuid, value)

    # Email addresses
    value = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        lambda m: f"{m.group(0).split('@')[0][:2]}***@{m.group(0).split('@')[1]}",
        value,
    )

    # Phone numbers (match various formats: 555-123-4567, 555.123.4567, 5551234567, +15551234567)
    value = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b|\b\+?\d{10,15}\b", "[REDACTED_PHONE]", value)

    # Credit card numbers
    value = re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[REDACTED_CARD]", value)

    # SSN
    value = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", value)

    # Restore preserved UUIDs
    for i, uuid_val in enumerate(placeholders):
        value = value.replace(f"__UUID_PLACEHOLDER_{i}__", uuid_val)

    return value


_FAIL_CLOSED_COLUMN_KEYS = frozenset({"column", "column_name"})


def _hash_column_name(value: str) -> str:
    normalized = value.strip().lower().encode("utf-8")
    return f"sha256:{hashlib.sha256(normalized).hexdigest()}"


def _redact_fail_closed_payload(value: Any) -> Any:
    from hub.apps.dq.log_helpers import _REDACTED_KEYS

    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key in _REDACTED_KEYS:
                continue
            if key in _FAIL_CLOSED_COLUMN_KEYS and isinstance(item, str):
                redacted[key] = _hash_column_name(item)
                continue
            redacted[key] = _redact_fail_closed_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_fail_closed_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_fail_closed_payload(item) for item in value)
    return value


def redact_fail_closed_audit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a fail-closed payload with sensitive keys/column names redacted."""
    redacted = _redact_fail_closed_payload(payload)
    return redacted if isinstance(redacted, dict) else {}


def _sanitize(value: str) -> str:
    """Neutralize C0 control characters, DEL, NUL, and Unicode line/paragraph separators.

    Replaces characters below ASCII space and ``\\x7f`` with a single ASCII space,
    strips NUL, neutralizes U+2028/U+2029 (log/UI line-break injection in some
    exporters), then collapses contiguous whitespace. Mitigates CRLF / fake-log-line
    injection when filenames or free-text fields are persisted in audit JSON (Phase
    260.2.G / pass-3 S3-4).

    Mirrors the intent of historical compliance ``_sanitize()`` call sites that fed
    structured audit payloads (see dq ``log_helpers`` module docstring cross-ref).
    """
    if not isinstance(value, str):
        return value

    cleaned_chars: list[str] = []
    for ch in value:
        o = ord(ch)
        if o == 0:
            continue
        if ch in ("\u2028", "\u2029"):
            cleaned_chars.append(" ")
            continue
        if o < 32 or o == 127:
            cleaned_chars.append(" ")
        else:
            cleaned_chars.append(ch)

    collapsed = re.sub(r"\s+", " ", "".join(cleaned_chars)).strip()
    return collapsed if collapsed else "[SANITIZED_EMPTY]"


def _sanitize_audit_payload_values(payload: Any) -> Any:
    """Recursively sanitize string leaves **and string dict keys** (details trees).

    Keys are normalized too so JSON/export pipelines cannot carry forgeable field names
    with embedded newlines (Phase 260.2.G closure).
    """
    if isinstance(payload, dict):
        out: dict[Any, Any] = {}
        for k, v in payload.items():
            nk = _sanitize(k) if isinstance(k, str) else k
            out[nk] = _sanitize_audit_payload_values(v)
        return out
    if isinstance(payload, list):
        return [_sanitize_audit_payload_values(item) for item in payload]
    if isinstance(payload, tuple):
        return tuple(_sanitize_audit_payload_values(item) for item in payload)
    if isinstance(payload, str):
        return _sanitize(payload)
    return payload


def create_audit_event(
    resource_type: str,
    action: str,
    actor_user: User | None = None,
    tenant=None,
    resource_id: str | None = None,
    result: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    full_details: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
    *,
    infer_tenant_from_actor: bool = True,
) -> AuditEvent:
    """
    Create an audit event with automatic PII redaction.

    Args:
        resource_type: Type of resource (e.g., "TENANT", "USER", "CONTRACT", "AUTH")
        action: Action performed (e.g., "CREATED", "UPDATED", "DELETED", "LOGIN")
        actor_user: User who performed the action (optional)
        tenant: Tenant this event belongs to (optional; see ``infer_tenant_from_actor``)
        resource_id: ID of the resource (optional)
        result: Result of the action ("SUCCESS", "FAILURE", "WARNING")
        details: Additional details as dictionary (will be sanitized for injection,
            then redacted for PII)
        full_details: Restricted details for admin storage (sanitized for injection;
            not passed through ``redact_pii`` — intentionally richer than ``details``)
        request: HTTP request object (optional, for extracting IP address, user agent)
        infer_tenant_from_actor: When True (default), if ``tenant`` is omitted (None),
            fall back to ``actor_user.tenant``. When False, keep ``tenant`` exactly as
            passed — required for Phase 260.1.F tenant-hard-delete summaries where the
            actor may still belong to an unrelated tenant FK but the event must remain
            system-scoped (``tenant=NULL`` DB row).

    Returns:
        Created AuditEvent instance
    """
    # Infer tenant from actor_user unless caller forbids it (explicit NULL tenant FK).
    if infer_tenant_from_actor and tenant is None and actor_user and hasattr(actor_user, "tenant"):
        tenant = actor_user.tenant

    # Prepare details with request metadata
    details_dict = details.copy() if details else {}
    full_details_dict = full_details.copy() if full_details else None

    if request:
        # Extract IP address
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        if ip_address:
            details_dict["ip_address"] = ip_address
            if full_details_dict is not None:
                full_details_dict["ip_address"] = ip_address

        # Extract user agent
        user_agent = request.META.get("HTTP_USER_AGENT")
        if user_agent:
            details_dict["user_agent"] = user_agent
            if full_details_dict is not None:
                full_details_dict["user_agent"] = user_agent

        # Extract request ID if available
        request_id = getattr(request, "request_id", None)
        if request_id:
            details_dict["request_id"] = str(request_id)
            if full_details_dict is not None:
                full_details_dict["request_id"] = str(request_id)

    # Phase 260.2.G — strip forgeable control characters before PII redaction / persist.
    details_dict = _sanitize_audit_payload_values(details_dict)
    if full_details_dict is not None:
        full_details_dict = _sanitize_audit_payload_values(full_details_dict)

    # Redact PII from details
    redacted_details = redact_pii(details_dict)

    # Validate resource_id format if provided (UUID field validation)
    if resource_id:
        try:
            import uuid

            # Try to parse as UUID to validate format
            uuid.UUID(str(resource_id))
        except (ValueError, TypeError):
            # Invalid UUID format - handle gracefully by setting to None
            # This allows audit events to be created even with invalid resource IDs
            resource_id = None

    def _create_event_with_manager():
        # Phase 277.B.111 — extract OTel trace_id for cross-system correlation
        trace_id = None
        try:
            from opentelemetry import trace as otel_trace

            span = otel_trace.get_current_span()
            if span is not None:
                ctx = span.get_span_context()
                if ctx.is_valid:
                    raw = ctx.trace_id
                    if raw:
                        # OTel trace_id is a 128-bit integer; format as
                        # 32-char hex then convert to UUID hex format:
                        # 8-4-4-4-12 chars with dashes.
                        import uuid as _uuid

                        hex_str = f"{int(raw):032x}"
                        trace_id = str(_uuid.UUID(hex=hex_str))
        except (ImportError, AttributeError, TypeError, RuntimeError, ValueError):
            # OTel not available, span context invalid, trace_id type mismatch,
            # internal SDK errors, or UUID formatting edge cases.
            # The trace_id is best-effort — audit event creation must never fail
            # because of OTel instrumentation issues.
            pass

        return AuditEvent.objects.create(
            tenant=tenant,
            actor_user=actor_user,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            details_json=redacted_details,
            full_details_json=full_details_dict,
            trace_id=trace_id,
        )

    tenant_id = None
    if tenant is not None:
        tenant_id = getattr(tenant, "id", None) or tenant

    # RLS hardening: ensure tenant-scoped audit rows are written under the
    # matching tenant GUC even on anonymous/auth bootstrap paths where
    # middleware tenant context is not yet available.
    if tenant_id:
        from hub.apps.tenants.request_tenant import tenant_context

        current_tenant = None
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.current_tenant_id', true)")
            row = cursor.fetchone()
            if row and row[0]:
                current_tenant = str(row[0])

        tenant_id_str = str(tenant_id)
        if current_tenant == tenant_id_str:
            audit_event = _create_event_with_manager()
        else:
            with tenant_context(tenant_id_str):
                audit_event = _create_event_with_manager()
    else:
        # Tenant-null/system-level audit rows. Production routes
        # this through the ``admin`` BYPASSRLS alias so the
        # ``WITH CHECK (tenant_id = current_setting(...))`` policy
        # doesn't reject NULL-tenant inserts. In test/dev where
        # ``admin`` and ``default`` share the same role, the admin
        # connection has a SEPARATE MVCC snapshot that doesn't see
        # the test transaction's freshly-inserted ``actor_user`` —
        # the INSERT then trips ``audit_events_actor_user_id_...
        # _fk_users_id``.
        #
        # Resolution: try ``admin`` first (production-correct path);
        # on FK violation, fall back to ``default`` with
        # ``row_security=off`` for the duration of the INSERT so the
        # RLS WITH CHECK doesn't reject the NULL-tenant row. The
        # default connection sees its own committed-and-uncommitted
        # data, so the actor_user FK resolves.
        #
        # In test mode (SKIP_TEST_MIGRATIONS=1), TransactionTestCase
        # forbids threaded connections to the `admin` alias because
        # the alias creates a separate connection whose transaction
        # is not tracked by the test runner.  Always route through
        # ``default`` with ``row_security=off`` in test mode.
        from django.db import IntegrityError as _IE

        _use_admin = not os.environ.get("SKIP_TEST_MIGRATIONS")
        if _use_admin:
            try:
                audit_event = AuditEvent.objects.db_manager("admin").create(
                    tenant=tenant,
                    actor_user=actor_user,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    result=result,
                    details_json=redacted_details,
                    full_details_json=full_details_dict,
                )
            except _IE as exc:
                if "actor_user_id" not in str(exc):
                    raise
                # Fall back to default connection with row_security off
                # for the INSERT — same RLS-bypass effect, but on a
                # connection whose snapshot can see the actor_user row.
                from django.db import transaction as _txn

                with _txn.atomic():
                    with connection.cursor() as _c:
                        _c.execute("SET LOCAL row_security = off")
                    audit_event = AuditEvent.objects.create(
                        tenant=tenant,
                        actor_user=actor_user,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        action=action,
                        result=result,
                        details_json=redacted_details,
                        full_details_json=full_details_dict,
                    )
        else:
            # Test mode: always use default connection with
            # row_security=off — the admin alias creates a
            # separate connection not tracked by TransactionTestCase.
            from django.db import transaction as _txn

            with _txn.atomic():
                with connection.cursor() as _c:
                    _c.execute("SET LOCAL row_security = off")
                audit_event = AuditEvent.objects.create(
                    tenant=tenant,
                    actor_user=actor_user,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    action=action,
                    result=result,
                    details_json=redacted_details,
                    full_details_json=full_details_dict,
                )

    # Phase 227 Wave 1 (227.L7 audit follow-up) — emit the
    # ``audit_events_total{action,resource_type,result}`` counter so
    # downstream Grafana panels (e.g. the asset-auto-revert tile on
    # the structureless-rollout dashboard) can count audit events
    # without scraping the audit_events table. Wrapped in a
    # try/except so a metric-backend outage CAN'T block the audit
    # row creation — the audit row is the load-bearing artefact;
    # the metric is the ops-visibility nice-to-have.
    try:
        from hub.apps.observability.otel_metrics import audit_events_total

        audit_events_total.labels(
            action=action or "UNKNOWN",
            resource_type=resource_type or "UNKNOWN",
            result=result or "SUCCESS",
        ).inc()
    except Exception:
        pass

    return audit_event


def log_tenant_operation(
    action: str,
    tenant,
    actor_user: User,
    resource_id: str | None = None,
    result: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditEvent:
    """Convenience function for logging tenant operations"""
    return create_audit_event(
        resource_type="TENANT",
        action=action,
        actor_user=actor_user,
        tenant=tenant,
        resource_id=resource_id or str(tenant.id) if tenant else None,
        result=result,
        details=details,
        request=request,
    )


def log_user_operation(
    action: str,
    user: User,
    actor_user: User,
    result: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditEvent:
    """Convenience function for logging user operations"""
    return create_audit_event(
        resource_type="USER",
        action=action,
        actor_user=actor_user,
        tenant=user.tenant if hasattr(user, "tenant") else None,
        resource_id=str(user.id),
        result=result,
        details=details,
        request=request,
    )


def log_auth_operation(
    action: str,
    user: User,
    result: str = "SUCCESS",
    details: dict[str, Any] | None = None,
    request: HttpRequest | None = None,
) -> AuditEvent:
    """Convenience function for logging authentication operations"""
    return create_audit_event(
        resource_type="AUTH",
        action=action,
        actor_user=user,
        tenant=user.tenant if hasattr(user, "tenant") else None,
        resource_id=str(user.id),
        result=result,
        details=details,
        request=request,
    )
