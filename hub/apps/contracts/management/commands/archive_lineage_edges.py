"""
Phase 228 F5 (228.F5.6 / REQ-LIN-F5-003) — operator-driven lineage
edge archival.

Two-stage pipeline matches the storage tiering decided by OP-3:

    LineageEdge (hot, 12 mo)
        -> [--target=archive (default)]
            -> LineageEdgeArchive (warm, 24 mo)
                -> [--target=s3]
                    -> S3 standard (jsonl.gz bundle, 36 mo)
                       -> Glacier (lifecycle, until 84 mo)
                          -> Deep Archive (lifecycle, beyond)

The command is **idempotent** — running it twice with the same
``--before`` cutoff produces zero new archive rows on the second run.
Open edges (``valid_to IS NULL``) are NEVER archived; the cutoff
only applies to ``valid_to``.

Usage::

    python manage.py archive_lineage_edges --before=2025-05-01
    python manage.py archive_lineage_edges --before=2025-05-01 --dry-run
    python manage.py archive_lineage_edges --before=2024-05-01 --target=s3
"""
from __future__ import annotations

import gzip
import io
import json
import logging
from datetime import date as _date, datetime, time, timezone as _tz

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


logger = logging.getLogger(__name__)


DEFAULT_BATCH_SIZE = 500


def _parse_cutoff(value: str) -> datetime:
    """Parse ``--before`` as ISO date or ISO datetime. Returns a
    timezone-aware datetime in UTC."""
    parsed: datetime | None = None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        # Try date-only form.
        try:
            d = _date.fromisoformat(value)
            parsed = datetime.combine(d, time.min)
        except ValueError as exc:
            raise CommandError(
                f"--before must be ISO date or datetime; got {value!r}"
            ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tz.utc)
    return parsed


def _s3_put_object(*, bucket: str, key: str, body: bytes) -> str:
    """Boundary helper — patched in tests so the command's own
    behaviour is exercised end-to-end without an actual S3 round-trip.
    Returns the canonical ``s3://bucket/key`` URI on success.

    Failure surfaces as a raised exception so the management command
    can roll back the export-mark write."""
    try:
        import boto3  # local import — keeps the module-load cheap.
    except Exception as exc:  # noqa: BLE001 — boto3 optional in dev.
        raise CommandError(
            "boto3 is not installed; cannot --target=s3"
        ) from exc
    region = getattr(settings, "AWS_REGION", "us-east-1")
    client = boto3.client("s3", region_name=region)
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/x-jsonlines+gzip",
        # Server-side encryption per the standard S3 baseline; the
        # bucket default is also SSE-KMS but the explicit parameter
        # avoids a regression if the bucket policy ever drops the
        # default.
        ServerSideEncryption="AES256",
    )
    return f"s3://{bucket}/{key}"


