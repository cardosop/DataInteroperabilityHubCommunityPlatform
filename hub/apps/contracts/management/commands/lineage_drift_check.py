"""
Phase 228 (228.0.DoD.3) — read-only drift verification gate.

Computes the open-edge vs JSON-lineage-entry-count delta across the
selected scope (all tenants by default; ``--tenant=<uuid>`` narrows)
and emits a structured JSON report. Exit-code-meaningful so the
operator's wrapper script + CI / cron can branch on the return code:

* exit 0   → ``status="ok"`` (delta ≤ tolerance) or
              ``status="EMPTY"`` (no contracts in scope).
* exit 1+  → ``status="DRIFT"`` (delta > tolerance).

Engineering invariants
----------------------

* **Read-only.** Never modifies LineageEdge rows. The verification
  must be safe to run during business hours / against production.
* **Idempotent.** A second invocation produces the same report; this
  is verified by running the same canonical predicate (``_desired_edge_set``)
  the signal handler + backfill use, so the diff semantics never
  diverge between writers and verifier.
* **Tolerance default 0.1%** matches REQ-LIN-003.
* **Structured stdout** — one JSON object per scope. Operator wraps
  with ``--tenant=$T`` per tenant + archives the artefact.

Usage::

    # Whole DB:
    python manage.py lineage_drift_check

    # Per-tenant (canonical staging usage):
    python manage.py lineage_drift_check --tenant=<uuid> --tolerance=0.001

    # Permissive (debug-only — accept up to 5%):
    python manage.py lineage_drift_check --tolerance=0.05
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError


DEFAULT_TOLERANCE = 0.001  # ±0.1%


class Command(BaseCommand):
    help = (
        "Phase 228 (228.0.DoD.3): read-only drift verification gate. "
        "Compares open LineageEdge count against JSON-lineage-entry count; "
        "exits non-zero on DRIFT > tolerance."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant",
            default=None,
            help="Restrict to a single tenant UUID (default: all tenants).",
        )
        parser.add_argument(
            "--tolerance",
            type=float,
            default=DEFAULT_TOLERANCE,
            help=(
                f"Drift tolerance as a fraction (default {DEFAULT_TOLERANCE} "
                "= 0.1%). Above this value the command exits non-zero."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        from hub.apps.contracts.models import Contract, LineageEdge
        from hub.apps.contracts.lineage_sync import _desired_edge_set

        tenant_id: str | None = options.get("tenant")
        tolerance: float = options["tolerance"]

        # Read the desired-state set across the contract corpus.
        contracts_qs = Contract.objects.all()
        edges_qs = LineageEdge.objects.filter(valid_to__isnull=True)
        if tenant_id:
            contracts_qs = contracts_qs.filter(tenant_id=tenant_id)
            edges_qs = edges_qs.filter(tenant_id=tenant_id)

        json_entries = 0
        for c in contracts_qs.iterator(chunk_size=500):
            json_entries += len(_desired_edge_set(c))
        edges_open = edges_qs.count()

        # Classify.
        status, delta_pct = self._classify(
            json_entries=json_entries,
            edges_open=edges_open,
            tolerance=tolerance,
        )

        report: dict[str, Any] = {
            "phase": "228.0.DoD.3",
            "status": status,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "json_entries": json_entries,
            "edges_open": edges_open,
            "delta_abs": abs(json_entries - edges_open),
            "delta_pct": round(delta_pct * 100, 4),
            "tolerance_pct": round(tolerance * 100, 4),
            "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.stdout.write(json.dumps(report, sort_keys=True))

        # Exit-code-meaningful: non-zero only on DRIFT so cron / CI can
        # branch. ``EMPTY`` is benign (no contracts in scope).
        if status == "DRIFT":
            raise CommandError(
                f"Lineage drift detected ({delta_pct * 100:.3f}%) "
                f"exceeds tolerance ({tolerance * 100:.3f}%). "
                f"Re-run backfill: python manage.py backfill_lineage_edges "
                f"--resume-key=drift-correction-$(date +%F)"
            )

    # ------------------------------------------------------------------

    @staticmethod
    def _classify(
        *,
        json_entries: int,
        edges_open: int,
        tolerance: float,
    ) -> tuple[str, float]:
        """Return ``(status, delta_pct_fraction)``.

        ``delta_pct`` is the absolute delta divided by the larger of
        the two counts (denominator ``max(j, e, 1)`` so a 0-vs-N case
        produces 100% drift instead of dividing by zero).
        """
        if json_entries == 0 and edges_open == 0:
            return "EMPTY", 0.0
        denom = max(json_entries, edges_open, 1)
        delta_pct = abs(json_entries - edges_open) / denom
        if delta_pct <= tolerance:
            return "ok", delta_pct
        return "DRIFT", delta_pct
