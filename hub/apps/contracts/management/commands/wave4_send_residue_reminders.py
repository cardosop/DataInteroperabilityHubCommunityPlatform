"""
Phase 227 Wave 4 (227.W4.2) — batch dispatcher for the T+7 residue
reminder.

Iterates the residue cohort produced by
:func:`hub.apps.contracts.management.commands.wave4_classify_residue.classify_tenants_by_residue`
and dispatches the
:func:`hub.apps.contracts.notifications.schema_editor_residue_reminder.send_schema_editor_residue_reminder`
helper per tenant.

Engineering invariants
----------------------
* **Drift guard** — every contract id from the classifier is re-loaded
  from the DB before dispatch and rows that are no longer
  structureless are excluded from the email body.  Customers must
  not receive a residue reminder listing an already-remediated
  contract; the gap between classification and dispatch can be
  hours when ops runs the two as separate steps.
* **Idempotency** — per-tenant: a tenant with a recent
  ``SCHEMA_EDITOR_RESIDUE_REMINDED`` audit row is skipped (so a
  re-run of the command never re-emails the same admins).
  Operator override via ``--force``; the forced re-send still
  records a fresh audit row so the trail captures the deliberate
  intent.
* **Critical idempotency sub-invariant** — the audit row is written
  ONLY when at least one admin received the email.  An all-failed
  batch (transient SES outage) leaves the tenant un-notified-for-real
  so a retry can self-heal.  Same convention as the W2 driver.
* **No-admin tenants are skipped, not crashed** — the Wave 0 + W2
  convention.
* **Dry-run** — ``--dry-run`` prints the per-tenant plan without
  invoking the email pipeline.
* **Audit trail** — ``--audit-output`` writes a per-dispatch JSONL
  line.  Pair with the runbook's ``EmailDelivery`` SQL query for
  cross-channel verification.
* **Deadline validation** — ``--deadline`` must be a valid ISO date
  strictly in the future.  A past or malformed deadline raises
  ``CommandError`` so ops can never accidentally send a reminder
  with a deadline of yesterday.

Usage
-----
::

    # Plan only — recommended first run.
    python manage.py wave4_send_residue_reminders \\
        --deadline=2026-06-01 --dry-run

    # Fire the reminder for every residue tenant.
    python manage.py wave4_send_residue_reminders \\
        --deadline=2026-06-01

    # Single-tenant escalation re-send (audit row written either way).
    python manage.py wave4_send_residue_reminders \\
        --deadline=2026-06-01 --tenant-id=<uuid> --force
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

DEFAULT_IDEMPOTENCY_DAYS = 30


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 4 (227.W4.2): dispatch the T+7 residue reminder "
        "to TENANT_ADMINs of every tenant whose contracts remain "
        "structureless after Wave 3.  Idempotent — per-tenant audit-"
        "event check prevents duplicate sends."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--deadline",
            required=True,
            help=(
                "Customer-facing remediation cutoff as ISO date "
                "(YYYY-MM-DD).  Must be in the future.  Matches the "
                "W4.3 escalation cron's deadline.  Conventionally "
                "30 days after the reminder send date."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help=(
                "Restrict dispatch to a single tenant UUID.  Without "
                "this flag the command iterates the residue cohort."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Plan + count only; do not invoke the email pipeline.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help=(
                "Re-send to tenants that have already received the "
                "reminder within the idempotency window.  The forced "
                "re-send still records a SCHEMA_EDITOR_RESIDUE_REMINDED "
                "audit row so the trail captures the intent."
            ),
        )
        parser.add_argument(
            "--idempotency-days",
            type=int,
            default=DEFAULT_IDEMPOTENCY_DAYS,
            help=(
                "How many days back to look for an existing "
                "SCHEMA_EDITOR_RESIDUE_REMINDED audit row.  Defaults "
                f"to {DEFAULT_IDEMPOTENCY_DAYS}.  0 disables the check."
            ),
        )
        parser.add_argument(
            "--audit-output",
            default=None,
            help=(
                "Path to write a per-dispatch JSONL audit trail.  "
                "Useful for cross-checking against EmailDelivery rows."
            ),
        )
        # Phase 227 W4 audit (W4.2/W4.3-AUDIT-1) — match the W4.4
        # smoke gate's scope so a tenant whose only structureless
        # contract is a DRAFT (data-engineer's edit buffer) doesn't
        # get reminded + escalated for a workflow that isn't broken.
        parser.add_argument(
            "--include-active-only",
            action="store_true",
            default=False,
            help=(
                "Only count ACTIVE structureless contracts as residue. "
                "Mirrors the W4.4 smoke-gate scope; without this flag "
                "DRAFT residue (data-engineer edit buffer) and RETIRED "
                "residue (tombstones) trigger reminders too."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        from hub.apps.contracts.notifications.schema_editor_residue_reminder import (
            NoTenantAdminsError,
            send_schema_editor_residue_reminder,
        )

        deadline = self._parse_deadline(options["deadline"])
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        idempotency_days = max(0, int(options["idempotency_days"]))
        audit_output = options.get("audit_output")
        active_only = bool(options.get("include_active_only"))
        audit_records: list[dict[str, Any]] = []

        residue_rows = self._load_residue_cohort(
            tenant_id=options.get("tenant_id"),
            active_only=active_only,
        )
        if not residue_rows:
            self.stdout.write(
                self.style.WARNING("  [no-op] no tenants with residue contracts found")
            )
            return

        sent_count = 0
        skipped_idem = 0
        skipped_no_admin = 0
        failed = 0

        for row in residue_rows:
            tenant = row["tenant"]
            tenant_label = f"{getattr(tenant, 'name', '?')} ({tenant.id})"

            if (
                not force
                and idempotency_days > 0
                and self._already_reminded(
                    tenant=tenant,
                    days=idempotency_days,
                )
            ):
                self.stdout.write(
                    self.style.WARNING(
                        f"  [skipped-idempotent] {tenant_label}: "
                        f"reminder sent within last "
                        f"{idempotency_days} day(s)"
                    )
                )
                skipped_idem += 1
                continue

            still_residue_contracts = row["contracts"]
            if not still_residue_contracts:
                # Drift guard: every contract was remediated between
                # classification and dispatch.  Skip — sending an
                # empty reminder would confuse the admin.
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [drift-clean] {tenant_label}: every residue "
                        "contract was remediated since classification"
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {tenant_label}: "
                    f"{len(still_residue_contracts)} residue contract(s)"
                    f" → would notify TENANT_ADMINs (deadline "
                    f"{deadline.isoformat()})"
                )
                continue

            try:
                dispatched = send_schema_editor_residue_reminder(
                    tenant=tenant,
                    structureless_contracts=still_residue_contracts,
                    deadline=deadline,
                )
            except NoTenantAdminsError:
                self.stdout.write(
                    self.style.WARNING(
                        f"  [skipped-no-admin] {tenant_label}: no "
                        "TENANT_ADMIN — escalate per runbook §227.W4.2"
                    )
                )
                skipped_no_admin += 1
                continue
            except Exception as exc:  # pragma: no cover — operator visibility
                self.stdout.write(
                    self.style.ERROR(f"  [failed] {tenant_label}: {type(exc).__name__}: {exc}")
                )
                failed += 1
                continue

            success_count = sum(1 for d in dispatched if d.get("success"))
            error_count = len(dispatched) - success_count
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Reminded {tenant_label}: "
                    f"{success_count} succeeded, {error_count} failed, "
                    f"{len(still_residue_contracts)} residue contract(s)"
                )
            )

            # Idempotency record — only when at least one admin got
            # the email.  Same critical invariant as the W2 driver.
            if success_count > 0:
                self._record_reminded_audit(
                    tenant=tenant,
                    deadline=deadline,
                    residue_count=len(still_residue_contracts),
                )
                sent_count += 1

            for d in dispatched:
                audit_records.append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": getattr(tenant, "name", ""),
                        "to_email": d["to_email"],
                        "email_type": d["email_type"],
                        "success": d["success"],
                        "error": d["error"],
                        "deadline": deadline.isoformat(),
                        "residue_count": len(still_residue_contracts),
                        "dispatched_at": _dt.datetime.now(
                            _dt.UTC,
                        ).isoformat(),
                    }
                )

        if audit_output and audit_records:
            self._write_audit_jsonl(Path(audit_output), audit_records)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nWave 4 reminder summary: "
                f"sent={sent_count}, "
                f"skipped-idempotent={skipped_idem}, "
                f"skipped-no-admin={skipped_no_admin}, "
                f"failed={failed}"
            )
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_deadline(raw: str) -> _dt.date:
        try:
            d = _dt.date.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"--deadline must be ISO date (YYYY-MM-DD); got {raw!r}") from exc
        if d <= _dt.date.today():
            raise CommandError(
                f"--deadline must be in the future; got {raw} "
                f"(today is {_dt.date.today().isoformat()})"
            )
        return d

    def _load_residue_cohort(
        self,
        *,
        tenant_id: str | None,
        active_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Build the (tenant, residue contracts) tuples to dispatch.

        Re-loads each contract row from the DB at dispatch time so
        ones remediated between classification and send are excluded
        from the email body.  Returns the **drift-guarded** list, not
        the original classifier output.
        """
        from hub.apps.contracts.management.commands.wave4_classify_residue import (
            classify_tenants_by_residue,
        )
        from hub.apps.contracts.models import Contract, ContractStatus
        from hub.apps.contracts.structureless import is_structureless
        from hub.apps.tenants.models import Tenant

        cohort = classify_tenants_by_residue(
            tenant_id=tenant_id,
            active_only=active_only,
        )
        residue_rows = [r for r in cohort if r["cohort"] == "residue"]
        if not residue_rows:
            return []

        # Hydrate the Tenant + Contract rows in two bulk queries.
        tenant_ids = [r["tenant_id"] for r in residue_rows]
        tenants_by_id = {str(t.id): t for t in Tenant.objects.filter(id__in=tenant_ids)}
        all_contract_ids = {cid for r in residue_rows for cid in r["residue_contract_ids"]}
        contracts_by_id = {str(c.id): c for c in Contract.objects.filter(id__in=all_contract_ids)}

        result: list[dict[str, Any]] = []
        for r in residue_rows:
            tenant = tenants_by_id.get(r["tenant_id"])
            if tenant is None:
                continue
            still_residue: list[Any] = []
            for cid in r["residue_contract_ids"]:
                contract = contracts_by_id.get(cid)
                if contract is None:
                    continue
                # Drift-guard: a contract remediated between classify
                # and dispatch must not appear in the email body.
                if not is_structureless(contract):
                    continue
                # Active-only enforcement at dispatch time too: a
                # contract demoted from ACTIVE to DRAFT between
                # classify and dispatch shouldn't drag the tenant
                # into the reminder under active_only mode.
                if active_only and getattr(contract, "status", None) != ContractStatus.ACTIVE:
                    continue
                still_residue.append(contract)
            result.append({"tenant": tenant, "contracts": still_residue})
        return result

    def _already_reminded(self, *, tenant: Any, days: int) -> bool:
        """True if a SCHEMA_EDITOR_RESIDUE_REMINDED audit row exists
        for this tenant in the last ``days`` days."""
        from datetime import timedelta as _td

        from django.utils import timezone

        from hub.apps.audit.models import AuditEvent

        cutoff = timezone.now() - _td(days=days)
        return AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_RESIDUE_REMINDED",
            timestamp__gte=cutoff,
        ).exists()

    def _record_reminded_audit(
        self,
        *,
        tenant: Any,
        deadline: _dt.date,
        residue_count: int,
    ) -> None:
        """Write the SCHEMA_EDITOR_RESIDUE_REMINDED audit row that
        guards the next re-run from re-emailing this tenant.

        The deadline + residue_count are stored in ``details_json``
        so the W4.3 escalation cron can replay the at-send-time
        deadline (vs guessing from a config file)."""
        from hub.apps.audit.utils import create_audit_event

        try:
            create_audit_event(
                resource_type="TENANT",
                action="SCHEMA_EDITOR_RESIDUE_REMINDED",
                tenant=tenant,
                resource_id=str(tenant.id),
                details={
                    "phase": "227.W4.2",
                    "deadline": deadline.isoformat(),
                    "residue_count": residue_count,
                },
            )
        except Exception as exc:  # pragma: no cover — best-effort
            self.stdout.write(
                self.style.WARNING(
                    f"  [warn] failed to record audit row for "
                    f"{tenant.id}: {type(exc).__name__}: {exc}"
                )
            )

    @staticmethod
    def _write_audit_jsonl(
        path: Path,
        records: Iterable[dict[str, Any]],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            for rec in records:
                fp.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
