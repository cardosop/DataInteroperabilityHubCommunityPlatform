"""
Phase 227 Wave 2 (227.W2.3) — batch dispatcher for the T-0
``SCHEMA_EDITOR_AVAILABLE`` announcement email.

Iterates tenants whose contracts violate the structural-floor
invariant and, for each one, calls
:func:`hub.apps.contracts.notifications.schema_editor_available.send_schema_editor_available_notification`.

Engineering invariants
----------------------
* **Idempotency** — per-tenant: a tenant with a recent
  ``SCHEMA_EDITOR_AVAILABLE_NOTIFIED`` audit row is skipped (so a
  re-run of the command never re-emails the same admins). Operator
  override via ``--force``; the forced re-send still records a fresh
  ``SCHEMA_EDITOR_AVAILABLE_NOTIFIED`` audit row so the audit trail
  shows the deliberate re-send.
* **Scope guard** — the default population is "tenants with
  structureless contracts". A tenant with all-clean contracts has no
  Schema editor work to do; emailing them is noise. ``--all-tenants``
  bypasses the guard for the rare case where ops wants to broadcast.
* **No-admin tenants are skipped, not crashed** — surfaces as a
  stderr warning. Same convention as the Wave 0 driver.
* **Dry-run** — ``--dry-run`` prints the per-tenant plan without
  invoking the email pipeline. Recommended first invocation.
* **Per-tenant failures fail open** — a tenant whose batch raises
  an unexpected exception logs the failure and the loop continues
  with the next tenant. Operators must read the summary at the end
  to find what to retry.
* **Audit trail** — ``--audit-output`` writes a per-dispatch JSONL
  line. Pair with the runbook's ``EmailDelivery`` SQL query for
  cross-channel verification.

Usage
-----
::

    # Plan only — recommended first run.
    python manage.py wave2_send_schema_editor_available_notifications --dry-run

    # Fire the announcement to every structureless-tenant.
    python manage.py wave2_send_schema_editor_available_notifications

    # Single-tenant escalation re-send (audit row is still written).
    python manage.py wave2_send_schema_editor_available_notifications \\
        --tenant-id=<uuid> --force

    # Broadcast to every active tenant (rare — bypasses scope guard).
    python manage.py wave2_send_schema_editor_available_notifications \\
        --all-tenants
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Iterable

from django.core.management.base import BaseCommand


# How long the idempotency window holds before a re-run is allowed
# without ``--force``. The W2 announcement is a one-shot rollout email,
# so a wide default (90 days) prevents accidental re-sends if the
# command is re-invoked. ``--idempotency-days`` lets ops shrink it.
DEFAULT_IDEMPOTENCY_DAYS = 90


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 2 (227.W2.3): dispatch the T-0 SCHEMA_EDITOR_AVAILABLE "
        "announcement email to TENANT_ADMINs of every tenant with "
        "structureless contracts. Idempotent — per-tenant audit-event "
        "check prevents duplicate sends."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--tenant-id",
            default=None,
            help=(
                "Restrict dispatch to a single tenant UUID. Without this "
                "flag the command iterates every tenant whose contracts "
                "violate the structural-floor invariant."
            ),
        )
        parser.add_argument(
            "--all-tenants",
            action="store_true",
            default=False,
            help=(
                "Broadcast to every active tenant — bypasses the default "
                "scope guard that limits emails to tenants with at least "
                "one structureless contract."
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
                "announcement within the idempotency window. The "
                "forced re-send still records a SCHEMA_EDITOR_AVAILABLE_NOTIFIED "
                "audit row so the audit trail captures the intent."
            ),
        )
        parser.add_argument(
            "--idempotency-days",
            type=int,
            default=DEFAULT_IDEMPOTENCY_DAYS,
            help=(
                "How many days back to look for an existing "
                "SCHEMA_EDITOR_AVAILABLE_NOTIFIED audit row. Defaults to "
                f"{DEFAULT_IDEMPOTENCY_DAYS}. Setting to 0 disables the "
                "check (equivalent to --force)."
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
        # Lazy imports keep the management-command import graph cheap.
        from hub.apps.contracts.notifications.schema_editor_available import (
            NoTenantAdminsError,
            send_schema_editor_available_notification,
        )
        from hub.apps.tenants.models import Tenant

        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        idempotency_days = max(0, int(options["idempotency_days"]))
        audit_output = options.get("audit_output")
        audit_records: list[dict[str, Any]] = []

        tenants = self._select_tenants(
            tenant_id=options.get("tenant_id"),
            all_tenants=options["all_tenants"],
        )

        if not tenants:
            self.stdout.write(self.style.WARNING(
                "  [no-op] no tenants matched the selection criteria"
            ))
            return

        sent_count = 0
        skipped_idem = 0
        skipped_no_admin = 0
        failed = 0

        for tenant in tenants:
            tenant_label = (
                f"{getattr(tenant, 'name', '?')} ({tenant.id})"
            )

            if not force and idempotency_days > 0:
                if self._already_notified(
                    tenant=tenant, days=idempotency_days,
                ):
                    self.stdout.write(self.style.WARNING(
                        f"  [skipped-idempotent] {tenant_label}: "
                        f"already notified within last "
                        f"{idempotency_days} day(s)"
                    ))
                    skipped_idem += 1
                    continue

            if dry_run:
                self.stdout.write(
                    f"  [dry-run] {tenant_label}: would notify "
                    "TENANT_ADMINs"
                )
                continue

            try:
                dispatched = send_schema_editor_available_notification(
                    tenant=tenant,
                )
            except NoTenantAdminsError:
                self.stdout.write(self.style.WARNING(
                    f"  [skipped-no-admin] {tenant_label}: no "
                    "TENANT_ADMIN — escalate per runbook §227.W2.3"
                ))
                skipped_no_admin += 1
                continue
            except Exception as exc:  # pragma: no cover — operator visibility
                self.stdout.write(self.style.ERROR(
                    f"  [failed] {tenant_label}: {type(exc).__name__}: {exc}"
                ))
                failed += 1
                continue

            success_count = sum(1 for d in dispatched if d.get("success"))
            error_count = len(dispatched) - success_count
            self.stdout.write(self.style.SUCCESS(
                f"  Notified {tenant_label}: "
                f"{success_count} succeeded, {error_count} failed"
            ))

            # Idempotency record — written ONLY when at least one
            # admin received the email. A 0/N batch (every recipient
            # bounced) leaves the tenant un-notified-for-real, so a
            # re-run can retry. Without this guard a transient SES
            # outage on the first run would never self-heal.
            if success_count > 0:
                self._record_notified_audit(tenant=tenant)
                sent_count += 1

            for d in dispatched:
                audit_records.append({
                    "tenant_id": str(tenant.id),
                    "tenant_name": getattr(tenant, "name", ""),
                    "to_email": d["to_email"],
                    "email_type": d["email_type"],
                    "success": d["success"],
                    "error": d["error"],
                    "dispatched_at": _dt.datetime.now(
                        _dt.timezone.utc
                    ).isoformat(),
                })

        if audit_output and audit_records:
            self._write_audit_jsonl(Path(audit_output), audit_records)

        # Summary — operator reads this to triage retries.
        self.stdout.write(self.style.SUCCESS(
            f"\nWave 2 announcement summary: "
            f"sent={sent_count}, "
            f"skipped-idempotent={skipped_idem}, "
            f"skipped-no-admin={skipped_no_admin}, "
            f"failed={failed}"
        ))

    # ------------------------------------------------------------------

    def _select_tenants(
        self, *, tenant_id: str | None, all_tenants: bool,
    ) -> list[Any]:
        """Return the ordered list of tenants to notify.

        Default scope: tenants with at least one structureless
        contract. ``--tenant-id`` selects a single row. ``--all-tenants``
        broadcasts to every active tenant.
        """
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import is_structureless
        from hub.apps.tenants.models import Tenant

        if tenant_id:
            try:
                return [Tenant.objects.get(id=tenant_id)]
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"  [warn] tenant_id={tenant_id} not in DB"
                ))
                return []

        if all_tenants:
            return list(Tenant.objects.filter(status="ACTIVE").order_by("id"))

        # Default: scope to tenants that own at least one structureless
        # contract. We walk the queryset rather than relying on a JSON
        # predicate filter (DB-portable + matches the canonical
        # ``is_structureless`` semantics exactly).
        seen_tenant_ids: set[Any] = set()
        scoped: list[Any] = []
        for contract in (
            Contract.objects.only("id", "tenant_id", "hub_contract_json")
            .iterator(chunk_size=200)
        ):
            if not is_structureless(contract):
                continue
            tenant_id_val = getattr(contract, "tenant_id", None)
            if tenant_id_val is None or tenant_id_val in seen_tenant_ids:
                continue
            seen_tenant_ids.add(tenant_id_val)

        if not seen_tenant_ids:
            return []
        return list(
            Tenant.objects.filter(id__in=seen_tenant_ids).order_by("id")
        )

    def _already_notified(self, *, tenant: Any, days: int) -> bool:
        """Return True if a SCHEMA_EDITOR_AVAILABLE_NOTIFIED audit row
        exists for this tenant in the last ``days`` days.

        Idempotency lives in the audit table (and not in a separate
        ``Tenant.schema_editor_announcement_sent_at`` column) because
        the audit table is already the durable source of truth for
        notification dispatches and matches the Wave 0 convention.
        """
        from datetime import timedelta as _td

        from django.utils import timezone

        from hub.apps.audit.models import AuditEvent

        cutoff = timezone.now() - _td(days=days)
        return AuditEvent.objects.filter(
            tenant=tenant,
            action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
            timestamp__gte=cutoff,
        ).exists()

    def _record_notified_audit(self, *, tenant: Any) -> None:
        """Write the SCHEMA_EDITOR_AVAILABLE_NOTIFIED audit row that
        guards the next re-run from re-emailing this tenant."""
        from hub.apps.audit.utils import create_audit_event
        try:
            create_audit_event(
                resource_type="TENANT",
                action="SCHEMA_EDITOR_AVAILABLE_NOTIFIED",
                tenant=tenant,
                resource_id=str(tenant.id),
                details={"phase": "227.W2.3"},
            )
        except Exception as exc:  # pragma: no cover — audit best-effort
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
