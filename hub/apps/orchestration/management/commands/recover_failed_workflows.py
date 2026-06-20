"""
Phase 68.1.4 — Recover failed and compensation-incomplete workflows.

Queries WorkflowInstance with:
- status FAILED or COMPENSATION_INCOMPLETE
- retry_count < max_retries
- updated_at older than 15 minutes (cooldown)

For FAILED: resets to DRAFT, increments retry_count, re-enqueues.
For COMPENSATION_INCOMPLETE: re-runs failed compensation steps only.
"""

from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Recover FAILED and COMPENSATION_INCOMPLETE workflows under max_retries."

    def add_arguments(self, parser):
        parser.add_argument("--cooldown-minutes", type=int, default=15)
        parser.add_argument("--batch-size", type=int, default=50)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        cooldown = timedelta(minutes=options["cooldown_minutes"])
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]
        cutoff = timezone.now() - cooldown

        instance_ids = list(
            WorkflowInstance.objects.filter(
                status__in=[
                    WorkflowStatus.FAILED,
                    WorkflowStatus.COMPENSATION_INCOMPLETE,
                ],
                retry_count__lt=F("max_retries"),
                updated_at__lt=cutoff,
            )
            .order_by("updated_at")
            .values_list("id", flat=True)[:batch_size]
        )

        recovered = 0
        comp_retried = 0
        skipped = 0

        for instance_id in instance_ids:
            try:
                with transaction.atomic():
                    instance = WorkflowInstance.objects.select_for_update(skip_locked=True).get(
                        id=instance_id
                    )
                    self._process_instance(instance, dry_run)

                if instance.status in (WorkflowStatus.DRAFT, WorkflowStatus.ROLLED_BACK):
                    recovered += 1
                else:
                    comp_retried += 1
            except WorkflowInstance.DoesNotExist:
                continue
            except Exception as exc:
                logger.warning(
                    "workflow_recovery_error", workflow_id=str(instance_id), error=str(exc)
                )
                skipped += 1

        self.stdout.write(
            f"Recovery: {recovered} retried, {comp_retried} compensation, {skipped} skipped"
        )

    def _process_instance(self, instance, dry_run):
        if instance.status == WorkflowStatus.FAILED:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would retry {instance.id}")
                return
            instance.status = WorkflowStatus.DRAFT
            instance.retry_count += 1
            instance.error_message = None
            instance.save(update_fields=["status", "retry_count", "error_message", "updated_at"])
            logger.info(
                "workflow_recovery_retry",
                workflow_id=str(instance.id),
                retry_count=instance.retry_count,
            )

        elif instance.status == WorkflowStatus.COMPENSATION_INCOMPLETE:
            if dry_run:
                self.stdout.write(f"[DRY RUN] Would re-compensate {instance.id}")
                return
            from hub.apps.orchestration.compensation import WorkflowCompensation

            handler = WorkflowCompensation()
            failed_step = instance.steps.filter(status="FAILED").order_by("step_index").first()
            if failed_step:
                instance.retry_count += 1
                instance.save(update_fields=["retry_count", "updated_at"])
                handler.rollback_workflow(instance, failed_step)
            else:
                instance.status = WorkflowStatus.ROLLED_BACK
                instance.save(update_fields=["status", "updated_at"])
            logger.info("workflow_compensation_retry", workflow_id=str(instance.id))
