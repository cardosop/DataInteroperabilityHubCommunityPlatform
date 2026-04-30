"""
Phase 26.15.2 — Management command for contract re-normalization.

Phase 227 Wave 0 (227.0.1) extends the command with:

* ``--filter=structureless`` — restrict to contracts whose normalized
  payload carries no structural fields (see :mod:`hub.apps.contracts.structureless`).
* ``--output=json`` — emit one JSONL row per matching contract on stdout.
  Combined with ``--dry-run`` the command becomes the diagnosis tool the
  Wave 0 ops runbook depends on.

Existing flags (`--spec-version`, `--tenant-id`, `--batch-size`,
`--dry-run`, `--sync`) keep their pre-Phase-227 semantics. The new flags
are additive — without them, behaviour is identical to before.

Examples
--------
Diagnose structureless contracts on a staging-clone DB::

    python manage.py renormalize_contracts \\
        --spec-version 3.1.0 \\
        --filter=structureless --dry-run --output=json \\
        > audit-reports/structureless-pre-rollout-2026-04-30.jsonl

Scope to a single tenant during triage::

    python manage.py renormalize_contracts \\
        --spec-version 3.1.0 \\
        --filter=structureless --dry-run --output=json \\
        --tenant-id <UUID>
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Re-normalize contracts for a given spec version. "
        "In live mode, enqueues an async RQ task. "
        "Phase 227 Wave 0: --filter=structureless --output=json emits "
        "JSONL diagnosis on stdout."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--spec-version",
            required=True,
            help="Spec version to re-normalize (e.g. 3.1.0)",
        )
        parser.add_argument(
            "--tenant-id",
            default=None,
            help="Restrict to a single tenant UUID",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Contracts per batch (default: 200)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview without writing to DB",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            default=False,
            help="Run synchronously (no RQ queue)",
        )
        # Phase 227 Wave 0
        parser.add_argument(
            "--filter",
            default=None,
            choices=["structureless"],
            help=(
                "Restrict the queryset. "
                "'structureless' selects contracts whose normalized "
                "HubContract has no models[].fields[] AND no "
                "schema.fields[] (see Phase 227 Wave 0 runbook)."
            ),
        )
        parser.add_argument(
            "--output",
            default=None,
            choices=["json"],
            help=(
                "Output format. 'json' emits one JSON object per "
                "matching contract on stdout (JSON Lines). "
                "Currently only meaningful with --filter=structureless "
                "and --dry-run."
            ),
        )

    def handle(self, *_args, **options):
        spec_version = options["spec_version"]
        tenant_id = options["tenant_id"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        sync = options["sync"]
        filter_kind = options.get("filter")
        output_format = options.get("output")

        if spec_version != "3.1.0":
            self.stderr.write(
                self.style.ERROR(
                    "Only --spec-version 3.1.0 is supported"
                )
            )
            return

        # Phase 227 Wave 0 path: --filter=structureless emits a JSONL
        # diagnosis report. This is short-circuited *before* the batch
        # re-normalization path because Wave 0 only diagnoses; the
        # actual self-heal happens in Wave 3 (after the ports helper +
        # ODCS recursive walker land).
        if filter_kind == "structureless":
            self._handle_structureless_filter(
                tenant_id=tenant_id,
                output_format=output_format,
                dry_run=dry_run,
            )
            return

        from hub.apps.contracts.tasks import (
            renormalize_contracts_v310,
        )

        if dry_run or sync:
            self.stdout.write(
                f"Running {'dry-run' if dry_run else 'sync'}"
                f" re-normalization for v{spec_version}"
                f" (batch_size={batch_size})"
            )
            result = renormalize_contracts_v310(
                tenant_id=tenant_id,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Complete: {result.get('processed', 0)}"
                    f" processed,"
                    f" {result.get('failed', 0)} failed"
                )
            )
            if dry_run and result.get("dry_run_warnings"):
                for cid, warns in result[
                    "dry_run_warnings"
                ].items():
                    self.stdout.write(
                        f"  {cid}: {len(warns)} warning(s)"
                    )
        else:
            # Enqueue as RQ task
            import django_rq

            queue = django_rq.get_queue("job_default")
            job = queue.enqueue(
                renormalize_contracts_v310,
                tenant_id=tenant_id,
                batch_size=batch_size,
                dry_run=False,
                job_timeout=3600,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enqueued renormalize_contracts_v310"
                    f" on job_default — RQ job ID: {job.id}"
                )
            )

    # ------------------------------------------------------------------
    # Phase 227 Wave 0 — structureless filter handler
    # ------------------------------------------------------------------

    def _handle_structureless_filter(
        self,
        *,
        tenant_id,
        output_format,
        dry_run,
    ):
        """Emit a diagnosis report for structureless contracts.

        Wave 0 is a diagnosis-only path. We deliberately ignore the
        ``--sync`` flag and never enqueue an RQ job — the goal is to
        produce a stable, reproducible JSONL artefact for triage and
        customer comms.

        The queryset uses :func:`structureless_filter_q` for coarse DB
        filtering, then refines per-row with :func:`is_structureless`
        because Postgres JSONField path lookups can't fully express
        "models with empty fields" or "schema.fields is null".
        """
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import (
            classify_structureless_contract,
            is_structureless,
            structureless_filter_q,
        )

        qs = Contract.objects.filter(structureless_filter_q()).order_by("id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        # Header is plain prose so operators can see the run parameters
        # at the top of the JSONL file. Filtered out by `jq -c .`.
        if output_format == "json":
            self.stdout.write(
                f"# renormalize_contracts --filter=structureless "
                f"--dry-run --output=json"
            )
            if tenant_id:
                self.stdout.write(f"# tenant_id={tenant_id}")
            self.stdout.write(f"# dry_run={dry_run}")

        emitted = 0
        scanned = 0
        for contract in qs.iterator(chunk_size=200):
            scanned += 1
            if not is_structureless(contract):
                continue

            classification = classify_structureless_contract(contract)
            payload = contract.hub_contract_json or {}
            if not isinstance(payload, dict):
                payload = {}

            models = payload.get("models") or []
            if not isinstance(models, list):
                models = []
            schema_block = payload.get("schema") or {}
            if not isinstance(schema_block, dict):
                schema_block = {}
            schema_fields = schema_block.get("fields") or []
            if not isinstance(schema_fields, list):
                schema_fields = []

            # Use getattr for FK-derived `_id` attributes — Django auto-
            # creates them at runtime but static checkers (pyright without
            # django-stubs) can't see them. getattr keeps the access
            # explicit and type-safe.
            tenant_fk_id = getattr(contract, "tenant_id", None)
            asset_fk_id = getattr(contract, "asset_id", None)

            record = {
                "contract_id": str(contract.id),
                "tenant_id": str(tenant_fk_id) if tenant_fk_id else None,
                "asset_id": str(asset_fk_id) if asset_fk_id else None,
                "spec_type": contract.original_spec_type,
                "spec_version": contract.original_spec_version,
                "original_format": contract.original_format,
                "classification": classification.value,
                "models_count": len(models),
                "schema_fields_count": len(schema_fields),
            }

            if output_format == "json":
                self.stdout.write(json.dumps(record, sort_keys=True))
            else:
                self.stdout.write(
                    f"  {record['contract_id']}: "
                    f"classification={record['classification']}, "
                    f"models_count={record['models_count']}, "
                    f"schema_fields_count={record['schema_fields_count']}"
                )
            emitted += 1

        if output_format == "json":
            self.stdout.write(
                f"# scanned={scanned} structureless={emitted}"
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scanned {scanned} contracts, "
                    f"{emitted} structureless"
                )
            )
