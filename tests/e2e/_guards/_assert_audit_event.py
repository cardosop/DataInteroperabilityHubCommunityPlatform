"""Dual-channel audit-event verification helpers.

The existing `tests/e2e/conftest.py::verify_audit_log` (line 1484) only asserts
`.count() > 0` on an AuditEvent queryset and raises a generic "not found"
message. When an assertion fails on CI you then spend 20 minutes guessing
why — were action names renamed? Was the tenant scoped correctly? Did the
event land under a different resource_type?

These helpers fix that. On failure they include the ten most recent audit
events recorded for the test tenant, so the diagnostic tells you what *was*
written — which is usually enough to pinpoint the bug in the audit signal
handler or the test's expectations.

Two variants:

* `assert_audit_event(...)` — synchronous; use after in-request writes.
  Meshant creates audit events via `AuditEvent.objects.create(...)` in
  `hub/apps/audit/utils.py:239`, so this is the correct helper for the
  overwhelming majority of Tier-1 write-path tests.

* `assert_audit_event_eventually(..., timeout=10)` — polling; use when the
  event is produced by an async pathway such as
  `hub/apps/jobs/tasks.process_job(...)` (compliance runs, DQ runs, Celery
  dispatch, any `transaction.on_commit` hook). Raises after `timeout`
  seconds with the same diagnostic as the sync variant.
"""

from __future__ import annotations

import time
from typing import Any


def _audit_event_model():
    # Deferred import so this module is safe to import at module load time in
    # tests that don't have Django set up yet (our own test__guards.py doesn't
    # want Django at import time; it sets up the test DB via pytest-django).
    from hub.apps.audit.models import AuditEvent
    return AuditEvent


def _recent_events_for(tenant, limit: int = 10) -> list[dict[str, Any]]:
    """Return the `limit` most recent audit events for `tenant` as dicts.

    Used verbatim in the assertion-failure diagnostic. We intentionally pull
    only the fields a developer needs to eyeball the delta — dumping full
    objects is noise.
    """
    AuditEvent = _audit_event_model()
    return list(
        AuditEvent.objects.filter(tenant_id=tenant.id)
        .order_by("-created_at")[:limit]
        .values("action", "resource_type", "resource_id", "result", "created_at")
    )


def _build_queryset(*, tenant, action: str, resource_type: str,
                    resource_id=None, result: str = "SUCCESS", **extras):
    AuditEvent = _audit_event_model()
    qs = AuditEvent.objects.filter(
        action=action,
        resource_type=resource_type,
        result=result,
        tenant_id=tenant.id,
        **extras,
    )
    if resource_id is not None:
        qs = qs.filter(resource_id=str(resource_id))
    return qs


def _failure_message(*, tenant, action, resource_type, resource_id, result,
                     extras, extra_prefix: str = "") -> str:
    recent = _recent_events_for(tenant)
    extras_str = f", extras={extras}" if extras else ""
    header = (
        f"{extra_prefix}Expected audit event not found: "
        f"action={action!r} resource_type={resource_type!r} "
        f"resource_id={resource_id!r} result={result!r}{extras_str}"
    )
    body = "\n".join(
        f"  - action={r['action']!r} type={r['resource_type']!r} "
        f"id={r['resource_id']!r} result={r['result']!r} @ {r['created_at']}"
        for r in recent
    )
    if not body:
        body = "  (tenant has no audit events at all)"
    return f"{header}\nMost recent 10 audit events for tenant {tenant.id}:\n{body}"


def assert_audit_event(
    tenant,
    action: str,
    resource_type: str,
    resource_id=None,
    *,
    result: str = "SUCCESS",
    **extras,
) -> None:
    """Assert that an audit event matching the predicate exists for `tenant`.

    Raises `AssertionError` with a diagnostic listing the ten most recent
    audit events recorded for this tenant.

    Intentionally positional for `action`/`resource_type`/`resource_id` to
    match the call-site idiom in tests/e2e/conftest.py::verify_audit_log so
    we can migrate existing tests with a near-mechanical find/replace.
    """
    qs = _build_queryset(
        tenant=tenant, action=action, resource_type=resource_type,
        resource_id=resource_id, result=result, **extras,
    )
    if not qs.exists():
        raise AssertionError(_failure_message(
            tenant=tenant, action=action, resource_type=resource_type,
            resource_id=resource_id, result=result, extras=extras,
        ))


def assert_audit_event_eventually(
    tenant,
    action: str,
    resource_type: str,
    resource_id=None,
    *,
    result: str = "SUCCESS",
    timeout: float = 10.0,
    poll_interval: float = 0.5,
    **extras,
) -> None:
    """Polling variant of `assert_audit_event` for async-produced events.

    Checks the queryset every `poll_interval` seconds up to `timeout` seconds.
    On timeout, raises an `AssertionError` that names the timeout in addition
    to the standard "last ten events" diagnostic.
    """
    if timeout <= 0:
        raise ValueError(f"timeout must be > 0, got {timeout!r}")
    if poll_interval <= 0:
        raise ValueError(f"poll_interval must be > 0, got {poll_interval!r}")

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qs = _build_queryset(
            tenant=tenant, action=action, resource_type=resource_type,
            resource_id=resource_id, result=result, **extras,
        )
        if qs.exists():
            return
        time.sleep(poll_interval)

    raise AssertionError(_failure_message(
        tenant=tenant, action=action, resource_type=resource_type,
        resource_id=resource_id, result=result, extras=extras,
        extra_prefix=f"(after polling {timeout:.1f}s) ",
    ))
