"""W4.6 (openspec oss-release-remediation, G1) — the provider-agnostic
estate-job handler seam.

The executor surfaces for provider estate jobs (UC metadata sync, cost
sync, the UC-change reaper) live in ``hub.apps.databricks_admin`` (their
handlers touch estate models and clients), while the Job dispatch table
(``jobs.tasks_base._execute_job_logic``) is the provider-agnostic
Appendix B "Job dispatch" spine. The provider-boundary contract forbids
importing estate code into provider-agnostic apps, so the dispatch rides
a registry inversion (the 7.5 cost-recording convention): this module
defines the consumer side only; ``databricks_admin`` registers its
handlers at app-ready. A future provider estate registers its own
handlers the same way.

An unregistered job type refuses with a classified ``JobExecutionError``
— never a silent no-op and never an ImportError-shaped crash (a
core-only process never installs the estate app, so its estate job
types simply have no handlers; such jobs cannot be enqueued there by
construction — the enqueueing management commands live in the estate).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

#: A handler executes one job object and returns the result dict (the
#: tasks_base contract).
EstateJobHandler = Callable[[Any], dict]


_registered_handlers: dict[str, EstateJobHandler] = {}
_registry_lock = threading.Lock()


def register_estate_job_handler(job_type: str, handler: EstateJobHandler) -> None:
    """Register a provider estate job handler under its ``JobType``
    string value. Idempotent — ``ready()`` may run more than once per
    process (importlib reloads, test setups)."""
    with _registry_lock:
        _registered_handlers[job_type] = handler


def get_estate_job_handler(job_type: str) -> EstateJobHandler | None:
    """The registered handler for a job type, or None when no provider
    registered one."""
    with _registry_lock:
        return _registered_handlers.get(job_type)


def registered_estate_job_types() -> tuple[str, ...]:
    """The registered job types (sorted — deterministic reporting)."""
    with _registry_lock:
        return tuple(sorted(_registered_handlers))
