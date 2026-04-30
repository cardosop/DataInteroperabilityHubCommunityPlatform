"""
Phase 26.15.2 — Management command for contract re-normalization.

Phase 227 Wave 0 (227.0.1) extended the command with:

* ``--filter=structureless`` — restrict to contracts whose normalized
  payload carries no structural fields (see :mod:`hub.apps.contracts.structureless`).
* ``--output=json`` — emit one JSONL row per matching contract on stdout.
  Combined with ``--dry-run`` the command becomes the diagnosis tool the
  Wave 0 ops runbook depends on.

Phase 227 Wave 3 (227.L6) extends it further with the **apply** path:

* ``--apply`` — re-normalize each structureless contract (uses the same
  pipeline as ``ContractService.update_contract``: parse → normalize →
  enforce structural floor → save). Successful re-normalization is what
  the ODPS-outputPorts walker (227.L1) exists to deliver — most
  staging-cataloged structureless ODPS rows self-heal once the walker
  ships, without customer action.
* ``--apply-asset-revert`` — additionally demote ACTIVE assets backed by
  contracts that REMAIN structureless after re-normalization (i.e., the
  customer-action cohort: ODCS contracts with no schema). Emits a
  per-asset ``ASSET_AUTO_REVERTED_STRUCTURELESS`` audit event the L6.4
  reverse migration can use to restore prior status.
* ``--silent-events`` — suppress per-contract webhooks during apply
  (useful for million-row migrations that would otherwise storm
  webhook subscribers); a single batch summary event is emitted on
  completion.
* ``--checkpoint-table=<name>`` — persist per-contract progress in
  ``MigrationCheckpoint`` rows partitioned by ``migration_name=<name>``.
  Re-runs with the same ``<name>`` skip already-done contracts.

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

Apply self-healing pass with checkpointing::

    python manage.py renormalize_contracts \\
        --spec-version 3.1.0 \\
        --filter=structureless --apply \\
        --checkpoint-table=structureless-self-heal-2026-05-01 \\
        --silent-events

Then, after the self-heal run, demote any remaining structureless assets::

    python manage.py renormalize_contracts \\
        --spec-version 3.1.0 \\
        --filter=structureless --apply --apply-asset-revert \\
        --checkpoint-table=structureless-revert-2026-05-08
"""
import json
import time

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

# Truncate stored ``MigrationCheckpoint.error`` to a sane length so a
# pathological exception (e.g. a multi-MB traceback) doesn't blow up the
# checkpoint table. Ops keep the full message via the structlog handler.
_MAX_ERROR_LEN = 1000


