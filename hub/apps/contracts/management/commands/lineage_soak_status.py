"""
Phase 228 (228.0.DoD.8) — soak-period status reporter.

The "no P1 incidents during 7-day staging soak" gate (DoD.8) is
operator-driven, but the operator needs a one-shot summary of the
window's events to call the gate. This command produces that summary.

It reads three signals directly from the database (no Prometheus
scrape — the command runs even when Prometheus is unreachable):

1. **Drift events** — any audit row with
   ``action="LINEAGE_EDGE_DRIFT_DETECTED"`` in the window. Critical.
2. **Edge-write storm** — count of ``LINEAGE_EDGE_CREATED`` +
   ``LINEAGE_EDGE_DELETED`` audit events in the window above an
   operator-configurable threshold (default 100k events ≈ 5x normal
   contract-corpus rate). Warning.
3. **Asset auto-revert events** — Phase 227 W5 autoreverts shouldn't
   spike during a Phase 228 soak. Warning.

Each rule's evaluation is rolled up into a top-level status:

* ``OK`` — every rule quiet.
* ``WARN`` — at least one warning condition matched; no critical
  conditions.
* ``CRITICAL`` — at least one critical condition matched → P1 → gate
  fails. Command exits non-zero.

Usage::

    # Default 7-day window (DoD.8 canonical):
    python manage.py lineage_soak_status

    # Daily check (cron):
    python manage.py lineage_soak_status --days=1

    # Per-tenant scope (operator escalation):
    python manage.py lineage_soak_status --tenant=<uuid> --days=7
"""
from __future__ import annotations

import datetime as _dt
import json
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


DEFAULT_WINDOW_DAYS = 7
DEFAULT_EDGE_WRITE_THRESHOLD = 100_000


class Command(BaseCommand):
    help = (
        "Phase 228 (228.0.DoD.8): summarise the soak-period status for "
        "lineage. Reports per-rule + rolled-up status; exits non-zero "
        "on CRITICAL so cron / CI can branch."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=DEFAULT_WINDOW_DAYS,
            help=f"Soak window in days (default {DEFAULT_WINDOW_DAYS}).",
        )
        parser.add_argument(
            "--tenant",
            default=None,
            help="Restrict to a single tenant UUID (default: all tenants).",
        )
        parser.add_argument(
            "--edge-write-threshold",
            type=int,
            default=DEFAULT_EDGE_WRITE_THRESHOLD,
            help=(
                f"Edge-write count threshold for the WARN classification "
                f"(default {DEFAULT_EDGE_WRITE_THRESHOLD})."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        from hub.apps.audit.models import AuditEvent

        days: int = options["days"]
        tenant_id: str | None = options.get("tenant")
        edge_threshold: int = options["edge_write_threshold"]

        cutoff = timezone.now() - _dt.timedelta(days=days)

        rules: list[dict[str, Any]] = []

        # ---- Rule 1 — drift detection events (critical) -----------------
        drift_count = self._count_in_window(
            AuditEvent,
            action="LINEAGE_EDGE_DRIFT_DETECTED",
            cutoff=cutoff,
            tenant_id=tenant_id,
        )
        rules.append({
            "rule": "drift",
            "severity": "critical",
            "count": drift_count,
            "status": "CRITICAL" if drift_count > 0 else "OK",
            "description": (
                "LineageEdge SCD Type 2 drift detected in window — "
                "any non-zero count is a P1."
            ),
        })

        # ---- Rule 2 — edge-write volume (warn on spike) -----------------
        edge_writes = self._count_in_window(
            AuditEvent,
            actions=("LINEAGE_EDGE_CREATED", "LINEAGE_EDGE_DELETED"),
            cutoff=cutoff,
            tenant_id=tenant_id,
        )
        rules.append({
            "rule": "edge_writes",
            "severity": "warning",
            "count": edge_writes,
            "threshold": edge_threshold,
            "status": "WARN" if edge_writes > edge_threshold else "OK",
            "description": (
                f"Total LineageEdge mutations in window. Above "
                f"{edge_threshold} suggests a runaway rewrite job."
            ),
        })

        # ---- Rule 3 — Phase 227 W5 auto-reverts (warn on any) -----------
        auto_revert_count = self._count_in_window(
            AuditEvent,
            action="ASSET_AUTO_REVERTED_STRUCTURELESS",
            cutoff=cutoff,
            tenant_id=tenant_id,
        )
        rules.append({
            "rule": "auto_revert",
            "severity": "warning",
            "count": auto_revert_count,
            "status": "WARN" if auto_revert_count > 0 else "OK",
            "description": (
                "Phase 227 Wave 5 auto-reverts shouldn't fire during a "
                "Phase 228 soak — a non-zero count means a Wave 5 sweep "
                "ran in the window. Verify it's an authorised cycle."
            ),
        })

        # ---- Roll-up status ---------------------------------------------
        if any(r["status"] == "CRITICAL" for r in rules):
            top_status = "CRITICAL"
        elif any(r["status"] == "WARN" for r in rules):
            top_status = "WARN"
        else:
            top_status = "OK"

        report: dict[str, Any] = {
            "phase": "228.0.DoD.8",
            "status": top_status,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "window_days": days,
            "window_start": cutoff.isoformat(),
            "window_end": timezone.now().isoformat(),
            "rules": rules,
            "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }
        self.stdout.write(json.dumps(report, sort_keys=True))

        if top_status == "CRITICAL":
            raise CommandError(
                f"Soak-period status: CRITICAL ({drift_count} drift events). "
                f"DoD.8 fails. Page on-call per "
                f"docs/runbooks/lineage-soak-period.md §"
                f"\"P1 escalation\"."
            )

    # ------------------------------------------------------------------

    @staticmethod
    def _count_in_window(
        model,
        *,
        cutoff,
        tenant_id: str | None = None,
        action: str | None = None,
        actions: tuple[str, ...] | None = None,
    ) -> int:
        qs = model.objects.filter(timestamp__gte=cutoff)
        if action:
            qs = qs.filter(action=action)
        if actions:
            qs = qs.filter(action__in=list(actions))
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs.count()
