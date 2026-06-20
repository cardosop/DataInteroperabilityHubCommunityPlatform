"""
Phase 228 X (228.X.3.1 / REQ-LIN-X-003) — GDPR tenant cascade.

Operator-driven purge of every lineage artifact for one tenant:

  * ``LineageEdge`` rows (open + closed, all SCD-2 history).
  * ``LineageEdgeArchive`` rows (warm tier).
  * S3 archive blobs whose URI is recorded on those archive rows.

Idempotent: a re-run on an already-purged tenant finds nothing and
exits 0. The S3 client is delegated to ``_s3_delete_objects`` so
tests can patch the boundary without faking the rest of the
pipeline (matches the convention of the F4 archive command).

Usage::

    python manage.py delete_lineage_edges_for_tenant --tenant=<uuid>
    python manage.py delete_lineage_edges_for_tenant --tenant=<uuid> --dry-run
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

logger = logging.getLogger(__name__)


def _s3_delete_objects(*, uris: Iterable[str]) -> int:
    """Delete S3 objects by URI. Returns the number deleted.
    Patched in tests so the cascade runs end-to-end without an
    actual round-trip. Failures raise; the caller catches +
    aggregates partial-success counts.
    """
    try:
        from urllib.parse import urlparse

        import boto3
    except Exception as exc:
        raise CommandError("boto3 is required for the S3 cascade") from exc

    client = boto3.client("s3")
    deleted = 0
    for uri in uris:
        parsed = urlparse(uri)
        if parsed.scheme != "s3":
            logger.warning("skipping non-s3 archive URI %s", uri)
            continue
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        client.delete_object(Bucket=bucket, Key=key)
        deleted += 1
    return deleted


class Command(BaseCommand):
    help = (
        "Phase 228 X (228.X.3.1): purge every lineage artifact for "
        "a single tenant — LineageEdge + LineageEdgeArchive + S3 blobs. "
        "Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *_args, **options):
        from hub.apps.contracts.models import LineageEdge, LineageEdgeArchive
        from hub.apps.tenants.models import Tenant

        tenant_id = options["tenant"]
        dry_run = options["dry_run"]

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist as exc:
            raise CommandError(f"Tenant {tenant_id!r} not found") from exc

        edges_qs = LineageEdge.objects.filter(tenant=tenant)
        archive_qs = LineageEdgeArchive.objects.filter(tenant=tenant)

        edge_count = edges_qs.count()
        archive_count = archive_qs.count()
        s3_uris = list(archive_qs.exclude(s3_uri="").values_list("s3_uri", flat=True))

        if dry_run:
            self.stdout.write(
                json.dumps(
                    {
                        "phase": "228.X.3.1",
                        "dry_run": True,
                        "tenant_id": str(tenant.id),
                        "lineage_edges": edge_count,
                        "archive_rows": archive_count,
                        "s3_blobs": len(s3_uris),
                    },
                    sort_keys=True,
                )
            )
            return

        # Atomic delete of relational rows; S3 cleanup happens AFTER
        # the transaction commits (S3 has no transactional guarantee
        # so we accept "blob orphan" risk before "row orphan" risk).
        with transaction.atomic():
            edges_qs.delete()
            archive_qs.delete()

        s3_deleted = 0
        s3_errors = 0
        if s3_uris:
            try:
                s3_deleted = _s3_delete_objects(uris=s3_uris)
            except Exception as exc:
                logger.warning(
                    "lineage_gdpr_cascade_s3_partial",
                    extra={
                        "tenant_id": str(tenant.id),
                        "error": str(exc),
                        "s3_uris": len(s3_uris),
                    },
                )
                s3_errors = 1

        self.stdout.write(
            json.dumps(
                {
                    "phase": "228.X.3.1",
                    "dry_run": False,
                    "tenant_id": str(tenant.id),
                    "lineage_edges_deleted": edge_count,
                    "archive_rows_deleted": archive_count,
                    "s3_blobs_deleted": s3_deleted,
                    "s3_errors": s3_errors,
                },
                sort_keys=True,
            )
        )
        logger.info(
            "lineage_gdpr_cascade_tenant_complete",
            extra={
                "tenant_id": str(tenant.id),
                "edges": edge_count,
                "archive": archive_count,
                "s3": s3_deleted,
            },
        )