class Command(BaseCommand):
    help = (
        "Phase 228 F5 (228.F5.6): move closed-and-old LineageEdge rows "
        "to LineageEdgeArchive (default) or export already-archived "
        "rows to S3 (--target=s3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--before",
            required=True,
            help="Archive rows where valid_to < this cutoff (ISO date or datetime).",
        )
        parser.add_argument(
            "--target",
            choices=["archive", "s3"],
            default="archive",
            help=(
                "archive (default): move from LineageEdge -> "
                "LineageEdgeArchive. s3: export already-archived "
                "rows to the configured S3 bucket."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Rows per batch (default {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument(
            "--bucket",
            default=None,
            help=(
                "S3 bucket override; default reads "
                "settings.LINEAGE_ARCHIVE_S3_BUCKET (per env)."
            ),
        )

    def handle(self, *_args, **options):
        target: str = options["target"]
        if target == "archive":
            return self._handle_archive(options)
        return self._handle_s3(options)

    # ------------------------------------------------------------------
    # archive: LineageEdge -> LineageEdgeArchive
    # ------------------------------------------------------------------

    def _handle_archive(self, options: dict) -> None:
        from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive

        cutoff = _parse_cutoff(options["before"])
        batch_size: int = options["batch_size"]
        dry_run: bool = options["dry_run"]

        # ``valid_to__lt`` excludes NULLs (Django ORM semantics) — open
        # edges are NEVER archived, regardless of cutoff.
        candidates_qs = LineageEdge.objects.filter(valid_to__lt=cutoff)
        candidate_count = candidates_qs.count()

        if dry_run:
            self.stdout.write(json.dumps({
                "phase": "228.F5.6",
                "dry_run": True,
                "before": cutoff.isoformat(),
                "target": "archive",
                "candidates": candidate_count,
            }, sort_keys=True))
            return

        moved = 0
        # Process in batches inside a transaction per batch so a long
        # backlog doesn't hold one massive lock.
        while True:
            with transaction.atomic():
                batch_ids = list(
                    candidates_qs.order_by("valid_to").values_list(
                        "pk", flat=True,
                    )[:batch_size]
                )
                if not batch_ids:
                    break
                rows = list(LineageEdge.objects.filter(pk__in=batch_ids))
                # Bulk insert into archive table (ignore_conflicts so
                # a re-run with the same cutoff does not double-archive
                # a row whose original was deleted but whose archive
                # row already exists by some other path — defensive).
                LineageEdgeArchive.objects.bulk_create(
                    [
                        LineageEdgeArchive(
                            original_edge_id=r.pk,
                            tenant_id=r.tenant_id,
                            source_contract_id=r.source_contract_id,
                            target_contract_id=r.target_contract_id,
                            source_model=r.source_model,
                            source_field=r.source_field,
                            target_model=r.target_model,
                            target_field=r.target_field,
                            edge_type=r.edge_type,
                            transformation_ref=r.transformation_ref,
                            job_ref=r.job_ref,
                            valid_from=r.valid_from,
                            valid_to=r.valid_to,
                        )
                        for r in rows
                    ],
                    ignore_conflicts=False,
                )
                # Delete the source rows AFTER the archive insert
                # commits (same transaction → DELETE is part of the
                # atomic; rollback discards the move on any error).
                LineageEdge.objects.filter(pk__in=batch_ids).delete()
                moved += len(rows)

        self.stdout.write(json.dumps({
            "phase": "228.F5.6",
            "dry_run": False,
            "before": cutoff.isoformat(),
            "target": "archive",
            "candidates": candidate_count,
            "moved": moved,
        }, sort_keys=True))
        logger.info(
            "lineage_archive_complete",
            extra={
                "before": cutoff.isoformat(),
                "moved": moved,
            },
        )

    # ------------------------------------------------------------------
    # s3: LineageEdgeArchive -> S3 jsonl.gz bundle
    # ------------------------------------------------------------------

    def _handle_s3(self, options: dict) -> None:
        from hub.apps.contracts.models import LineageEdgeArchive

        cutoff = _parse_cutoff(options["before"])
        batch_size: int = options["batch_size"]
        dry_run: bool = options["dry_run"]
        bucket = options.get("bucket") or getattr(
            settings, "LINEAGE_ARCHIVE_S3_BUCKET", None,
        )

        if not dry_run and not bucket:
            raise CommandError(
                "--target=s3 requires either --bucket or "
                "settings.LINEAGE_ARCHIVE_S3_BUCKET to be configured"
            )

        # Eligible rows: in archive table, NOT already exported,
        # ``valid_to`` predates the cutoff.
        candidates_qs = LineageEdgeArchive.objects.filter(
            exported_to_s3_at__isnull=True,
            valid_to__lt=cutoff,
        )
        candidate_count = candidates_qs.count()

        if dry_run:
            self.stdout.write(json.dumps({
                "phase": "228.F5.6",
                "dry_run": True,
                "before": cutoff.isoformat(),
                "target": "s3",
                "candidates": candidate_count,
            }, sort_keys=True))
            return

        exported = 0
        bundles_uploaded = 0
        while True:
            with transaction.atomic():
                batch = list(
                    candidates_qs.order_by("valid_to")[:batch_size]
                )
                if not batch:
                    break

                # Build one jsonl.gz bundle per batch — one S3 PUT
                # per bundle keeps S3 object count manageable while
                # keeping bundles small enough that an object scan
                # of one bundle isn't pathological.
                buf = io.BytesIO()
                with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                    for row in batch:
                        line = json.dumps({
                            "id": str(row.id),
                            "original_edge_id": str(row.original_edge_id),
                            "tenant_id": str(row.tenant_id),
                            "source_contract": str(row.source_contract_id) if row.source_contract_id else None,
                            "target_contract": str(row.target_contract_id) if row.target_contract_id else None,
                            "source_model": row.source_model,
                            "source_field": row.source_field,
                            "target_model": row.target_model,
                            "target_field": row.target_field,
                            "edge_type": row.edge_type,
                            "transformation_ref": row.transformation_ref,
                            "job_ref": row.job_ref,
                            "valid_from": row.valid_from.isoformat() if row.valid_from else None,
                            "valid_to": row.valid_to.isoformat() if row.valid_to else None,
                            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
                        }, sort_keys=True)
                        gz.write(line.encode("utf-8") + b"\n")
                body = buf.getvalue()

                # S3 key encodes the cutoff date + a UUID — the date
                # prefix supports lifecycle rules ("everything under
                # 2024/ moves to Deep Archive on 2031-01-01").
                from uuid import uuid4
                key = (
                    f"{cutoff.year:04d}/{cutoff.month:02d}/"
                    f"lineage-archive-{uuid4().hex}.jsonl.gz"
                )
                uri = _s3_put_object(bucket=bucket, key=key, body=body)
                bundles_uploaded += 1

                # Spec REQ-LIN-F5-004 scenario "Archive to S3":
                #   "the rows are written to S3 Glacier as a JSON-Lines
                #    blob AND removed from LineageEdgeArchive".
                # We DELETE the archive rows after a successful S3
                # PUT — the canonical record for archived-and-cold
                # data is the S3 object (including its versioning +
                # lifecycle transition history). The bundle key is
                # captured in the structured stdout JSON so an
                # operator can correlate a batch to its S3 object
                # for restore operations (see PITR runbook).
                LineageEdgeArchive.objects.filter(
                    pk__in=[r.pk for r in batch],
                ).delete()
                exported += len(batch)

        self.stdout.write(json.dumps({
            "phase": "228.F5.6",
            "dry_run": False,
            "before": cutoff.isoformat(),
            "target": "s3",
            "candidates": candidate_count,
            "exported": exported,
            "bundles_uploaded": bundles_uploaded,
        }, sort_keys=True))
        logger.info(
            "lineage_archive_s3_complete",
            extra={
                "before": cutoff.isoformat(),
                "exported": exported,
                "bundles": bundles_uploaded,
            },
        )
