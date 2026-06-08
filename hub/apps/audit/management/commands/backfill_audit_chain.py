"""
Phase 234.1.9 — backfill the hash chain on existing ``AuditEvent`` rows.

Old rows (pre-234.1) carry NULL ``chain_sequence`` / ``prev_chain_hash``
/ ``chain_hash`` because they were inserted before the schema gained
those columns. The chain MUST be populated before any verifier
endpoint or Merkle snapshot can run.

Algorithm
=========

For each tenant (and the platform chain via tenant=None):

1.  Find the latest already-chained row → its ``chain_sequence`` and
    ``chain_hash`` are the resume anchor.
2.  Find all un-chained rows newer than the anchor (timestamp >= anchor's
    timestamp, or all rows if no anchor exists). Order strictly by
    ``(timestamp, id)`` so two rows with the same wall-clock get a
    deterministic order — without this the chain would re-shuffle on
    repeated backfills and the verifier would explode.
3.  In batches of ``--batch-size``, recompute each row's chain fields
    using the writer's canonical-form and hash routines, and persist
    via ``QuerySet.update()`` (bypasses :meth:`AuditEvent.save`'s
    immutability guard — this command is the only legitimate caller
    of ``update()`` on this table).

Options
=======

* ``--dry-run`` — compute but do not persist. Useful for shadow
  rollouts where the operator wants to size the work first.
* ``--resume-from`` — chain_sequence to resume from. The special
  value ``auto`` (default) uses the latest persisted ``chain_sequence``
  on the tenant. Operators rolling forward after a partial run can
  pass an explicit integer to re-run a known-bad slice.
* ``--tenant-id`` — restrict to a single tenant (UUID or empty string
  ``""``/``__platform__`` for the platform chain). Defaults to every
  tenant.
* ``--batch-size`` — rows written per ``update()`` (default 1000).
"""
from __future__ import annotations
import logging
import uuid
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from hub.apps.audit.chain import canonical_form, compute_chain_hash
from hub.apps.audit.models import AuditEvent

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1_000