class Command(BaseCommand):
    help = (
        "Re-normalize contracts for a given spec version. "
        "In live mode, enqueues an async RQ task. "
        "Phase 227 Wave 0: --filter=structureless --output=json emits "
        "JSONL diagnosis on stdout. "
        "Phase 227 Wave 3: --apply self-heals via re-normalization; "
        "--apply-asset-revert demotes residue ACTIVE assets; "
        "--checkpoint-table=<name> makes the run resumable."
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
            choices=["json", "count"],
            help=(
                "Output format. 'json' emits one JSON object per "
                "matching contract on stdout (JSON Lines). "
                "'count' (Phase 227 L7.6) emits a single integer to "
                "stdout — the number of structureless contracts — "
                "for the daily cron that updates the "
                "``contract_structureless_backlog`` Prometheus gauge "
                "via the pushgateway."
            ),
        )
        # Phase 227 Wave 3 (227.L6.1)
        parser.add_argument(
            "--apply",
            action="store_true",
            default=False,
            help=(
                "Phase 227 Wave 3: actually re-normalize each "
                "matching contract (vs. the default dry-run "
                "diagnosis-only path). Requires --filter=structureless."
            ),
        )
        parser.add_argument(
            "--apply-asset-revert",
            action="store_true",
            default=False,
            help=(
                "Phase 227 Wave 3: after re-normalization, demote any "
                "ACTIVE asset whose currently-active contract REMAINS "
                "structureless to DRAFT and emit an "
                "``ASSET_AUTO_REVERTED_STRUCTURELESS`` audit event. "
                "Implies --apply."
            ),
        )
        parser.add_argument(
            "--silent-events",
            action="store_true",
            default=False,
            help=(
                "Phase 227 Wave 3: suppress per-contract webhooks "
                "during --apply; emit one ``CONTRACT_BATCH_RENORMALIZED`` "
                "audit event with summary counts at the end."
            ),
        )
        parser.add_argument(
            "--checkpoint-table",
            default=None,
            help=(
                "Phase 227 Wave 3: name to partition "
                "``MigrationCheckpoint`` rows by. Re-runs with the "
                "same name skip already-done contracts (resumable). "
                "Required for --apply on prod-scale data."
            ),
        )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, *_args, **options):
        spec_version = options["spec_version"]
        tenant_id = options["tenant_id"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        sync = options["sync"]
        filter_kind = options.get("filter")
        output_format = options.get("output")
        apply_mode = options.get("apply", False)
        apply_asset_revert = options.get("apply_asset_revert", False)
        silent_events = options.get("silent_events", False)
        checkpoint_table = options.get("checkpoint_table")

        if spec_version != "3.1.0":
            self.stderr.write(
                self.style.ERROR(
                    "Only --spec-version 3.1.0 is supported"
                )
            )
            return

        # --apply-asset-revert implies --apply for safety: the revert
        # decision depends on the post-re-normalization payload shape,
        # so we must run the re-normalization step first.
        if apply_asset_revert:
            apply_mode = True

        # --apply / --apply-asset-revert / --silent-events / --checkpoint-table
        # are only meaningful in conjunction with --filter=structureless.
        # Reject the combination early to give operators a clear error
        # rather than silently no-op'ing.
        if (
            apply_mode or apply_asset_revert or silent_events or checkpoint_table
        ) and filter_kind != "structureless":
            self.stderr.write(
                self.style.ERROR(
                    "--apply / --apply-asset-revert / --silent-events / "
                    "--checkpoint-table require --filter=structureless"
                )
            )
            return

        # Phase 227 Wave 0/3: --filter=structureless. Diagnosis-only by
        # default; --apply switches to the self-heal path.
        if filter_kind == "structureless":
            if apply_mode:
                self._handle_structureless_apply(
                    tenant_id=tenant_id,
                    batch_size=batch_size,
                    output_format=output_format,
                    apply_asset_revert=apply_asset_revert,
                    silent_events=silent_events,
                    checkpoint_table=checkpoint_table,
                )
            else:
                self._handle_structureless_filter(
                    tenant_id=tenant_id,
                    output_format=output_format,
                    dry_run=dry_run,
                )
            return

        # Pre-Phase-227 path (legacy ODCS v3.1.0 backfill).
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
    # Phase 227 Wave 0 — structureless filter handler (diagnosis-only)
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
        """
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import (
            classify_structureless_contract,
            is_structureless,
        )

        # Iterate ALL contracts (optionally tenant-scoped) and apply the
        # canonical Python predicate per row. We deliberately do NOT
        # apply the coarse `structureless_filter_q()` here — its narrow
        # ORM expression (`hub_contract_json IS NULL OR models = []`)
        # would exclude payloads like `models=[{"fields": []}]` from
        # ever reaching the predicate, producing false-clean results.
        qs = Contract.objects.all().order_by("id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

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
        # Phase 227 L7.6 — ``--output=count`` short-circuits per-row
        # JSON emission and writes only the integer count at the end.
        # Used by the daily cron that updates the
        # ``contract_structureless_backlog`` Prometheus gauge via the
        # pushgateway.
        count_only = output_format == "count"

        for contract in qs.iterator(chunk_size=200):
            scanned += 1
            if not is_structureless(contract):
                continue

            if count_only:
                # No per-row work in count-only mode — just tally.
                emitted += 1
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
        elif count_only:
            # Cron-friendly: a single integer on stdout, nothing else.
            # The daily pushgateway script greps for this exact line.
            self.stdout.write(str(emitted))
            # Also update the OTel UpDownCounter directly so processes
            # with the OTel SDK loaded see the gauge advance immediately
            # (the pushgateway path is the prom-only fallback).
            try:
                from hub.apps.contracts.normalization_metrics import (
                    set_structureless_backlog,
                )
                set_structureless_backlog(
                    count=emitted,
                    tenant_id=tenant_id,
                )
            except Exception:
                pass
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Scanned {scanned} contracts, "
                    f"{emitted} structureless"
                )
            )

    # ------------------------------------------------------------------
    # Phase 227 Wave 3 (227.L6) — structureless apply handler
    # ------------------------------------------------------------------

    def _handle_structureless_apply(
        self,
        *,
        tenant_id,
        batch_size,
        output_format,
        apply_asset_revert,
        silent_events,
        checkpoint_table,
    ):
        """Re-normalize each structureless contract; optionally revert
        residue assets to DRAFT.

        Resume logic
        ------------
        If ``checkpoint_table`` is supplied, contracts already
        recorded as ``done`` for that migration name are excluded
        from the queryset before processing. Within each batch we
        ``select_for_update(skip_locked=True)`` so concurrent runners
        (e.g. RQ workers) don't fight over the same row — the second
        worker silently skips locked rows and picks the next batch.

        Per-batch atomicity
        -------------------
        Each batch runs inside ``transaction.atomic``: if any
        per-contract write fails, the entire batch's checkpoints +
        contract updates roll back together. The next iteration
        re-fetches fresh state. This trades throughput for safety —
        we never partial-commit a batch.
        """
        from hub.apps.contracts.models import Contract
        from hub.apps.contracts.structureless import is_structureless

        run_id = f"renorm-{int(time.time() * 1000)}"
        # Observability — one structured log line at start so ops can
        # correlate the run with the RQ job ID / cron timestamp.
        try:
            import structlog
            logger = structlog.get_logger(__name__)
        except ImportError:  # structlog optional
            import logging
            logger = logging.getLogger(__name__)

        logger.info(
            "renormalize_structureless_apply_start",
            run_id=run_id,
            tenant_id=tenant_id,
            batch_size=batch_size,
            apply_asset_revert=apply_asset_revert,
            silent_events=silent_events,
            checkpoint_table=checkpoint_table,
        )

        # Build the candidate list. Coarse SQL filter excludes the
        # obviously-done ones (NULL hub_contract_json or models = [])
        # is intentionally NOT applied — see Wave 0 docstring above.
        qs = Contract.objects.all().order_by("id")
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)

        # Resume — exclude already-completed checkpoints. ``done`` AND
        # ``failed`` rows both skip on resume; ops can clear ``failed``
        # rows manually if they want to retry.
        skip_ids: set = set()
        if checkpoint_table:
            from hub.apps.contracts.models import MigrationCheckpoint

            skip_ids = set(
                MigrationCheckpoint.objects.filter(
                    migration_name=checkpoint_table,
                    status__in=[
                        MigrationCheckpoint.STATUS_DONE,
                        MigrationCheckpoint.STATUS_FAILED,
                    ],
                ).values_list("contract_id", flat=True)
            )
            if skip_ids:
                qs = qs.exclude(id__in=skip_ids)
                self.stdout.write(
                    f"# resuming: skipping {len(skip_ids)} contracts "
                    f"already recorded under "
                    f"checkpoint_table={checkpoint_table}"
                )

        # Refine with the canonical Python predicate. We materialise
        # candidate ids once so each batch can re-query with
        # ``select_for_update(skip_locked=True)`` cleanly.
        candidate_ids = []
        for contract in qs.iterator(chunk_size=batch_size):
            if is_structureless(contract):
                candidate_ids.append(contract.id)

        total = len(candidate_ids)
        processed = 0
        healed = 0  # successfully self-healed via re-normalization
        residual = 0  # remained structureless after re-normalization
        failed = 0
        reverted_asset_ids: list = []

        if output_format == "json":
            self.stdout.write(
                f"# renormalize_contracts --filter=structureless --apply"
            )
            self.stdout.write(f"# run_id={run_id} total_candidates={total}")

        for offset in range(0, total, batch_size):
            batch_ids = candidate_ids[offset:offset + batch_size]
            batch_outcomes = self._process_apply_batch(
                batch_ids=batch_ids,
                checkpoint_table=checkpoint_table,
                apply_asset_revert=apply_asset_revert,
                silent_events=silent_events,
                output_format=output_format,
                run_id=run_id,
            )
            processed += batch_outcomes["processed"]
            healed += batch_outcomes["healed"]
            residual += batch_outcomes["residual"]
            failed += batch_outcomes["failed"]
            reverted_asset_ids.extend(batch_outcomes["reverted_asset_ids"])

        # Phase 227 Wave 3 (227.L6.1) — emit a single batch summary
        # audit event when --silent-events. This is the "one batch
        # summary instead of N webhook events" promise from the spec.
        if silent_events and processed > 0:
            try:
                from hub.apps.audit.utils import create_audit_event

                create_audit_event(
                    resource_type="CONTRACT",
                    action="CONTRACT_BATCH_RENORMALIZED",
                    actor_user=None,
                    tenant=None,
                    resource_id=None,
                    details={
                        "run_id": run_id,
                        "checkpoint_table": checkpoint_table,
                        "tenant_id": str(tenant_id) if tenant_id else None,
                        "total_candidates": total,
                        "processed": processed,
                        "healed": healed,
                        "residual": residual,
                        "failed": failed,
                        "reverted_asset_ids": [
                            str(aid) for aid in reverted_asset_ids
                        ],
                    },
                )
            except Exception as exc:
                logger.warning(
                    "renormalize_batch_summary_audit_failed",
                    run_id=run_id,
                    error=str(exc),
                )

        summary = {
            "run_id": run_id,
            "total_candidates": total,
            "processed": processed,
            "healed": healed,
            "residual": residual,
            "failed": failed,
            "reverted_asset_ids": [str(a) for a in reverted_asset_ids],
        }

        if output_format == "json":
            self.stdout.write(
                "# " + json.dumps(summary, sort_keys=True)
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Apply complete: total={total} processed={processed} "
                    f"healed={healed} residual={residual} failed={failed} "
                    f"reverted_assets={len(reverted_asset_ids)}"
                )
            )

        logger.info(
            "renormalize_structureless_apply_complete", **summary
        )

    def _process_apply_batch(
        self,
        *,
        batch_ids,
        checkpoint_table,
        apply_asset_revert,
        silent_events,
        output_format,
        run_id,
    ):
        """Process one batch of candidate contracts inside an atomic
        transaction, with row-level locking.

        Returns counts dict for the caller to aggregate.

        Phase 227 L7.1 — observes
        ``contracts_renormalize_batch_duration_seconds{spec_type, outcome}``
        once per batch with the wall-clock duration and a derived
        ``outcome`` label (``healed``, ``residual``, ``mixed``, or
        ``failed``).
        """
        from hub.apps.contracts.models import (
            Contract,
            MigrationCheckpoint,
        )
        from hub.apps.contracts.structureless import is_structureless

        try:
            import structlog
            logger = structlog.get_logger(__name__)
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)

        outcome = {
            "processed": 0,
            "healed": 0,
            "residual": 0,
            "failed": 0,
            "reverted_asset_ids": [],
        }

        batch_started_at = time.time()

        with transaction.atomic():
            # ``select_for_update(skip_locked=True)`` so concurrent
            # runners don't fight over the same row. SQLite ignores
            # ``of=`` and ``skip_locked`` (no-ops there); Postgres
            # honors them for true row-level locking.
            locked_rows = list(
                Contract.objects.select_for_update(
                    skip_locked=True
                )
                .filter(id__in=batch_ids)
                .order_by("id")
            )

            for contract in locked_rows:
                outcome["processed"] += 1
                contract_id = str(contract.id)

                try:
                    healed = self._renormalize_one(contract, silent_events)

                    # Re-query fresh: ``contract.refresh_from_db()`` so
                    # ``is_structureless`` checks the post-save payload.
                    contract.refresh_from_db()

                    if not is_structureless(contract):
                        outcome["healed"] += 1
                        result_status = "healed"
                    else:
                        outcome["residual"] += 1
                        result_status = "residual"

                        # Customer-action cohort: revert ACTIVE assets
                        # backed by still-structureless contracts.
                        if apply_asset_revert:
                            reverted = self._maybe_revert_asset(
                                contract, run_id=run_id
                            )
                            if reverted:
                                outcome["reverted_asset_ids"].append(
                                    contract.asset_id
                                )

                    if checkpoint_table:
                        MigrationCheckpoint.objects.update_or_create(
                            migration_name=checkpoint_table,
                            contract=contract,
                            defaults={
                                "status": MigrationCheckpoint.STATUS_DONE,
                                "error": None,
                                "completed_at": timezone.now(),
                            },
                        )

                    if output_format == "json":
                        self.stdout.write(
                            json.dumps(
                                {
                                    "contract_id": contract_id,
                                    "result": result_status,
                                    "asset_id": (
                                        str(contract.asset_id)
                                        if contract.asset_id
                                        else None
                                    ),
                                    "run_id": run_id,
                                },
                                sort_keys=True,
                            )
                        )
                    _ = healed  # logged at logger level above

                except Exception as exc:  # noqa: BLE001 — per-contract isolation
                    outcome["failed"] += 1
                    logger.warning(
                        "renormalize_contract_failed",
                        run_id=run_id,
                        contract_id=contract_id,
                        error=str(exc),
                    )

                    if checkpoint_table:
                        MigrationCheckpoint.objects.update_or_create(
                            migration_name=checkpoint_table,
                            contract=contract,
                            defaults={
                                "status": MigrationCheckpoint.STATUS_FAILED,
                                "error": str(exc)[:_MAX_ERROR_LEN],
                                "completed_at": timezone.now(),
                            },
                        )

                    if output_format == "json":
                        self.stdout.write(
                            json.dumps(
                                {
                                    "contract_id": contract_id,
                                    "result": "failed",
                                    "error": str(exc)[:200],
                                    "run_id": run_id,
                                },
                                sort_keys=True,
                            )
                        )

        # Phase 227 L7.1 — observe batch duration with a derived
        # outcome label. ``mixed`` covers the most common Wave-3 case
        # (some healed + some residue), ``failed`` is set if ANY row
        # raised. Empty batches (skip_locked elided everything)
        # observe with outcome=``healed`` (zero duration cost is fine).
        try:
            from hub.apps.contracts.normalization_metrics import (
                record_renormalize_batch_duration,
            )
            if outcome["failed"] > 0:
                outcome_label = "failed"
            elif outcome["healed"] > 0 and outcome["residual"] > 0:
                outcome_label = "mixed"
            elif outcome["residual"] > 0:
                outcome_label = "residual"
            else:
                outcome_label = "healed"
            record_renormalize_batch_duration(
                # ``spec_type`` is heterogeneous within a batch (a run
                # can mix ODCS + ODPS), so we report ``ALL`` here.
                # Per-spec breakdown is available via the per-row
                # logs and the L7.1 success-path histograms.
                spec_type="ALL",
                outcome=outcome_label,
                duration_seconds=time.time() - batch_started_at,
            )
        except Exception:
            # Metric backend outage MUST NOT break the migration.
            pass

        return outcome

    def _renormalize_one(self, contract, silent_events: bool) -> bool:
        """Re-normalize a single contract using the production
        normalization pipeline. Returns True iff the contract was
        successfully written; False if the engine returned an empty
        payload (caller treats as residue).

        Uses ``NormalizationService.normalize_contract`` so the
        structural-floor enforcement (227.L3) runs identically to the
        live POST/PATCH path.
        """
        from hub.apps.contracts.normalization_service import (
            NormalizationService,
        )
        from hub.apps.core.services.base import (
            ValidationError as ServiceValidationError,
        )

        normalization_service = NormalizationService(
            tenant_id=str(contract.tenant_id) if contract.tenant_id else None,
            user_id=None,
        )

        try:
            (
                hub_contract,
                detected_spec_type,
                detected_spec_version,
                norm_status,
                norm_errors,
                norm_warnings,
            ) = normalization_service.normalize_contract(
                raw_contract=contract.original_raw or "",
                format=contract.original_format,
                spec_type=contract.original_spec_type,
                tenant_id=(
                    str(contract.tenant_id) if contract.tenant_id else None
                ),
                # ``contract_id=None`` deliberately — the production
                # event-publishing path requires the contract to be a
                # known row; in --silent-events mode we want no
                # per-contract events at all. If silent_events is
                # False, we still pass None here because we run a
                # batch-level CONTRACT_BATCH_RENORMALIZED audit event
                # at the end of the run, which is the right granularity
                # for a million-row migration.
                contract_id=None if silent_events else str(contract.id),
                # Phase 227 L7.1 — tag floor-violation telemetry with
                # source=migration so the dashboard can split self-heal
                # rejections from live POST/PATCH rejections.
                source="migration",
            )
        except ServiceValidationError:
            # Floor violation — the contract failed to self-heal.
            # Leave hub_contract_json untouched; caller's
            # ``is_structureless`` check picks up the residue.
            return False

        if not hub_contract:
            return False

        contract.hub_contract_json = hub_contract
        contract.normalization_status = (
            norm_status
            if hasattr(norm_status, "value") is False
            else norm_status.value
        )
        contract.normalization_errors = norm_errors or []
        contract.normalization_warnings = norm_warnings or []
        contract.save(
            update_fields=[
                "hub_contract_json",
                "normalization_status",
                "normalization_errors",
                "normalization_warnings",
                # ``updated_at`` is ``auto_now=True`` on Contract — but
                # Django only writes ``auto_now`` fields when they're
                # in ``update_fields`` explicitly OR when ``update_fields``
                # is None. Without this, the L4.3 ETag (derived from
                # ``updated_at + version + id``) would not advance
                # after a self-heal, leaving clients with stale
                # If-Match validators after migration. Including it
                # also makes downstream observers (cache invalidation,
                # the L6.6 resume regression-guard) able to tell the
                # difference between processed-this-run and
                # already-done.
                "updated_at",
            ]
        )
        return True

    def _maybe_revert_asset(self, contract, *, run_id: str) -> bool:
        """If the asset backing ``contract`` is ACTIVE and the contract
        remains structureless, demote the asset to DRAFT and emit an
        ``ASSET_AUTO_REVERTED_STRUCTURELESS`` audit event.

        Returns True iff a revert was applied. Already-DRAFT assets,
        contract-less assets, and assets where the contract status is
        not ACTIVE are no-ops (return False).

        The audit event details payload is the contract carrying the
        forward operation — the L6.4 reverse migration reads these
        events to restore prior status.
        """
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.audit.utils import create_audit_event

        asset = getattr(contract, "asset", None)
        if asset is None:
            return False
        if asset.status != AssetStatus.ACTIVE:
            return False
        # Only revert if THIS contract is the asset's currently-active
        # contract. If the asset has multiple ACTIVE contracts and a
        # different one satisfies the floor, we don't touch the asset.
        if contract.status != "ACTIVE":
            return False
        active_contracts = list(
            asset.contracts.filter(status="ACTIVE")
        )
        from hub.apps.contracts.structureless import is_structureless
        if any(not is_structureless(c) for c in active_contracts):
            return False

        previous_status = asset.status
        asset.status = AssetStatus.DRAFT
        asset.save(update_fields=["status", "updated_at"])

        try:
            create_audit_event(
                resource_type="ASSET",
                action="ASSET_AUTO_REVERTED_STRUCTURELESS",
                actor_user=None,
                tenant=getattr(asset, "tenant", None),
                resource_id=str(asset.id),
                details={
                    "previous_status": str(previous_status),
                    "new_status": str(AssetStatus.DRAFT),
                    "contract_id": str(contract.id),
                    "run_id": run_id,
                    "reason": (
                        "currently-active contract remains structureless "
                        "after Phase 227 self-heal pass"
                    ),
                },
            )
        except Exception:
            # Audit event failure must NOT roll back the demotion —
            # the asset state change is the load-bearing operation.
            pass
        return True
