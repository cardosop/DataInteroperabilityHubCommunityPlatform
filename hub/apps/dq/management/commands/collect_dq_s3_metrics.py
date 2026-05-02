"""
Phase 240.1.B.5 — Daily DQ S3 payload metrics collector.

Walks the configured DQ payload bucket / prefix, aggregates object
sizes per-tenant (the leading path segment after the prefix is the
tenant id by convention), and updates the
``dq_s3_payload_bytes_total{tenant_id}`` Prometheus gauge.

Wired in production via the
``helm/templates/cronjob/collect-dq-s3-metrics.yaml`` Kubernetes
CronJob that runs ``python manage.py collect_dq_s3_metrics`` daily at
02:00 UTC.

The collector is idempotent (gauge ``set()`` semantics, not Counter
``inc()``) so Kubernetes-CronJob occasional double-fire does not
double-count.

Why not RQ-scheduled inline (the proposal originally said "Celery beat")?
The repo uses RQ + K8s CronJobs for scheduled work (no rq-scheduler
dependency). Existing precedent: ``recover-stuck-jobs`` /
``backup-fuseki-tdb2`` / ``mailhog-prune`` all live as K8s CronJobs
calling Django management commands. This collector follows the same
pattern.
"""
from __future__ import annotations

import logging
from typing import Dict

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Walk the DQ payload S3 bucket and update the "
        "dq_s3_payload_bytes_total gauge per-tenant."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--bucket",
            default=None,
            help=(
                "Override DQ_S3_BUCKET. Defaults to the Django setting "
                "(falls back to AWS_STORAGE_BUCKET_NAME)."
            ),
        )
        parser.add_argument(
            "--prefix",
            default=None,
            help=(
                "Override DQ_S3_PREFIX (default 'dq/'). The path "
                "segment immediately after the prefix is treated as "
                "the tenant id."
            ),
        )

    def handle(self, *args, **opts):
        bucket = opts.get("bucket") or getattr(
            settings, "DQ_S3_BUCKET",
            getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""),
        )
        prefix = opts.get("prefix")
        if prefix is None:
            prefix = getattr(settings, "DQ_S3_PREFIX", "dq/")
        if not prefix.endswith("/"):
            prefix = prefix + "/"

        if not bucket:
            self.stdout.write(self.style.WARNING(
                "DQ_S3_BUCKET unset; nothing to collect.",
            ))
            return

        try:
            import boto3
        except ImportError:  # pragma: no cover — boto3 is a hard dep
            self.stdout.write(self.style.ERROR(
                "boto3 not installed; cannot collect DQ S3 metrics.",
            ))
            return

        s3 = boto3.client("s3")
        per_tenant: Dict[str, int] = {}
        objects_scanned = 0
        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents") or []:
                    objects_scanned += 1
                    key = obj.get("Key") or ""
                    size = int(obj.get("Size") or 0)
                    # Strip the prefix; the next segment is the tenant id.
                    tail = key[len(prefix):]
                    tenant_id = tail.split("/", 1)[0] if "/" in tail else tail
                    if not tenant_id:
                        continue
                    per_tenant[tenant_id] = per_tenant.get(tenant_id, 0) + size
        except Exception as exc:  # noqa: BLE001 — fail-soft; collector is
            # observability-only.  Exiting non-zero would page oncall;
            # the alert ``DQS3PayloadGrowthAnomaly`` can't fire if the
            # gauge isn't written, so an empty pass is the right
            # signal.
            self.stdout.write(self.style.ERROR(
                f"S3 list failed: {exc}",
            ))
            logger.warning(
                "collect_dq_s3_metrics_list_failed bucket=%s prefix=%s error=%s",
                bucket, prefix, exc,
            )
            return

        # Update the gauge — set(), not inc(), so re-runs are idempotent.
        from services.shared.metrics import dq_s3_payload_bytes_total

        for tenant_id, total in per_tenant.items():
            dq_s3_payload_bytes_total.labels(
                service="hub", tenant_id=tenant_id,
            ).set(total)

        self.stdout.write(self.style.SUCCESS(
            f"Collected DQ S3 metrics: {objects_scanned} objects, "
            f"{len(per_tenant)} tenants, "
            f"{sum(per_tenant.values())} total bytes."
        ))
