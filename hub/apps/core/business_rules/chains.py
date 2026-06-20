"""
Phase 274.7 — RuleChain primitive.

A ``RuleChain`` is a named, ordered sequence of rule steps that
executes within an active transaction context. It provides:
- Short-circuit on first failure (default)
- Per-step OTel spans under a parent chain span
- Single ``rule_chain_completed`` audit event
- Async-safe semantics (no side-effect helpers fire until all steps pass)
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from hub.apps.core.business_rules.base import RuleExecutionContext, ValidationResult

logger = logging.getLogger(__name__)

# Phase 274.8.2 — OTel parent span. Import is optional so the chain runs
# fine in environments where OpenTelemetry isn't installed (the same
# pattern :mod:`base` already uses).
try:
    from opentelemetry import trace as _otel_trace

    from hub.apps.observability.otel_config import get_tracer as _otel_get_tracer

    _OTEL_AVAILABLE = True
except ImportError:
    _otel_trace = None
    _otel_get_tracer = None
    _OTEL_AVAILABLE = False


class _NullSpanCtx:
    """Context manager that no-ops when OpenTelemetry isn't available.

    Returned by :func:`_chain_span` so call-site code stays uniform
    (``with _chain_span(...) as span: ...``) without an availability
    branch on every attribute set.
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, *_args, **_kwargs):
        return None

    def record_exception(self, *_args, **_kwargs):
        return None

    def is_recording(self):
        return False


def _chain_span(chain_name: str):
    """Open an OTel span over a chain execution, or a no-op shim."""
    if not _OTEL_AVAILABLE or _otel_get_tracer is None:
        return _NullSpanCtx()
    try:
        tracer = _otel_get_tracer(__name__)
        return tracer.start_as_current_span(f"business_rule_chain.{chain_name}")
    except Exception:
        # Never let a tracer-init failure break chain execution.
        return _NullSpanCtx()


