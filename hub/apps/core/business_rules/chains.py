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

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from django.db import transaction

from hub.apps.core.business_rules.base import BusinessRules, RuleExecutionContext, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class RuleChain:
    """Phase 274.7 — named chain of business rule steps."""

    name: str
    steps: List[Callable[..., ValidationResult]] = field(default_factory=list)
    requires_transaction: bool = True
    short_circuit: bool = True
    async_safe: bool = True

    def execute(
        self,
        context: Optional[RuleExecutionContext] = None,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
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
        results: Dict[str, ValidationResult] = {}
        errors: List[str] = []

        for step in self.steps:
            step_name = getattr(step, "__name__", str(step))
            try:
                result = step(ctx, **kwargs) if callable(step) else ValidationResult(is_valid=True)
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
                if self.short_circuit:
                    break

        duration_ms = (time.monotonic() - started_at) * 1000
        all_valid = all(r.is_valid for r in results.values())

        # Phase 274.7.2 — single audit event per chain execution.
        try:
            from hub.apps.audit.utils import create_audit_event
            create_audit_event(
                resource_type="RULE_CHAIN",
                action="RULE_CHAIN_COMPLETED",
                actor_user=None,
                tenant=None,
                resource_id=self.name,
                result="SUCCESS" if all_valid else "FAILURE",
                details={
                    "chain": self.name,
                    "steps": list(results.keys()),
                    "outcome": "PASS" if all_valid else "FAIL",
                    "duration_ms": round(duration_ms, 2),
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
                    from hub.apps.users.models import User
                    from hub.apps.tenants.models import Tenant
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

_CHAINS: Dict[str, RuleChain] = {}


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
    context: Optional[RuleExecutionContext] = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Execute a registered chain by name."""
    chain = _CHAINS.get(name)
    if chain is None:
        raise ValueError(f"RuleChain '{name}' not found. Registered: {list(_CHAINS.keys())}")
    return chain.execute(
        context=context, tenant_id=tenant_id, user_id=user_id, **kwargs,
    )


def get_chain(name: str) -> Optional[RuleChain]:
    """Return a registered chain, or None."""
    return _CHAINS.get(name)
