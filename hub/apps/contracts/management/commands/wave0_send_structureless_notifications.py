"""
Phase 227 Wave 0 (227.0.3) — batch dispatcher for the structureless-
contract T-14 heads-up notification.

Reads a JSONL artefact (output of ``wave0_capture_structureless``),
groups contract rows by tenant, and for each affected tenant calls
:func:`hub.apps.contracts.notifications.structureless.send_structureless_contract_pending_notification`.

Engineering invariants
----------------------
* **Drift guard** — every contract id from the JSONL is re-loaded from
  the DB before dispatch, and rows that are no longer structureless
  (per the canonical predicate) are excluded from the email body.
  Customers must not receive a notification listing already-remediated
  contracts.
* **No-admin tenants are skipped, not crashed** — a tenant with zero
  TENANT_ADMINs surfaces as a stderr warning and the dispatcher
  continues with other tenants. Operators must follow runbook §227.0.3
  to escalate, then re-run for the affected tenant.
* **Dry-run** — `--dry-run` prints a per-tenant fan-out plan without
  invoking the email pipeline. This is the recommended first invocation
  for every Wave 0 batch.
* **Audit trail** — `--audit-output` writes a per-dispatch JSONL line
  with tenant_id, recipients, deadline, and contract_count. Pair with
  the runbook's `EmailDelivery` SQL query for cross-channel verification.
* **Deadline validation** — must be a valid ISO date and strictly in
  the future. A past or malformed deadline raises ``CommandError``.
"""
from __future__ import annotations

import datetime as _dt
import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 0 (227.0.3): dispatch the T-14 heads-up email to "
        "TENANT_ADMINs of tenants whose contracts appear in the JSONL artefact."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            required=True,
            help="JSONL artefact produced by wave0_capture_structureless.",
        )
        parser.add_argument(
            "--deadline",
            required=True,
            help=(
                "Wave-5 customer deadline as ISO date (YYYY-MM-DD). "
                "Must be in the future."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Plan + count only; do not invoke the email pipeline.",
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict dispatch to a single tenant UUID.",
        )
        parser.add_argument(
            "--audit-output",
            default=None,
            help=(
                "Path to write a per-dispatch JSONL audit trail. "
                "Useful for cross-checking against EmailDelivery rows."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        deadline = self._parse_deadline(options["deadline"])
        input_path = Path(options["input"])
        if not input_path.exists():
            raise CommandError(f"Input file not found: {input_path}")

        rows_by_tenant = self._load_rows_grouped_by_tenant(input_path)

        if options.get("tenant_id"):
            rows_by_tenant = {
                tid: rows for tid, rows in rows_by_tenant.items()
                if tid == options["tenant_id"]
            }

        dry_run: bool = options["dry_run"]
        audit_output = options.get("audit_output")
        audit_records: list[dict] = []

        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.notifications.structureless import (
            NoTenantAdminsError,
            send_structureless_contract_pending_notification,
        )
        from hub.apps.contracts.structureless import is_structureless
        from hub.apps.tenants.models import Tenant

        for tenant_id, rows in rows_by_tenant.items():
            if tenant_id is None:
                self.stdout.write(self.style.WARNING(
                    "  [warn] skipping rows with null tenant_id"
                ))
                continue
            try:
                tenant = Tenant.objects.get(id=tenant_id)
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  [warn] skipping tenant_id={tenant_id} — not in DB"
                ))
                continue

            # Drift guard: re-load each contract and exclude any that
            # are no longer structureless.
            contract_ids = [r["contract_id"] for r in rows]
            current_contracts = list(
                Contract.objects.filter(id__in=contract_ids)
            )
            still_structureless = [
                c for c in current_contracts if is_structureless(c)
            ]
            remediated_ids = [
                str(c.id) for c in current_contracts
                if not is_structureless(c)
            ]
            for cid in remediated_ids:
                self.stdout.write(self.style.WARNING(
                    f"  [skipped] {cid} no longer structureless (remediated since capture)"
                ))

            tenant_label = getattr(tenant, "name", str(tenant_id))

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {tenant_label} ({tenant_id}): "
                    f"{len(still_structureless)} contract(s) → "
                    f"would notify TENANT_ADMINs"
                )
                continue

            try:
                dispatched = send_structureless_contract_pending_notification(
                    tenant=tenant,
                    structureless_contracts=still_structureless,
                    deadline=deadline,
                )
            except NoTenantAdminsError:
                self.stdout.write(self.style.WARNING(
                    f"  [skipped] {tenant_label} ({tenant_id}): "
                    f"no TENANT_ADMIN — escalate per runbook §227.0.3"
                ))
                continue

            self.stdout.write(self.style.SUCCESS(
                f"  Notified {tenant_label} ({tenant_id}): "
                f"{len(dispatched)} email(s) — "
                f"{len(still_structureless)} contract(s)"
            ))

            for d in dispatched:
                audit_records.append({
                    "tenant_id": str(tenant_id),
                    "tenant_name": tenant_label,
                    "to_email": d["to_email"],
                    "email_type": d["email_type"],
                    "deadline": deadline.isoformat(),
                    "contract_count": len(still_structureless),
                    "dispatched_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
                })

        if audit_output and audit_records:
            audit_path = Path(audit_output)
            audit_path.parent.mkdir(parents=True, exist_ok=True)
            with audit_path.open("w", encoding="utf-8") as fp:
                for rec in audit_records:
                    fp.write(json.dumps(rec, sort_keys=True) + "\n")
            self.stdout.write(self.style.SUCCESS(
                f"  Audit trail written to {audit_path} "
                f"({len(audit_records)} record(s))"
            ))

    # ------------------------------------------------------------------

    @staticmethod
    def _parse_deadline(raw: str) -> _dt.date:
        try:
            d = _dt.date.fromisoformat(raw)
        except (TypeError, ValueError) as exc:
            raise CommandError(
                f"--deadline must be ISO date (YYYY-MM-DD); got {raw!r}"
            ) from exc
        if d <= _dt.date.today():
            raise CommandError(
                f"--deadline must be in the future; got {raw} "
                f"(today is {_dt.date.today().isoformat()})"
            )
        return d

    @staticmethod
    def _load_rows_grouped_by_tenant(path: Path) -> dict[str | None, list[dict]]:
        groups: dict[str | None, list[dict]] = defaultdict(list)
        with path.open("r", encoding="utf-8") as fp:
            for raw in fp:
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict) or "contract_id" not in obj:
                    continue
                groups[obj.get("tenant_id")].append(obj)
        return dict(groups)
