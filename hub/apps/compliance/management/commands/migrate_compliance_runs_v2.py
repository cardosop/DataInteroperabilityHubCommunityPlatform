"""
Management command: migrate_compliance_runs_v2

Phase 19.15.2 — Idempotent backfill of v2 fields on ComplianceRun rows that
have regulation_mapping_json data (i.e. a completed v1 scan) but still have
null values in the three v2 alert/violation columns added in migration 0003:

  • cross_border_alert
  • localisation_alert
  • legal_basis_violations

Why v2 fields can be null on completed rows
-------------------------------------------
These fields were introduced after many compliance runs had already completed.
The Django model migration (0003) added the columns with null=True / blank=True
so existing rows silently received NULL rather than being backfilled at
migration time.  This command performs that deferred backfill.

Derivation strategy
-------------------
The original v2 service response objects are not stored verbatim; the three
alert fields were only captured starting with the code that uses the v2
compliance-service.  For old rows we reconstruct approximate but safe
values from the stored regulation_mapping_json:

  cross_border_alert
    Examine which regulation keys appear as dict-valued entries in
    regulation_mapping_json.  Any regulation that carries cross-border
    transfer restrictions (GDPR, GDPR_SCHREMS_II, UK_GDPR, PIPL_CN, LGPD)
    triggers applicable=True.

  localisation_alert
    Same approach for regulations that impose data-localisation requirements
    (PIPL_CN, PDPA_SG, DPDP_IN).

  legal_basis_violations
    Cannot be reconstructed from the stored v1 data; set to [] (empty list —
    no violations on record for this run).

All derived objects are stamped with "backfilled": true so API consumers and
dashboards can distinguish reconstructed data from natively-captured v2 data.

Idempotency
-----------
• The command only touches rows where at least one v2 field is still null.
• Already-populated fields are never overwritten.
• Running the command multiple times is safe.

Usage
-----
  python manage.py migrate_compliance_runs_v2
  python manage.py migrate_compliance_runs_v2 --dry-run
  python manage.py migrate_compliance_runs_v2 --batch-size 500
  python manage.py migrate_compliance_runs_v2 --dry-run --verbosity 2
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Regulation classification tables
#
# Mirrored from the compliance-service regulations package.  Inlined here so
# the management command has no runtime dependency on the FastAPI service.
# ---------------------------------------------------------------------------

#: Regulations that impose cross-border data transfer restrictions.
_CROSS_BORDER_REGS: frozenset[str] = frozenset({
    "GDPR",
    "GDPR_SCHREMS_II",
    "UK_GDPR",
    "PIPL_CN",
    "LGPD",
})

#: Regulations that impose data-localisation requirements.
_LOCALISATION_REGS: frozenset[str] = frozenset({
    "PIPL_CN",
    "PDPA_SG",
    "DPDP_IN",
})

#: Top-level keys in regulation_mapping_json that are NOT regulation names.
#: These are structural / metering / error metadata keys.
_NON_REG_KEYS: frozenset[str] = frozenset({
    "metering",
    "error",
    "error_type",
    "fail_closed",
    "cancelled",
    "schema_version",
    "regulation_summary",
    "metadata",
})

# How many rows to log a progress message after.
_PROGRESS_INTERVAL = 100


def _derive_v2_fields(regulation_mapping_json: dict) -> dict[str, Any]:
    """
    Derive the three v2 alert/violation fields from a v1 regulation_mapping_json.

    Returns a dict with keys:
      cross_border_alert, localisation_alert, legal_basis_violations
    """
    # Extract the names of regulations that actually applied.
    # A regulation entry is a dict value under a key that isn't a known
    # structural key.
    applicable_regs = sorted(
        key
        for key, value in regulation_mapping_json.items()
        if key not in _NON_REG_KEYS and isinstance(value, dict)
    )

    cross_border_applicable = sorted(
        r for r in applicable_regs if r in _CROSS_BORDER_REGS
    )
    localisation_applicable = sorted(
        r for r in applicable_regs if r in _LOCALISATION_REGS
    )

    return {
        "cross_border_alert": {
            "applicable": bool(cross_border_applicable),
            "applicable_regulations": cross_border_applicable,
            "requires_safeguards": bool(cross_border_applicable),
            "backfilled": True,
        },
        "localisation_alert": {
            "applicable": bool(localisation_applicable),
            "applicable_regulations": localisation_applicable,
            "strict_localisation": bool(localisation_applicable),
            "backfilled": True,
        },
        # Cannot reconstruct from v1 data; empty list is the safe default.
        "legal_basis_violations": [],
    }


class Command(BaseCommand):
    help = (
        "Idempotent backfill of cross_border_alert, localisation_alert, and "
        "legal_basis_violations on ComplianceRun rows that have "
        "regulation_mapping_json but null v2 fields (Phase 19.15.2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Show what would be updated without committing any changes. "
                "Prints per-row details when combined with --verbosity 2."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            metavar="N",
            help=(
                "Number of rows to bulk_update per database round-trip "
                "(default: 200).  Reduce if memory is constrained."
            ),
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        batch_size: int = options["batch_size"]
        verbosity: int = options["verbosity"]

        if batch_size < 1:
            raise CommandError("--batch-size must be a positive integer.")

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no database changes will be made.")
            )

        from hub.apps.compliance.models import ComplianceRun

        # Rows eligible for backfill: have regulation_mapping_json (completed
        # scan) and at least one v2 field is still null.
        eligible_qs = ComplianceRun.objects.filter(
            regulation_mapping_json__isnull=False,
        ).filter(
            Q(cross_border_alert__isnull=True)
            | Q(localisation_alert__isnull=True)
            | Q(legal_basis_violations__isnull=True)
        ).only(
            "id",
            "regulation_mapping_json",
            "cross_border_alert",
            "localisation_alert",
            "legal_basis_violations",
        ).order_by("created_at")

        total_eligible = eligible_qs.count()
        self.stdout.write(
            f"Found {total_eligible} ComplianceRun row(s) eligible for backfill."
        )

        if total_eligible == 0:
            self.stdout.write(self.style.SUCCESS("Nothing to do. All rows are up-to-date."))
            return

        processed = 0
        updated = 0
        skipped_invalid = 0
        pending_batch: list[ComplianceRun] = []
        changed_fields = ["cross_border_alert", "localisation_alert", "legal_basis_violations"]

        for run in eligible_qs.iterator(chunk_size=batch_size):
            processed += 1

            reg_mapping = run.regulation_mapping_json
            if not isinstance(reg_mapping, dict):
                # Unexpected shape (e.g. a list or scalar stored by an old bug).
                # Skip rather than corrupt.
                skipped_invalid += 1
                if verbosity >= 2:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  Skipping run {run.id}: regulation_mapping_json "
                            f"is not a dict (got {type(reg_mapping).__name__})"
                        )
                    )
                continue

            derived = _derive_v2_fields(reg_mapping)

            # Only set fields that are currently null — never overwrite existing
            # data (idempotency guarantee: fields set by a previous run are
            # respected).
            dirty = False
            if run.cross_border_alert is None:
                run.cross_border_alert = derived["cross_border_alert"]
                dirty = True
            if run.localisation_alert is None:
                run.localisation_alert = derived["localisation_alert"]
                dirty = True
            if run.legal_basis_violations is None:
                run.legal_basis_violations = derived["legal_basis_violations"]
                dirty = True

            if not dirty:
                # All three fields already populated — nothing to write.
                continue

            if verbosity >= 2:
                self.stdout.write(
                    f"  [{processed}/{total_eligible}] run {run.id}: "
                    f"cross_border={run.cross_border_alert.get('applicable')}, "
                    f"localisation={run.localisation_alert.get('applicable')}, "
                    f"violations={run.legal_basis_violations}"
                )

            updated += 1

            if not dry_run:
                pending_batch.append(run)

            # Flush the current batch.
            if not dry_run and len(pending_batch) >= batch_size:
                with transaction.atomic():
                    ComplianceRun.objects.bulk_update(pending_batch, changed_fields)
                pending_batch.clear()

            # Periodic progress log.
            if processed % _PROGRESS_INTERVAL == 0:
                self.stdout.write(
                    f"  Progress: {processed}/{total_eligible} processed, "
                    f"{updated} updated so far."
                )

        # Flush any remaining rows in the last (partial) batch.
        if not dry_run and pending_batch:
            with transaction.atomic():
                ComplianceRun.objects.bulk_update(pending_batch, changed_fields)
            pending_batch.clear()

        # Final summary.
        summary_parts = [
            f"Processed {processed} row(s).",
            f"Updated {updated} row(s).",
        ]
        if skipped_invalid:
            summary_parts.append(
                f"Skipped {skipped_invalid} row(s) with unexpected "
                "regulation_mapping_json shape."
            )
        if dry_run:
            summary_parts.append("(DRY RUN — no changes committed.)")

        summary = "  ".join(summary_parts)
        style = self.style.SUCCESS if not dry_run else self.style.WARNING
        self.stdout.write(style(summary))
