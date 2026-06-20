"""
Phase 227 Wave 4 (227.W4.1) — tenant-residue classification command.

Partitions every tenant that owns at least one contract into one of
two cohorts:

* ``clean`` — zero remaining structureless contracts.  Safe to roll
  the W4 enforcement comms forward.
* ``residue`` — at least one remaining structureless contract.
  Drives the W4.2 T+7 reminder + W4.3 30-day escalation pipeline.

Why a dedicated command (vs reusing renormalize_contracts)
----------------------------------------------------------
``renormalize_contracts --filter=structureless --output=json`` already
emits one row **per structureless contract**.  W4 needs the **per
tenant** view: cohort, residue count, and the residue contract ids
the W4.2 driver embeds in the reminder email body.  Building that
artefact post-hoc from the per-contract JSONL would force every
downstream consumer (driver / dashboard / smoke-test) to re-aggregate
the same counts; the canonical place to do it once is here.

Output
------
JSONL (default) — one row per tenant::

    {
        "tenant_id": "uuid",
        "tenant_name": "...",
        "cohort": "clean" | "residue",
        "residue_count": int,
        "residue_contract_ids": ["uuid", ...]
    }

Or ``--output=human`` for a one-line summary suitable for a runbook
spot-check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand

# ---------------------------------------------------------------------------
# Pure-function classifier — kept module-level so other commands /
# tests can import it without going through the BaseCommand entry point.
# ---------------------------------------------------------------------------


def classify_tenants_by_residue(
    *,
    tenant_id: str | None = None,
    active_only: bool = False,
) -> list[dict[str, Any]]:
    """Return the per-tenant residue classification.

    Args
    ----
    tenant_id
        Optional UUID — restrict the scan to a single tenant.
    active_only
        Mirror the renormalize command's ``--include-active-only``
        flag: DRAFT/RETIRED residue contracts don't promote a tenant
        to the residue cohort (data engineer's edit buffer / tombstone).

    Returns
    -------
    List of dicts; one per tenant that owns at least one contract.
    Tenants with no contracts at all are excluded — they're vacuously
    satisfied but emitting them would inflate the W4 dashboard's
    rollout-tracker numerator.
    """
    from hub.apps.contracts.models import Contract, ContractStatus
    from hub.apps.contracts.structureless import is_structureless

    qs = Contract.objects.all().order_by("id")
    if tenant_id:
        qs = qs.filter(tenant_id=tenant_id)

    # Build a per-tenant aggregate in one queryset walk. Iterator keeps
    # memory bounded on prod-scale data.
    by_tenant: dict[str, dict[str, Any]] = {}
    for contract in qs.only(
        "id",
        "tenant_id",
        "hub_contract_json",
        "status",
    ).iterator(chunk_size=200):
        tid = getattr(contract, "tenant_id", None)
        if tid is None:
            continue
        # Phase 227 W4 audit (W4.1-AUDIT-1): under ``active_only=True``
        # a tenant with ONLY DRAFT/RETIRED contracts has no
        # customer-facing residue and no rollout work to do — they
        # must be excluded from the cohort, not surfaced as "clean".
        # Skipping the per-row work BEFORE the slot is created
        # guarantees a tenant only enters the dict if it owns at
        # least one row in the active-only scope.
        if active_only and contract.status != ContractStatus.ACTIVE:
            continue
        tid_str = str(tid)
        slot = by_tenant.setdefault(
            tid_str,
            {
                "tenant_id": tid_str,
                "tenant_name": "",
                "cohort": "clean",
                "residue_count": 0,
                "residue_contract_ids": [],
            },
        )
        if is_structureless(contract):
            slot["residue_count"] += 1
            slot["residue_contract_ids"].append(str(contract.id))
            slot["cohort"] = "residue"

    if not by_tenant:
        return []

    # Hydrate tenant_name in one query — saves N round-trips on
    # prod-scale data.
    from hub.apps.tenants.models import Tenant

    name_map = dict(Tenant.objects.filter(id__in=by_tenant.keys()).values_list("id", "name"))
    rows: list[dict[str, Any]] = []
    for tid, slot in by_tenant.items():
        slot["tenant_name"] = str(name_map.get(_to_uuid(tid), "")) or ""
        # Stable sort within a tenant so the output is reproducible
        # for diffing across runs.
        slot["residue_contract_ids"].sort()
        rows.append(slot)
    rows.sort(key=lambda r: r["tenant_id"])
    return rows


def _to_uuid(value: str) -> Any:
    """Best-effort UUID coercion (the name_map keys come from Django
    as UUID objects on Postgres; matching by string would miss them)."""
    import uuid as _uuid

    try:
        return _uuid.UUID(value)
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 4 (227.W4.1): partition tenants into clean / "
        "residue cohorts based on remaining structureless contracts."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict the scan to a single tenant UUID.",
        )
        parser.add_argument(
            "--include-active-only",
            action="store_true",
            default=False,
            help=(
                "Mirror the renormalize command flag: DRAFT/RETIRED "
                "residue does NOT promote a tenant to the residue cohort."
            ),
        )
        parser.add_argument(
            "--only-residue",
            action="store_true",
            default=False,
            help=(
                "Emit only the residue cohort.  Matches the input "
                "shape the W4.2 reminder driver consumes."
            ),
        )
        parser.add_argument(
            "--output",
            choices=["human", "json"],
            default="human",
            help="Output format.  Default human one-line summary.",
        )
        parser.add_argument(
            "--audit-output",
            default=None,
            help=(
                "Optional JSONL artefact path.  The same shape that "
                "stdout emits with --output=json — useful for "
                "feeding the W4.2 driver via --input."
            ),
        )

    def handle(self, *_args, **options):
        tenant_id = options.get("tenant_id")
        active_only = bool(options.get("include_active_only"))
        only_residue = bool(options.get("only_residue"))
        output = options["output"]
        audit_output = options.get("audit_output")

        rows = classify_tenants_by_residue(
            tenant_id=tenant_id,
            active_only=active_only,
        )
        if only_residue:
            rows = [r for r in rows if r["cohort"] == "residue"]

        # Emit
        if output == "json":
            self._emit_json(rows)
        else:
            self._emit_human(rows)

        if audit_output:
            audit_path = Path(audit_output)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("w", encoding="utf-8") as fp:
                for r in rows:
                    fp.write(json.dumps(r, sort_keys=True, default=str) + "\n")

    # ------------------------------------------------------------------

    def _emit_json(self, rows):
        for row in rows:
            self.stdout.write(json.dumps(row, sort_keys=True, default=str))

    def _emit_human(self, rows):
        clean = sum(1 for r in rows if r["cohort"] == "clean")
        residue = sum(1 for r in rows if r["cohort"] == "residue")
        residue_total = sum(r["residue_count"] for r in rows)
        self.stdout.write(
            self.style.SUCCESS(
                f"Phase 227 Wave 4 — tenant residue classification: "
                f"clean={clean}, residue={residue}, "
                f"residue_contracts_total={residue_total}"
            )
        )
        for row in rows:
            if row["cohort"] != "residue":
                continue
            self.stdout.write(
                f"  residue: {row['tenant_name'] or row['tenant_id']} "
                f"({row['tenant_id']}) — {row['residue_count']} contract(s)"
            )
