"""
Phase 227 Wave 2 (227.W2.4) — Schema-editor adoption-gate report.

Computes the customer-facing adoption metric used to gate progression
from Wave 2 (editor GA) → Wave 3 (auto-self-heal job).

Adoption gate
-------------
**≥ 30 % of tenants that own at least one structureless contract have
opened the Schema editor at least once during the watch window.**

The query joins two populations:

1. **Tenants with structureless contracts** — pulled live from the
   contracts table via :func:`hub.apps.contracts.structureless.is_structureless`.
2. **Tenants that have opened the editor** — pulled from the
   :class:`AuditEvent` table where ``action='SCHEMA_EDITOR_OPENED'``
   (recorded server-side by the metrics-receive endpoint, Phase 227 L7.2).

The audit table (rather than OTel counters) is the canonical source of
truth because:
* Counters live in Prometheus, which Django can't query directly.
* Audit rows are tenant-scoped, retained 3 years, and tamper-evident
  (Wave 0 invariant).

Output
------
By default the command emits a human-readable summary on stdout. Pass
``--output=json`` to get a machine-parseable JSONL row + summary
suitable for piping into a CI/CD adoption-gate check.

Usage examples
--------------
::

    # Default human report.
    python manage.py schema_editor_adoption_report

    # 7-day watch window, JSON output for CI.
    python manage.py schema_editor_adoption_report \\
        --since-days=7 --output=json > adoption.jsonl

    # Strict gate — exit 1 if adoption < 30 %.
    python manage.py schema_editor_adoption_report \\
        --since-days=7 --gate-threshold=0.30
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand
from django.utils import timezone

DEFAULT_GATE_THRESHOLD = 0.30
DEFAULT_WATCH_WINDOW_DAYS = 7


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 2 — schema-editor adoption gate. "
        "Computes the % of tenants with structureless contracts that "
        "have opened the editor in the watch window, and (optionally) "
        "exits non-zero when the gate threshold is not met."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--since-days",
            type=int,
            default=DEFAULT_WATCH_WINDOW_DAYS,
            help=(
                "Watch-window length in days. Default: 7. The adoption "
                "metric counts editor-opened events from now-Nd to now."
            ),
        )
        parser.add_argument(
            "--gate-threshold",
            type=float,
            default=None,
            help=(
                "If supplied, exit 1 when adoption ratio < this value "
                "(e.g. 0.30 for the Wave 2 → Wave 3 threshold). When "
                "omitted, the command always exits 0 and only reports."
            ),
        )
        parser.add_argument(
            "--output",
            choices=["human", "json"],
            default="human",
            help="Output format: human-readable (default) or JSONL.",
        )
        parser.add_argument(
            "--include-tenants",
            action="store_true",
            help=(
                "Emit per-tenant rows in the JSON output: which tenants "
                "have structureless contracts, and which of them have "
                "opened the editor. Useful for support / customer comms."
            ),
        )

    def handle(self, *_args, **options):
        since_days = int(options["since_days"])
        threshold = options.get("gate_threshold")
        output = options["output"]
        include_tenants = bool(options.get("include_tenants"))

        if since_days <= 0:
            self.stderr.write(
                self.style.ERROR("--since-days must be > 0")
            )
            return

        report = compute_adoption_report(
            since_days=since_days,
            include_tenants=include_tenants,
        )

        if output == "json":
            self._emit_json(report)
        else:
            self._emit_human(report, since_days=since_days)

        if threshold is not None and report["ratio"] < threshold:
            self.stderr.write(
                self.style.ERROR(
                    f"Adoption gate FAILED: ratio "
                    f"{report['ratio']:.1%} < threshold {threshold:.1%}. "
                    f"Wave 3 progression blocked until adoption catches up."
                )
            )
            # Returning a non-zero exit code requires raising
            # SystemExit; ``BaseCommand.handle`` swallows return values.
            raise SystemExit(1)

    # ------------------------------------------------------------------
    # Output formatters
    # ------------------------------------------------------------------

    def _emit_human(self, report: Dict[str, Any], *, since_days: int) -> None:
        self.stdout.write(
            self.style.SUCCESS(
                "Phase 227 Wave 2 — schema-editor adoption report"
            )
        )
        self.stdout.write(f"Watch window: last {since_days} day(s).")
        self.stdout.write(
            f"Tenants with structureless contracts:      "
            f"{report['structureless_tenant_count']}"
        )
        self.stdout.write(
            f"... of those, opened the editor:           "
            f"{report['adopted_tenant_count']}"
        )
        ratio_pct = report["ratio"] * 100
        self.stdout.write(f"Adoption ratio:                            {ratio_pct:.1f} %")

    def _emit_json(self, report: Dict[str, Any]) -> None:
        self.stdout.write(json.dumps(report, sort_keys=True, default=str))


# ---------------------------------------------------------------------------
# Pure-function core (kept module-level so the test suite can import it
# without going through the management-command machinery).
# ---------------------------------------------------------------------------


def compute_adoption_report(
    *,
    since_days: int = DEFAULT_WATCH_WINDOW_DAYS,
    include_tenants: bool = False,
    now: Optional[Any] = None,
) -> Dict[str, Any]:
    """Compute the adoption ratio report.

    Args
    ----
    since_days
        Watch-window length. The adoption metric only counts
        ``SCHEMA_EDITOR_OPENED`` audit events whose ``timestamp`` is
        within ``now - since_days`` to ``now``.
    include_tenants
        When True, the report carries ``structureless_tenant_ids`` and
        ``adopted_tenant_ids`` lists. Off by default so the report is
        cheap to emit in tight CI gates.
    now
        Optional anchor for the watch window — useful in tests. When
        ``None``, uses ``django.utils.timezone.now()``.

    Returns
    -------
    Dict with the canonical shape:

        {
            "structureless_tenant_count": int,
            "adopted_tenant_count": int,
            "ratio": float,                 # 0.0 when no tenants
            "watch_window_days": int,
            "structureless_tenant_ids": [str, ...]   # if include_tenants
            "adopted_tenant_ids": [str, ...]         # if include_tenants
        }
    """
    from hub.apps.audit.models import AuditEvent
    from hub.apps.contracts.models import Contract
    from hub.apps.contracts.structureless import is_structureless

    anchor = now or timezone.now()
    window_start = anchor - timedelta(days=since_days)

    # 1) Tenants with at least one structureless contract.
    structureless_tenant_ids: List[str] = []
    seen: set[str] = set()
    # ``iterator(chunk_size=...)`` keeps memory bounded on large
    # contract corpora — the report runs as a CI gate so we don't want
    # it to OOM.
    for contract in (
        Contract.objects.only("id", "tenant_id", "hub_contract_json")
        .iterator(chunk_size=200)
    ):
        if not is_structureless(contract):
            continue
        tenant_id = getattr(contract, "tenant_id", None)
        if tenant_id is None:
            continue
        tenant_id_str = str(tenant_id)
        if tenant_id_str in seen:
            continue
        seen.add(tenant_id_str)
        structureless_tenant_ids.append(tenant_id_str)

    # 2) Tenants that have opened the editor in the watch window.
    adopted_qs = (
        AuditEvent.objects.filter(
            action="SCHEMA_EDITOR_OPENED",
            timestamp__gte=window_start,
            tenant_id__in=structureless_tenant_ids,
        )
        .values_list("tenant_id", flat=True)
        .distinct()
    )
    adopted_tenant_ids = [str(tid) for tid in adopted_qs if tid]

    # Ratio (zero when no structureless tenants — vacuously satisfied).
    if structureless_tenant_ids:
        ratio = len(adopted_tenant_ids) / len(structureless_tenant_ids)
    else:
        ratio = 0.0

    report: Dict[str, Any] = {
        "structureless_tenant_count": len(structureless_tenant_ids),
        "adopted_tenant_count": len(adopted_tenant_ids),
        "ratio": round(ratio, 4),
        "watch_window_days": since_days,
    }
    if include_tenants:
        report["structureless_tenant_ids"] = sorted(structureless_tenant_ids)
        report["adopted_tenant_ids"] = sorted(adopted_tenant_ids)
    return report
