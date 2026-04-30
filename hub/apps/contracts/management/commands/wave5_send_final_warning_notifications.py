"""
Phase 227 Wave 5 (227.W5.1) — batch dispatcher for the T+30 final
warning notification.

Iterates the cohort of tenants whose **currently-active** contracts
are still structureless and dispatches the
:func:`hub.apps.contracts.notifications.asset_auto_revert_warning.send_final_warning_notification`
helper per tenant. This is the last customer-action window before
the W5 ``--apply-asset-revert`` sweep.

Engineering invariants
----------------------
* **Default scope guard** — without ``--tenant-id`` or
  ``--all-tenants``, the driver targets only tenants that actually
  have at least one structureless ACTIVE contract. Sending the
  final warning to an already-clean tenant is noise that erodes
  email trust.
* **Idempotency** — per-tenant: a tenant with a recent
  ``ASSET_AUTO_REVERT_WARNING_NOTIFIED`` audit row is skipped (so a
  re-run never re-emails the same admins). Operator override via
  ``--force``; the forced re-send still records a fresh audit row
  capturing the deliberate intent.
* **Critical idempotency sub-invariant** — the audit row is written
  ONLY when at least one admin received the email. An all-failed
  batch (transient SES outage) leaves the tenant un-notified-for-
  real so a retry can self-heal. Same convention as the W2 / W4
  drivers (see W2.3-AUDIT-2 closeout).
* **Drift guard** — every contract id is re-loaded from the DB
  before dispatch and rows that are no longer structureless are
  excluded from the email body.
* **No-admin tenants are skipped, not crashed** — surfaced as
  ``[skipped-no-admin]`` in stdout so ops can re-grant the role.
* **Dry-run** — ``--dry-run`` prints the per-tenant plan without
  invoking the email pipeline.
* **Audit trail** — ``--audit-output`` writes a per-dispatch JSONL
  line for cross-checking against ``EmailDelivery`` rows.
* **Deadline validation** — ``--deadline`` must be a valid ISO date
  strictly in the future. A past or malformed deadline raises
  ``CommandError``.

Usage
-----
::

    # Plan only — recommended first run.
    python manage.py wave5_send_final_warning_notifications \\
        --deadline=2026-06-15 --dry-run

    # Fire the warning for every tenant with structureless ACTIVE contracts.
    python manage.py wave5_send_final_warning_notifications \\
        --deadline=2026-06-15

    # Single-tenant escalation re-send (audit row written either way).
    python manage.py wave5_send_final_warning_notifications \\
        --deadline=2026-06-15 --tenant-id=<uuid> --force
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Iterable

from django.core.management.base import BaseCommand, CommandError


DEFAULT_IDEMPOTENCY_DAYS = 14
W51_AUDIT_ACTION = "ASSET_AUTO_REVERT_WARNING_NOTIFIED"


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 5 (227.W5.1): dispatch the T+30 final warning "
        "to TENANT_ADMINs of every tenant whose currently-active "
        "contracts remain structureless 14 days before W5 cutover. "
        "Idempotent — per-tenant audit-event check prevents duplicate "
        "sends."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--deadline",
            required=True,
            help=(
                "Customer-facing W5 cutover date as ISO date "
                "(YYYY-MM-DD). Must be in the future. The W5 "
                "auto-revert sweep is intended to run on or after "
                "this date."
            ),
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help=(
                "Restrict dispatch to a single tenant UUID. Without "
                "this flag the command iterates every tenant with at "
                "least one structureless ACTIVE contract."
            ),
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            default=False,
            help=(
                "Bypass the default scope guard and broadcast to "
                "every tenant in the system, even those with no "
                "structureless contracts. Use only for explicit "
                "broadcast operations; the default scope is what you "
                "almost always want."
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
                "warning within the idempotency window. The forced "
                f"re-send still records a {W51_AUDIT_ACTION} audit "
                "row so the trail captures the deliberate intent."
            ),
        )
        parser.add_argument(
            "--idempotency-days",
            type=int,
            default=DEFAULT_IDEMPOTENCY_DAYS,
            help=(
                f"How many days back to look for an existing "
                f"{W51_AUDIT_ACTION} audit row. Defaults to "
                f"{DEFAULT_IDEMPOTENCY_DAYS}. 0 disables the check."
            ),
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
        from hub.apps.contracts.notifications.asset_auto_revert_warning import (
            NoTenantAdminsError,
            send_final_warning_notification,
        )

        deadline = self._parse_deadline(options["deadline"])
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        all_tenants: bool = options["all_tenants"]
        tenant_id: str | None = options.get("tenant_id")
        idempotency_days = max(0, int(options["idempotency_days"]))
        audit_output = options.get("audit_output")
        audit_records: list[dict[str, Any]] = []

        residue_rows = self._load_cohort(
            tenant_id=tenant_id,
            all_tenants=all_tenants,
        )
        if not residue_rows:
            self.stdout.write(self.style.WARNING(
                "  [no-op] no tenants with structureless ACTIVE "
                "contracts found"
            ))
            self.stdout.write(self.style.SUCCESS(
                "\nWave 5 final-warning summary: "
                "sent=0, skipped-idempotent=0, skipped-no-admin=0, failed=0"
            ))
            return

        sent_count = 0
        skipped_idem = 0
        skipped_no_admin = 0
        failed = 0

        for row in residue_rows:
            tenant = row["tenant"]
            tenant_label = (
                f"{getattr(tenant, 'name', '?')} ({tenant.id})"
            )

            if not force and idempotency_days > 0:
                if self._already_warned(
                    tenant=tenant, days=idempotency_days,
                ):
                    self.stdout.write(self.style.WARNING(
                        f"  [skipped-idempotent] {tenant_label}: "
                        f"warning sent within last "
                        f"{idempotency_days} day(s)"
                    ))
                    skipped_idem += 1
                    continue

            still_residue = row["contracts"]

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {tenant_label}: "
                    f"{len(still_residue)} structureless ACTIVE "
                    f"contract(s) → would notify TENANT_ADMINs "
                    f"(deadline {deadline.isoformat()})"
                )
                continue

            try:
                dispatched = send_final_warning_notification(
                    tenant=tenant,
                    structureless_contracts=still_residue,
                    deadline=deadline,
                )
            except NoTenantAdminsError:
                self.stdout.write(self.style.WARNING(
                    f"  [skipped-no-admin] {tenant_label}: no "
                    "TENANT_ADMIN — escalate per runbook §227.W5.1"
                ))
                skipped_no_admin += 1
                continue
            except Exception as exc:  # pragma: no cover — operator visibility
                self.stdout.write(self.style.ERROR(
                    f"  [failed] {tenant_label}: "
                    f"{type(exc).__name__}: {exc}"
                ))
                failed += 1
                continue

            success_count = sum(1 for d in dispatched if d.get("success"))
            error_count = len(dispatched) - success_count
            self.stdout.write(self.style.SUCCESS(
                f"  Warned {tenant_label}: "
                f"{success_count} succeeded, {error_count} failed, "
                f"{len(still_residue)} structureless ACTIVE contract(s)"
            ))

            # Critical idempotency sub-invariant — only when ≥1 admin
            # actually received the email. All-failed batch leaves
            # the tenant un-notified-for-real so a retry can self-heal.
            if success_count > 0:
                self._record_warned_audit(
                    tenant=tenant,
                    deadline=deadline,
                    residue_count=len(still_residue),
                )
                sent_count += 1

            for d in dispatched:
                audit_records.append({
                    "tenant_id": str(tenant.id),
                    "tenant_name": getattr(tenant, "name", ""),
                    "to_email": d["to_email"],
                    "email_type": d["email_type"],
                    "success": d["success"],
                    "error": d["error"],
                    "deadline": deadline.isoformat(),
                    "residue_count": len(still_residue),
                    "dispatched_at": _dt.datetime.now(
                        _dt.timezone.utc,
                    ).isoformat(),
                })

        if audit_output and audit_records:
            self._write_audit_jsonl(Path(audit_output), audit_records)

        self.stdout.write(self.style.SUCCESS(
            f"\nWave 5 final-warning summary: "
            f"sent={sent_count}, "
            f"skipped-idempotent={skipped_idem}, "
            f"skipped-no-admin={skipped_no_admin}, "
            f"failed={failed}"
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
    def _load_cohort(
        *, tenant_id: str | None, all_tenants: bool,
    ) -> list[dict[str, Any]]:
        """Build the (tenant, structureless ACTIVE contracts) tuples
        to dispatch. Default scope: only tenants whose currently-
        ACTIVE contracts include at least one structureless row.
        ``--all-tenants`` bypasses the scope guard. ``--tenant-id``
        narrows to a single tenant regardless of scope."""
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import is_structureless
        from hub.apps.tenants.models import Tenant

        # 1) Pick the tenant universe.
        if tenant_id:
            tenants = list(Tenant.objects.filter(id=tenant_id))
        elif all_tenants:
            tenants = list(Tenant.objects.all())
        else:
            # Default scope — only tenants with at least one
            # structureless ACTIVE contract. Apply the canonical
            # Python predicate at iteration time to catch payloads
            # the coarse SQL filter would miss
            # (e.g. ``models=[{"fields": []}]``).
            tenants_with_residue: list[Any] = []
            seen: set = set()
            for c in (
                Contract.objects.filter(status="ACTIVE")
                .select_related("tenant")
                .iterator(chunk_size=200)
            ):
                if c.tenant_id in seen:
                    continue
                if is_structureless(c):
                    seen.add(c.tenant_id)
                    if c.tenant is not None:
                        tenants_with_residue.append(c.tenant)
            tenants = tenants_with_residue

        # 2) For each tenant, collect the structureless ACTIVE
        # contracts we want to surface in the email. Drift-guard at
        # iteration time so a contract remediated between cohort
        # selection and dispatch is excluded.
        #
        # SELF-AUDIT-1: skip empty-residue tenants in ALL modes. The
        # email body says "you have N structureless contracts" — sending
        # to a tenant with N=0 is a lie. Pre-fix, ``--all-tenants`` and
        # ``--tenant-id`` bypassed this check; both spec and template
        # contract require the residue precondition. ``--all-tenants``
        # still has value as a debug enumeration (it cross-checks the
        # default scope query by walking the Tenant table directly
        # rather than deriving from Contract rows), but it must not
        # email clean tenants.
        rows: list[dict[str, Any]] = []
        for tenant in tenants:
            residue: list[Any] = []
            for c in Contract.objects.filter(
                tenant=tenant,
                status="ACTIVE",
            ):
                if is_structureless(c):
                    residue.append(c)
            if not residue:
                continue
            rows.append({"tenant": tenant, "contracts": residue})
        return rows

    def _already_warned(self, *, tenant: Any, days: int) -> bool:
        """True if a ``ASSET_AUTO_REVERT_WARNING_NOTIFIED`` audit row
        exists for this tenant in the last ``days`` days."""
        from datetime import timedelta as _td

        from django.utils import timezone

        from hub.apps.audit.models import AuditEvent

        cutoff = timezone.now() - _td(days=days)
        return AuditEvent.objects.filter(
            tenant=tenant,
            action=W51_AUDIT_ACTION,
            timestamp__gte=cutoff,
        ).exists()

    def _record_warned_audit(
        self, *, tenant: Any, deadline: _dt.date, residue_count: int,
    ) -> None:
        """Write the ``ASSET_AUTO_REVERT_WARNING_NOTIFIED`` audit row
        that guards the next re-run from re-emailing this tenant.

        The deadline + residue_count are stored in ``details_json`` so
        ops can correlate the at-send-time deadline (vs guessing from
        a config file)."""
        from hub.apps.audit.utils import create_audit_event
        try:
            create_audit_event(
                resource_type="TENANT",
                action=W51_AUDIT_ACTION,
                tenant=tenant,
                resource_id=str(tenant.id),
                details={
                    "phase": "227.W5.1",
                    "deadline": deadline.isoformat(),
                    "residue_count": residue_count,
                },
            )
        except Exception as exc:  # pragma: no cover — best-effort
            self.stdout.write(self.style.WARNING(
                f"  [warn] failed to record audit row for "
                f"{tenant.id}: {type(exc).__name__}: {exc}"
            ))

    @staticmethod
    def _write_audit_jsonl(
        path: Path, records: Iterable[dict[str, Any]],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fp:
            for rec in records:
                fp.write(json.dumps(rec, sort_keys=True, default=str) + "\n")
