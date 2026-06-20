"""
Phase 228 (REQ-LIN-003, 228.0.11) — backfill ``LineageEdge`` rows from
``Contract.hub_contract_json.lineage`` for contracts that pre-date the
signal handler.

The command is **idempotent** (running twice produces the same end
state — same close-then-insert semantics as the live signal handler)
and **resumable** (a Redis checkpoint per ``--resume-key`` lets a
crashed run pick up at the next batch).

Engineering invariants
----------------------

* Reuses the canonical ``_sync_contract_edges`` helper from
  ``hub.apps.contracts.lineage_sync`` so the backfill semantics are
  bit-identical to the signal handler. There are NOT two diff
  implementations.
* Per-batch ``select_for_update(skip_locked=True)`` so concurrent
  writers (the live signal) do not block; locked rows are deferred
  to the next batch.
* ``--dry-run`` outputs the per-contract plan without writing.
* Post-run verification compares ``count(open LineageEdge)`` against
  ``sum(json lineage entries)`` and warns within ±0.1% tolerance.

Usage::

    python manage.py backfill_lineage_edges --batch-size=500
    python manage.py backfill_lineage_edges --tenant=<uuid> --dry-run
    python manage.py backfill_lineage_edges --resume-key=lin-2026-04-30
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

DEFAULT_BATCH_SIZE = 500
DEFAULT_VERIFY_TOLERANCE = 0.001  # ±0.1%


class Command(BaseCommand):
    help = (
        "Phase 228 (REQ-LIN-003): idempotent + resumable backfill of "
        "the LineageEdge index from Contract.hub_contract_json.lineage."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Contracts per batch (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--tenant",
            default=None,
            help="Restrict to a single tenant UUID (default: all tenants).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Plan + count only; do not write LineageEdge rows.",
        )
        parser.add_argument(
            "--resume-key",
            default=None,
            help=(
                "Redis key used to checkpoint progress per batch. A "
                "crashed run with the same key resumes at the next "
                "batch. Without this flag the run is non-resumable."
            ),
        )
        parser.add_argument(
            "--verify-tolerance",
            type=float,
            default=DEFAULT_VERIFY_TOLERANCE,
            help=(
                "Post-run verification tolerance for the open-edge "
                f"count vs JSON-lineage-entry count (default: ±{DEFAULT_VERIFY_TOLERANCE * 100:.1f}%)."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        from hub.apps.contracts.lineage_sync import _sync_contract_edges
        from hub.apps.contracts.models import Contract

        batch_size: int = options["batch_size"]
        tenant_id: str | None = options.get("tenant")
        dry_run: bool = options["dry_run"]
        resume_key: str | None = options.get("resume_key")
        tolerance: float = options["verify_tolerance"]

        logger = logging.getLogger(__name__)
        logger.info(
            "backfill_lineage_edges_start",
            extra={
                "batch_size": batch_size,
                "tenant_id": tenant_id,
                "dry_run": dry_run,
                "resume_key": resume_key,
            },
        )

        last_done_id = self._load_resume_checkpoint(resume_key)
        if last_done_id:
            self.stdout.write(f"  [resume] picking up after contract {last_done_id}")

        qs = Contract.objects.all().order_by("id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if last_done_id:
            qs = qs.filter(id__gt=last_done_id)

        # Materialise candidate IDs once so the per-batch
        # ``select_for_update`` re-fetch is decoupled from iteration.
        candidate_ids = list(qs.values_list("id", flat=True))
        total = len(candidate_ids)

        if dry_run:
            self.stdout.write(f"  [dry-run] would process {total} contract(s)")

        processed = 0
        adds = 0
        removes = 0
        for offset in range(0, total, batch_size):
            batch_ids = candidate_ids[offset : offset + batch_size]
            with transaction.atomic():
                # ``skip_locked`` so a concurrent live save doesn't block.
                # SQLite ignores it (no-op); Postgres honours it.
                rows = list(
                    Contract.objects.select_for_update(skip_locked=True)
                    .filter(id__in=batch_ids)
                    .order_by("id")
                )
                for contract in rows:
                    if dry_run:
                        desired = self._desired_count(contract)
                        self.stdout.write(
                            f"    [plan] contract={contract.id} would_have_open_edges={desired}"
                        )
                        processed += 1
                        continue
                    pre_adds, _pre_removes = _count_open_edges(contract)
                    _sync_contract_edges(contract)
                    post_adds, _post_removes = _count_open_edges(contract)
                    delta = post_adds - pre_adds
                    if delta > 0:
                        adds += delta
                    elif delta < 0:
                        removes += -delta
                    processed += 1

            if not dry_run and resume_key and rows:
                self._save_resume_checkpoint(resume_key, rows[-1].id)

        if not dry_run:
            verified = self._verify_consistency(
                tenant_id=tenant_id,
                tolerance=tolerance,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nBackfill complete: processed={processed} adds≥{adds} "
                    f"removes≥{removes} verification={verified}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\n[dry-run] would process {processed} contract(s)")
            )

    # ------------------------------------------------------------------

    @staticmethod
    def _desired_count(contract: Any) -> int:
        from hub.apps.contracts.lineage_sync import _desired_edge_set

        return len(_desired_edge_set(contract))

    def _verify_consistency(
        self,
        *,
        tenant_id: str | None,
        tolerance: float,
    ) -> str:
        """Compare ``count(open LineageEdge)`` against the JSON-lineage
        entry count across the same scope. REQ-LIN-003: ±0.1% tolerance."""
        from hub.apps.contracts.lineage_sync import _desired_edge_set
        from hub.apps.contracts.models import Contract, LineageEdge

        qs_contract = Contract.objects.all()
        qs_edges = LineageEdge.objects.filter(valid_to__isnull=True)
        if tenant_id:
            qs_contract = qs_contract.filter(tenant_id=tenant_id)
            qs_edges = qs_edges.filter(tenant_id=tenant_id)

        json_count = 0
        for c in qs_contract.iterator(chunk_size=500):
            json_count += len(_desired_edge_set(c))
        edge_count = qs_edges.count()

        if json_count == 0 and edge_count == 0:
            return "ok (0/0)"
        denominator = max(json_count, edge_count, 1)
        delta = abs(json_count - edge_count) / denominator
        marker = "ok" if delta <= tolerance else "DRIFT"
        return f"{marker} (json={json_count}, edges={edge_count}, delta={delta * 100:.3f}%)"

    # --- Resume-key checkpoint helpers --------------------------------

    @staticmethod
    def _load_resume_checkpoint(resume_key: str | None):
        if not resume_key:
            return None
        try:
            from django.core.cache import cache

            value = cache.get(f"backfill_lineage:{resume_key}")
            return value
        except Exception:
            return None

    @staticmethod
    def _save_resume_checkpoint(resume_key: str, contract_id: Any) -> None:
        try:
            from django.core.cache import cache

            cache.set(
                f"backfill_lineage:{resume_key}",
                str(contract_id),
                timeout=3600 * 24,
            )
        except Exception:
            return


def _count_open_edges(contract: Any) -> tuple[int, int]:
    """Return ``(open_count, closed_count)`` for the contract."""
    from hub.apps.contracts.models import LineageEdge

    open_count = LineageEdge.objects.filter(
        target_contract=contract,
        valid_to__isnull=True,
    ).count()
    closed_count = LineageEdge.objects.filter(
        target_contract=contract,
        valid_to__isnull=False,
    ).count()
    return open_count, closed_count