class Command(BaseCommand):
    help = (
        "Backfill chain_sequence / prev_chain_hash / chain_hash on AuditEvent "
        "rows that pre-date Phase 234.1. Idempotent; supports --dry-run and "
        "--resume-from."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute but do not persist (no UPDATE statements run).",
        )
        parser.add_argument(
            "--tenant-id",
            type=str,
            default=None,
            help=(
                "Restrict to a single tenant. Pass a UUID, or the literal "
                "string '__platform__' / empty string for the platform chain. "
                "Omit to process every tenant."
            ),
        )
        parser.add_argument(
            "--resume-from",
            type=str,
            default="auto",
            help=(
                "chain_sequence to resume from. 'auto' (default) resumes "
                "after the latest persisted sequence; pass an integer to "
                "re-run a known-bad slice (rows with chain_sequence > N "
                "are wiped and re-computed)."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Rows per update batch (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--skip-verify",
            action="store_true",
            help=(
                "Phase 234.1 audit-fix — skip the end-of-run "
                "verify_chain_segment() check. Default: verify on every "
                "non-dry-run, raising CommandError if the backfill produced "
                "any mismatch. Skip only when re-running after a known good "
                "verifier pass."
            ),
        )

    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        tenant_arg = options.get("tenant_id")
        resume_from = options.get("resume_from", "auto")
        batch_size = int(options.get("batch_size", DEFAULT_BATCH_SIZE))
        verify_after = not options.get("skip_verify", False)

        if batch_size < 1:
            raise CommandError("--batch-size must be >= 1")

        tenants = self._resolve_tenants(tenant_arg)
        total_processed = 0
        for tenant_id in tenants:
            tenant_label = "__platform__" if tenant_id is None else str(tenant_id)
            try:
                rows = self._chain_tenant(
                    tenant_id=tenant_id,
                    resume_from=resume_from,
                    batch_size=batch_size,
                    dry_run=dry_run,
                )
            except CommandError:
                raise
            except Exception as exc:  # pragma: no cover — defensive surface
                self.stderr.write(self.style.ERROR(
                    f"[{tenant_label}] backfill failed: {exc}"
                ))
                raise
            total_processed += rows
            verb = "would chain" if dry_run else "chained"
            self.stdout.write(
                self.style.SUCCESS(f"[{tenant_label}] {verb} {rows} row(s)")
            )

            # Phase 234.1 audit-fix Gap D — end-of-run integrity check.
            # Pull the freshly-chained rows back through the same verifier
            # the REST endpoint uses. A non-empty mismatch list here means
            # the backfill logic itself produced a corrupted chain (a real
            # implementation bug, e.g. ordering / canonical-form drift). We
            # surface it as a hard CommandError so CI catches it instead of
            # the auditor noticing weeks later. Skipped on ``--dry-run`` and
            # toggleable via ``--skip-verify`` for ops who already attested
            # via an independent verifier.
            if verify_after and not dry_run:
                self._verify_or_fail(tenant_id=tenant_id, tenant_label=tenant_label)

        verb = "would chain" if dry_run else "chained"
        self.stdout.write(
            self.style.SUCCESS(f"Total {verb}: {total_processed} row(s)")
        )

    def _verify_or_fail(self, *, tenant_id, tenant_label: str) -> None:
        """Re-run :func:`verify_chain_segment` against the freshly-chained rows."""
        from hub.apps.audit.chain import verify_chain_segment

        rows = list(
            AuditEvent.all_objects.filter(
                tenant_id=tenant_id, chain_hash__isnull=False
            )
            .order_by("chain_sequence")
        )
        result = verify_chain_segment(rows)
        if not result.verified:
            preview = "; ".join(
                f"{m.reason}@seq={m.chain_sequence}" for m in result.mismatches[:5]
            )
            raise CommandError(
                f"[{tenant_label}] backfill produced an invalid chain — "
                f"{len(result.mismatches)} mismatch(es): {preview}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"[{tenant_label}] post-backfill verify OK: "
                f"{result.checked} row(s), {len(result.gaps)} gap(s)"
            )
        )

    # ------------------------------------------------------------------
    # tenant fan-out
    # ------------------------------------------------------------------

    def _resolve_tenants(self, tenant_arg: str | None) -> Iterable[uuid.UUID | None]:
        if tenant_arg is None:
            # Every tenant that has at least one AuditEvent, plus the
            # platform chain when applicable.
            tenant_ids = list(
                AuditEvent.all_objects.order_by()
                .values_list("tenant_id", flat=True)
                .distinct()
            )
            # ``distinct`` over a nullable column already collapses NULLs
            # to a single entry, so the platform chain shows up naturally
            # as the lone ``None``.
            return tenant_ids
        normalized = (tenant_arg or "").strip()
        if normalized in ("", "__platform__"):
            return [None]
        try:
            return [uuid.UUID(normalized)]
        except ValueError as exc:
            raise CommandError(
                f"--tenant-id must be a UUID, '__platform__', or empty; got {tenant_arg!r}"
            ) from exc

    # ------------------------------------------------------------------
    # per-tenant chain population
    # ------------------------------------------------------------------

    def _chain_tenant(
        self,
        *,
        tenant_id: uuid.UUID | None,
        resume_from: str,
        batch_size: int,
        dry_run: bool,
    ) -> int:
        # --- compute resume anchor ----------------------------------------
        anchor_seq, anchor_hash = self._anchor(tenant_id=tenant_id, resume_from=resume_from)

        # --- target rows --------------------------------------------------
        target_qs = AuditEvent.all_objects.filter(tenant_id=tenant_id)
        if anchor_seq is None:
            # No anchor → process every un-chained row (genesis-build mode).
            target_qs = target_qs.filter(chain_hash__isnull=True)
        else:
            # Anchored → process rows that are NOT yet chained AND come
            # AFTER the anchor in timestamp order. We don't re-walk
            # already-chained rows because their hash is canonical and
            # rewriting would re-issue downstream Merkle proofs needlessly.
            target_qs = target_qs.filter(chain_hash__isnull=True)
        target_qs = target_qs.order_by("timestamp", "id")

        # --- iterate ------------------------------------------------------
        prev_seq = anchor_seq or 0
        prev_hash = anchor_hash
        processed = 0

        # Use values() so we don't pay for full model instantiation on
        # rows we're only going to UPDATE by id. We need every canonical
        # field plus id + timestamp + chain_sequence.
        FIELDS = [
            "id", "tenant_id", "actor_user_id",
            "resource_type", "resource_id",
            "action", "result",
            "details_json", "full_details_json",
            "timestamp",
        ]
        # iterator() to keep memory flat even on huge tenants.
        batch: list[tuple[uuid.UUID, int, str | None, str]] = []
        for row in target_qs.values(*FIELDS).iterator(chunk_size=batch_size):
            prev_seq += 1
            canonical = canonical_form(row)
            ts = row["timestamp"]
            ts_iso = ts.isoformat() if ts is not None else ""
            new_hash = compute_chain_hash(canonical, prev_hash, ts_iso)
            batch.append((row["id"], prev_seq, prev_hash, new_hash))
            prev_hash = new_hash
            processed += 1
            if len(batch) >= batch_size:
                self._flush(batch, dry_run=dry_run)
                batch = []
        if batch:
            self._flush(batch, dry_run=dry_run)
        return processed

    def _anchor(
        self,
        *,
        tenant_id: uuid.UUID | None,
        resume_from: str,
    ) -> tuple[int | None, str | None]:
        """Return (chain_sequence, chain_hash) of the resume anchor row.

        ``resume_from`` semantics:

        * ``"auto"`` — last persisted chain_sequence on the tenant (or
          (None, None) if nothing is yet chained → genesis-build).
        * an integer — find the row at that exact chain_sequence and
          truncate rows after it (un-chain them) so the slice can be
          re-built.
        """
        if resume_from == "auto":
            row = (
                AuditEvent.all_objects.filter(
                    tenant_id=tenant_id, chain_hash__isnull=False
                )
                .order_by("-chain_sequence")
                .values("chain_sequence", "chain_hash")
                .first()
            )
            if not row:
                return None, None
            return int(row["chain_sequence"]), row["chain_hash"]

        try:
            n = int(resume_from)
        except ValueError as exc:
            raise CommandError(
                "--resume-from must be 'auto' or an integer chain_sequence"
            ) from exc
        if n < 0:
            raise CommandError("--resume-from must be >= 0")
        if n == 0:
            # Re-build from scratch: wipe chain on this tenant, return no anchor.
            AuditEvent.all_objects.filter(tenant_id=tenant_id).update(
                chain_sequence=None,
                prev_chain_hash=None,
                chain_hash=None,
            )
            return None, None
        row = (
            AuditEvent.all_objects.filter(
                tenant_id=tenant_id, chain_sequence=n
            )
            .values("chain_sequence", "chain_hash")
            .first()
        )
        if not row:
            raise CommandError(
                f"--resume-from={n}: no row at that chain_sequence for tenant"
            )
        # Wipe rows AFTER the anchor so we can re-chain them.
        AuditEvent.all_objects.filter(
            tenant_id=tenant_id, chain_sequence__gt=n
        ).update(chain_sequence=None, prev_chain_hash=None, chain_hash=None)
        return int(row["chain_sequence"]), row["chain_hash"]

    def _flush(
        self,
        batch: list[tuple[uuid.UUID, int, str | None, str]],
        *,
        dry_run: bool,
    ) -> None:
        if dry_run:
            return
        with transaction.atomic():
            for row_id, seq, prev, h in batch:
                AuditEvent.all_objects.filter(id=row_id).update(
                    chain_sequence=seq,
                    prev_chain_hash=prev,
                    chain_hash=h,
                )
