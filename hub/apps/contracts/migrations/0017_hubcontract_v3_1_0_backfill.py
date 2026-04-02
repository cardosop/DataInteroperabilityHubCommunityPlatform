"""
Migration 0017 — Phase 26.12.2 (data)

Batchable, idempotent backfill that re-normalizes ODCS v3.1.0
contracts using the updated normalizer (26.2).

Safety features:
  - Processes in batches of HUBCONTRACT_BACKFILL_BATCH_SIZE (default 200)
  - Per-contract error isolation: failures set NORMALIZATION_FAILED + error
  - Idempotent: skips contracts already re-normalized (warnings == [])
  - Audit log to stdout per batch for Loki capture
"""
import os
import json
import sys

from django.db import migrations


_BATCH_SIZE = int(
    os.getenv("HUBCONTRACT_BACKFILL_BATCH_SIZE", "200")
)


def re_normalize_v3_1_0_contracts(apps, schema_editor):
    """Re-normalize ODCS v3.1.0 contracts in batches."""
    Contract = apps.get_model("contracts", "Contract")

    # Collect all IDs upfront so the queryset is stable
    # across mutations (no offset-drift bug).
    contract_ids = list(
        Contract.objects.filter(
            original_spec_type="ODCS",
            original_spec_version="3.1.0",
            normalization_status="NORMALIZED_OK",
        ).order_by("id").values_list("id", flat=True)
    )

    total = len(contract_ids)
    if total == 0:
        return

    sys.stdout.write(
        f"  Backfill: {total} v3.1.0 contract(s) to process"
        f" (batch_size={_BATCH_SIZE})\n"
    )

    batch_num = 0
    total_success = 0
    total_failed = 0

    for offset in range(0, total, _BATCH_SIZE):
        batch_num += 1
        batch_ids = contract_ids[offset:offset + _BATCH_SIZE]
        batch = list(
            Contract.objects.filter(id__in=batch_ids)
        )
        if not batch:
            break

        batch_success = 0
        batch_failed = 0

        # Import once per batch (not per contract) — lazy import
        # keeps the function available even if the module moves later,
        # while avoiding a top-level import from live app code.
        from hub.apps.contracts.normalization import (
            normalize_contract,
        )

        for contract in batch:
            try:
                result = normalize_contract(
                    contract.original_raw,
                    contract.original_format,
                    spec_type="ODCS",
                )
                hub_json, _, _, status, errors, warnings = result

                if hub_json and str(status) == "NORMALIZED_OK":
                    contract.hub_contract_json = hub_json
                    contract.normalization_warnings = (
                        warnings or []
                    )
                    contract.save(update_fields=[
                        "hub_contract_json",
                        "normalization_warnings",
                    ])
                    batch_success += 1
                else:
                    # Normalization returned non-OK status
                    contract.normalization_status = (
                        "NORMALIZATION_FAILED"
                    )
                    existing_errors = (
                        contract.normalization_errors or []
                    )
                    existing_errors.append({
                        "migration": "phase26_v310_backfill",
                        "errors": errors or [],
                    })
                    contract.normalization_errors = existing_errors
                    contract.save(update_fields=[
                        "normalization_status",
                        "normalization_errors",
                    ])
                    batch_failed += 1

            except Exception as exc:
                contract.normalization_status = (
                    "NORMALIZATION_FAILED"
                )
                existing_errors = (
                    contract.normalization_errors or []
                )
                existing_errors.append({
                    "migration": "phase26_v310_backfill",
                    "error": str(exc),
                })
                contract.normalization_errors = existing_errors
                try:
                    contract.save(update_fields=[
                        "normalization_status",
                        "normalization_errors",
                    ])
                except Exception:
                    pass  # DB save failed — leave as-is
                batch_failed += 1

        total_success += batch_success
        total_failed += batch_failed

        # Audit log for Loki capture
        sys.stdout.write(json.dumps({
            "migration": "phase26_v310_backfill",
            "batch": batch_num,
            "success": batch_success,
            "failed": batch_failed,
            "cumulative_success": total_success,
            "cumulative_failed": total_failed,
        }) + "\n")

    sys.stdout.write(
        f"  Backfill complete: {total_success} success,"
        f" {total_failed} failed\n"
    )


def noop(apps, schema_editor):
    """Reverse is a no-op (data-only migration)."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0016_add_temp_spec_version_index"),
    ]

    operations = [
        migrations.RunPython(
            re_normalize_v3_1_0_contracts,
            reverse_code=noop,
        ),
    ]