@dataclass
class RuleChain:
    """Phase 274.7 — named chain of business rule steps."""

    name: str
    steps: list[Callable[..., ValidationResult]] = field(default_factory=list)
    requires_transaction: bool = True
    short_circuit: bool = True
    async_safe: bool = True

    def execute(
        self,
        context: RuleExecutionContext | None = None,
        *,
        tenant_id: str | None = None,
        user_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute the chain within a transaction.

        Returns ``{outcome, steps, duration_ms, errors}``.
        Side-effect helpers (cache, search-index, webhook, lineage)
        MUST NOT fire until ALL steps succeed (§13.3).
        """
        if self.requires_transaction and not transaction.get_connection().in_atomic_block:
            raise RuntimeError(
                f"RuleChain '{self.name}' requires an active transaction. "
                f"Wrap the call in transaction.atomic()."
            )

        ctx = context or RuleExecutionContext(
            tenant_id=tenant_id,
            user_id=user_id,
        )

        started_at = time.monotonic()
        results: dict[str, ValidationResult] = {}
        errors: list[str] = []

        # Phase 274.8.2 — open the canonical parent span for the entire
        # chain. Per-step spans opened by individual rules (via
        # ``BusinessRules.execute``) become children of this one so
        # dashboards can collapse a full chain into a single root and
        # drill into each step underneath. Attributes are stamped at
        # exit (after we know duration + outcome) so a single span
        # carries the whole chain summary.
        with _chain_span(self.name) as chain_span:
            chain_span.set_attribute("business_rule_chain.name", self.name)
            chain_span.set_attribute(
                "business_rule_chain.tenant_id", str(tenant_id) if tenant_id else ""
            )
            chain_span.set_attribute("business_rule_chain.user_id", str(user_id) if user_id else "")
            chain_span.set_attribute("business_rule_chain.short_circuit", bool(self.short_circuit))
            chain_span.set_attribute("business_rule_chain.steps_planned", len(self.steps))

            for step in self.steps:
                base_name = getattr(step, "__name__", str(step))
                # Disambiguate duplicate step names so every step entry
                # is preserved in the results dict (Phase 274.7.10).
                step_name = base_name
                if step_name in results:
                    idx = 2
                    while f"{base_name}_{idx}" in results:
                        idx += 1
                    step_name = f"{base_name}_{idx}"
                try:
                    result = (
                        step(ctx, **kwargs) if callable(step) else ValidationResult(is_valid=True)
                    )
                    if isinstance(result, ValidationResult):
                        results[step_name] = result
                        if not result.is_valid and self.short_circuit:
                            errors = result.errors
                            break
                    else:
                        results[step_name] = ValidationResult(is_valid=True)
                except Exception as exc:
                    results[step_name] = ValidationResult(
                        is_valid=False,
                        errors=[str(exc)],
                    )
                    errors.append(f"{step_name}: {exc}")
                    # Record the exception on the chain span so
                    # Tempo/Jaeger surfaces the failing step without
                    # forcing operators to cross-reference logs.
                    with contextlib.suppress(Exception):
                        chain_span.record_exception(exc)
                    if self.short_circuit:
                        break

            duration_ms = (time.monotonic() - started_at) * 1000
            all_valid = all(r.is_valid for r in results.values())

            # Stamp final outcome on the span before the context manager
            # exits so the span is closed with the canonical shape:
            # name, tenant_id, user_id, short_circuit, steps_planned,
            # steps_executed, outcome, duration_ms, errors_count.
            try:
                chain_span.set_attribute("business_rule_chain.steps_executed", len(results))
                chain_span.set_attribute(
                    "business_rule_chain.outcome", "PASS" if all_valid else "FAIL"
                )
                chain_span.set_attribute("business_rule_chain.duration_ms", round(duration_ms, 2))
                chain_span.set_attribute("business_rule_chain.errors_count", len(errors))
            except Exception:
                pass

        # Phase 274.7.2 — single audit event per chain execution.
        # Created on the default connection as a system-level audit row
        # (tenant=None).  The audit is within the caller's transaction by
        # design — step-level audit rows AND chain-completed rows share the
        # caller's atomic boundary.  For durability across rollbacks (Phase
        # 277.1.3), production deployments use the admin BYPASSRLS
        # connection; that optimisation is applied in a follow-up when the
        # audit service exposes a ``using`` kwarg.
        try:
            from hub.apps.audit.models import AuditEvent

            AuditEvent.objects.create(
                resource_type="RULE_CHAIN",
                action="RULE_CHAIN_COMPLETED",
                tenant=None,
                actor_user=None,
                resource_id=None,
                result="SUCCESS" if all_valid else "FAILURE",
                details_json={
                    "chain": self.name,
                    "steps": list(results.keys()),
                    "outcome": "PASS" if all_valid else "FAIL",
                    "duration_ms": round(duration_ms, 2),
                    "audit_retention_category": "business_rules",  # Phase 274.16.8 — 30-day window
                    "tenant_id": tenant_id,
                },
            )
        except Exception:
            logger.exception("chain_audit_failed")

        # Phase 274.7.4 — async failure notification.
        if not all_valid and getattr(ctx, "metadata", {}).get("is_async"):
            try:
                from hub.apps.notifications.utils import create_user_notification

                if user_id and tenant_id:
                    from hub.apps.tenants.models import Tenant
                    from hub.apps.users.models import User

                    user = User.objects.get(pk=user_id)
                    tenant_obj = Tenant.objects.get(pk=tenant_id)
                    create_user_notification(
                        user=user,
                        tenant=tenant_obj,
                        title=f"Chain '{self.name}' failed",
                        message="; ".join(errors[:3]),
                        notification_type="ERROR",
                        category="SYSTEM",
                    )
            except Exception:
                logger.exception("chain_async_notification_failed")

        return {
            "outcome": "PASS" if all_valid else "FAIL",
            "steps": results,
            "duration_ms": round(duration_ms, 2),
            "errors": errors,
        }


# ── Chain registry ──────────────────────────────────────────────────────

_CHAINS: dict[str, RuleChain] = {}


def register_chain(
    name: str,
    *,
    requires_transaction: bool = True,
    short_circuit: bool = True,
    async_safe: bool = True,
) -> Callable:
    """Decorator that registers a function as a RuleChain builder."""

    def decorator(func):
        chain = RuleChain(
            name=name,
            requires_transaction=requires_transaction,
            short_circuit=short_circuit,
            async_safe=async_safe,
        )
        chain.steps = list(func()) if callable(func) else []
        _CHAINS[name] = chain
        return func

    return decorator


def execute_chain(
    name: str,
    context: RuleExecutionContext | None = None,
    *,
    tenant_id: str | None = None,
    user_id: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Execute a registered chain by name."""
    chain = _CHAINS.get(name)
    if chain is None:
        raise ValueError(f"RuleChain '{name}' not found. Registered: {list(_CHAINS.keys())}")
    return chain.execute(
        context=context,
        tenant_id=tenant_id,
        user_id=user_id,
        **kwargs,
    )


def get_chain(name: str) -> RuleChain | None:
    """Return a registered chain, or None."""
    return _CHAINS.get(name)
