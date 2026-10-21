"""P7 (openspec add-databricks-cost-guardrails task 7.5, design D4) — the
provider-agnostic cost-recording seam.

The warehouse connectors record ONE cost entry per executed query
(``WarehouseConnector._record_cost`` in ``base.py``). The ledger itself is
a provider estate model — ``DatabricksCostLedger`` lives in
``databricks_admin``, and the provider-boundary contract (CLAUDE.md /
``warehouses/models.py``) forbids importing ``databricks_admin`` models
into this app. The write therefore rides a registry inversion:
``databricks_admin`` registers its ledger writer at app-ready
(``hub/apps/databricks_admin/apps.py``), and this module dispatches to
every registered backend. A future provider estate (Snowflake, ...)
registers its own writer the same way — the seam is homed here once,
never duplicated per provider (the Appendix B discipline).

The facade NEVER raises: cost accounting must never break data movement
(the Phase 273 best-effort discipline). Backend failures — a broken
ledger, an unknown tenant, a malformed record — log a warning and drop
the entry; the query result is already on its way to the caller.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CostRecord:
    """One cost entry for one executed query (the 7.5 attribution contract).

    ``source`` is the movement attribution (``query``/``export``/
    ``ingestion``/``job``); ``workspace_id``/``warehouse_id`` are optional
    provider-estate attribution resolved best-effort by the backend.
    """

    tenant_id: str
    units: float
    unit_label: str
    source: str = "query"
    workspace_id: str | None = None
    warehouse_id: str | None = None
    meta: dict | None = field(default=None)


# A backend writes one record to its provider's ledger. It MUST NOT raise
# for a record it cannot write with attribution complete — drop the
# attribution, keep the cost (the ledger is the truth).
CostBackend = Callable[[CostRecord], None]

_registered_backends: list[CostBackend] = []
_registry_lock = threading.Lock()


def register_cost_backend(backend: CostBackend) -> None:
    """Register a provider ledger writer. Idempotent — ``ready()`` may run
    more than once per process (importlib reloads, test setups)."""
    with _registry_lock:
        if backend not in _registered_backends:
            _registered_backends.append(backend)


def record_cost(record: CostRecord) -> None:
    """Dispatch one cost record to every registered backend.

    NEVER raises: a missing backend, a broken ledger, or a malformed
    record logs a warning and the entry is dropped — cost accounting must
    never break the query path (the Phase 273 discipline).
    """
    backends = tuple(_registered_backends)
    if not backends:
        logger.warning(
            "warehouse_cost_record_dropped: no cost backend registered "
            "(tenant=%s, source=%s, units=%s)",
            record.tenant_id,
            record.source,
            record.units,
        )
        return
    for backend in backends:
        try:
            backend(record)
        except Exception:
            # (the Phase 273 discipline: cost accounting must never break
            # data movement, whatever the backend throws)
            logger.warning(
                "warehouse_cost_record_failed (backend=%s, tenant=%s, "
                "source=%s, units=%s, label=%s)",
                getattr(backend, "__name__", type(backend).__name__),
                record.tenant_id,
                record.source,
                record.units,
                record.unit_label,
                exc_info=True,
            )
