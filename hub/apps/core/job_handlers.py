"""Phase 313.1 — job handler registry.

Core owns the dispatch mechanism (``hub/apps/jobs/tasks_base.py``); paid apps
register their handlers from ``AppConfig.ready()``. In core-only mode no paid
handler exists and the dispatcher falls through to its unknown-type error —
no paid import ever happens on the core path.

Registration is idempotent by design (last registration wins), matching the
``@register_chain`` reload semantics used elsewhere in core: a repeated
``ready()`` (test reloads, double setup) must never duplicate or raise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

# job type value (JobType TextChoices string) → handler(job_obj) -> dict
_JOB_HANDLERS: dict[str, Callable[..., Any]] = {}


def register_job_handler(job_type: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator: register the wrapped function as the handler for ``job_type``."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        _JOB_HANDLERS[job_type] = fn
        return fn

    return decorator


def get_job_handler(job_type: str) -> Callable[..., Any] | None:
    """Return the registered handler for ``job_type`` or None (core-only)."""
    return _JOB_HANDLERS.get(job_type)


def all_registered_job_types() -> frozenset[str]:
    """Snapshot of registered job-type keys (diagnostics/tests)."""
    return frozenset(_JOB_HANDLERS)
