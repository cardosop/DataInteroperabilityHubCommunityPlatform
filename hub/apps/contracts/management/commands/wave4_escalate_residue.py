"""
Phase 227 Wave 4 (227.W4.3) — 30-day deadline escalation cron.

Reads the ``SCHEMA_EDITOR_RESIDUE_REMINDED`` audit rows the W4.2
driver wrote and, for each row whose ``details.deadline`` has passed,
escalates if-and-only-if the tenant's residue is STILL present.

What "escalation" means in the post-2026-04-30 ungate world
-----------------------------------------------------------
The original spec language said "enable the floor flag for the residue
tenants regardless of whether they remediated. Tenants who haven't
acted will see HTTP 400 STRUCTURELESS_CONTRACT on new uploads — that's
the desired behavior."  Under the ungate directive, the floor is
ALREADY enforced for every tenant from the moment L3.3 shipped — there
is no flag to flip.  So the W4.3 escalation in the post-ungate world is
a pure record-keeping + ops-visibility step:

* Emit one ``STRUCTURELESS_RESIDUE_DEADLINE_PASSED`` audit row per
  eligible tenant.  This is the authoritative customer-facing
  artefact ("we gave you 30 days; the deadline has passed; the
  enforcement is now load-bearing for your tenant").
* Drive a platform-admin summary so support/CS knows which tenants
  to call (the floor itself blocks them at the API edge but a
  human follow-up softens the experience).

Why query the audit table (not a separate state column)
-------------------------------------------------------
The deadline lives in the W4.2 reminder's ``details.deadline`` (the
audit row written when the reminder was sent).  Replaying it from the
audit table guarantees the cron sees the SAME deadline the customer
saw, even if a config knob shifted between reminder and cron run.

Idempotency
-----------
Per (tenant, reminder) pair: a tenant that already has a
``STRUCTURELESS_RESIDUE_DEADLINE_PASSED`` audit row whose timestamp
is AFTER the most-recent reminder is NOT escalated again.  This means
a re-reminder (W4.2 ``--force`` or a fresh batch) implicitly resets the
escalation eligibility for the tenant.

Usage
-----
::

    # Plan only.
    python manage.py wave4_escalate_residue --dry-run

    # Production run — append-only audit emission.
    python manage.py wave4_escalate_residue

    # With operator audit trail.
    python manage.py wave4_escalate_residue \\
        --audit-output=audit-reports/wave4-escalation-$(date +%F).jsonl
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 4 (227.W4.3): emit "
        "STRUCTURELESS_RESIDUE_DEADLINE_PASSED audit rows for tenants "
        "whose W4.2 reminder deadline has passed AND whose residue "
        "remains.  Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Plan only; emit no audit rows.",
        )
        parser.add_argument(
            "--audit-output",
            default=None,
            help=(
                "Optional JSONL artefact path — one row per "
                "escalation decision (escalated / remediated / "
                "future-deadline / already-escalated)."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        dry_run: bool = options["dry_run"]
        audit_output = options.get("audit_output")
        records: List[Dict[str, Any]] = []

        decisions = list(self._iter_decisions())

        escalated = 0
        remediated = 0
        future = 0
        already = 0

        for decision in decisions:
            tenant = decision["tenant"]
            tenant_label = (
                f"{getattr(tenant, 'name', '?')} ({tenant.id})"
            )
            verdict = decision["verdict"]
            if verdict == "escalate":
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"  [dry-run] would escalate {tenant_label}: "
                        f"deadline {decision['deadline']}, "
                        f"{decision['residue_count']} residue contract(s)"
                    ))
                else:
                    self._emit_escalation_audit(
                        tenant=tenant,
                        deadline=decision["deadline"],
                        residue_count=decision["residue_count"],
                    )
                    self.stdout.write(self.style.ERROR(
                        f"  [escalated] {tenant_label}: deadline "
                        f"{decision['deadline']}, "
                        f"{decision['residue_count']} residue contract(s)"
                    ))
                escalated += 1
            elif verdict == "remediated":
                self.stdout.write(self.style.SUCCESS(
                    f"  [remediated] {tenant_label}: residue cleared "
                    f"before {decision['deadline']}"
                ))
                remediated += 1
            elif verdict == "future":
                self.stdout.write(
                    f"  [future-deadline] {tenant_label}: deadline "
                    f"{decision['deadline']} not yet reached"
                )
                future += 1
            elif verdict == "already-escalated":
                self.stdout.write(
                    f"  [already-escalated] {tenant_label}: "
                    f"STRUCTURELESS_RESIDUE_DEADLINE_PASSED already on file"
                )
                already += 1

            records.append({
                "tenant_id": str(tenant.id),
                "tenant_name": getattr(tenant, "name", ""),
                "verdict": verdict,
                "deadline": decision["deadline"],
                "residue_count": decision["residue_count"],
                "decided_at": _dt.datetime.now(
                    _dt.timezone.utc
                ).isoformat(),
            })

        if audit_output and records:
            audit_path = Path(audit_output)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("w", encoding="utf-8") as fp:
                for rec in records:
                    fp.write(
                        json.dumps(rec, sort_keys=True, default=str)
                        + "\n"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"\nWave 4 escalation summary: "
            f"escalated={escalated}, remediated={remediated}, "
            f"future={future}, already-escalated={already}"
        ))

    # ------------------------------------------------------------------

    def _iter_decisions(self) -> Iterable[Dict[str, Any]]:
        """Walk the most-recent ``SCHEMA_EDITOR_RESIDUE_REMINDED``
        audit row per tenant and decide the verdict.

        The "most recent" filter is critical: a tenant might have
        been reminded twice (once forced, once after an idempotency
        window expired); only the latest reminder's deadline is
        load-bearing for escalation.
        """
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import is_structureless

        # Fetch all reminder rows ordered newest-first; keep only the
        # first (newest) per tenant.
        reminder_qs = (
            AuditEvent.objects.filter(
                action="SCHEMA_EDITOR_RESIDUE_REMINDED",
            )
            .select_related("tenant")
            .order_by("-timestamp")
        )
        latest_by_tenant: Dict[str, Any] = {}
        for row in reminder_qs:
            tenant = getattr(row, "tenant", None)
            if tenant is None:
                continue
            tid = str(tenant.id)
            if tid in latest_by_tenant:
                continue
            latest_by_tenant[tid] = row

        # Fetch any prior escalation rows in one query — used to
        # short-circuit double-escalation per (tenant, reminder).
        escalation_rows = (
            AuditEvent.objects.filter(
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
                tenant_id__in=list(latest_by_tenant.keys()),
            )
            .order_by("-timestamp")
        )
        latest_escalation_by_tenant: Dict[str, Any] = {}
        for row in escalation_rows:
            tid = str(getattr(row, "tenant_id", ""))
            if tid and tid not in latest_escalation_by_tenant:
                latest_escalation_by_tenant[tid] = row

        today = timezone.now().date()

        for tid, reminder in latest_by_tenant.items():
            details = getattr(reminder, "details_json", None) or {}
            raw_deadline = details.get("deadline")
            try:
                deadline = (
                    _dt.date.fromisoformat(str(raw_deadline))
                    if raw_deadline
                    else None
                )
            except (TypeError, ValueError):
                logger.warning(
                    "wave4_escalate_residue.malformed_deadline",
                    extra={"tenant_id": tid, "raw": raw_deadline},
                )
                continue
            if deadline is None:
                continue

            tenant = reminder.tenant
            residue_count_at_send = int(details.get("residue_count") or 0)

            # Verdict precedence: future-deadline → already-escalated
            # → remediated → escalate.
            if deadline >= today:
                yield {
                    "tenant": tenant,
                    "deadline": deadline.isoformat(),
                    "residue_count": residue_count_at_send,
                    "verdict": "future",
                }
                continue

            existing_escalation = latest_escalation_by_tenant.get(tid)
            if (
                existing_escalation is not None
                and existing_escalation.timestamp >= reminder.timestamp
            ):
                yield {
                    "tenant": tenant,
                    "deadline": deadline.isoformat(),
                    "residue_count": residue_count_at_send,
                    "verdict": "already-escalated",
                }
                continue

            # Re-check residue at run time — a tenant who fixed their
            # contracts the day before the deadline must not be
            # escalated.
            still_residue = 0
            for contract in (
                Contract.objects.filter(tenant=tenant)
                .only("id", "tenant_id", "hub_contract_json")
                .iterator(chunk_size=200)
            ):
                if is_structureless(contract):
                    still_residue += 1

            if still_residue == 0:
                yield {
                    "tenant": tenant,
                    "deadline": deadline.isoformat(),
                    "residue_count": 0,
                    "verdict": "remediated",
                }
                continue

            yield {
                "tenant": tenant,
                "deadline": deadline.isoformat(),
                "residue_count": still_residue,
                "verdict": "escalate",
            }

    def _emit_escalation_audit(
        self,
        *,
        tenant: Any,
        deadline: str,
        residue_count: int,
    ) -> None:
        from hub.apps.audit.utils import create_audit_event
        try:
            create_audit_event(
                resource_type="TENANT",
                action="STRUCTURELESS_RESIDUE_DEADLINE_PASSED",
                tenant=tenant,
                resource_id=str(tenant.id),
                details={
                    "phase": "227.W4.3",
                    "deadline": deadline,
                    "residue_count": residue_count,
                },
            )
        except Exception as exc:  # pragma: no cover — best-effort
            self.stdout.write(self.style.WARNING(
                f"  [warn] failed to emit escalation audit row "
                f"for {tenant.id}: {type(exc).__name__}: {exc}"
            ))
