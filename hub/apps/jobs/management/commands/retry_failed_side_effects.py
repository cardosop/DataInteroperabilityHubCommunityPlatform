"""
Phase 76.3 — Retry failed side effects (outbox pattern).

Finds SideEffect rows in FAILED status with attempt_count < MAX and
updated_at older than 30 minutes, then re-executes them.

Dispatches to the correct app's executor based on the SideEffect's
run_content_type (scheduled_ingestion vs scheduled_export).

Designed to run every 30 minutes via a Kubernetes CronJob.
"""

from datetime import timedelta

import structlog
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from hub.apps.jobs.models import SideEffect, SideEffectStatus

logger = structlog.get_logger(__name__)

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_AFTER_MINUTES = 30

# Map app_label -> executor module path
_EXECUTOR_MAP = {
    "scheduled_ingestion": (
        "hub.apps.scheduled_ingestion.worker_run_lifecycle"
    ),
    "scheduled_export": (
        "hub.apps.scheduled_export.worker_run_lifecycle"
    ),
}


def _get_executor(se: SideEffect):
    """
    Resolve the correct execute_side_effect function based on
    the SideEffect's run_content_type app_label.
    """
    import importlib

    app_label = se.run_content_type.app_label
    module_path = _EXECUTOR_MAP.get(app_label)
    if module_path is None:
        raise ValueError(
            f"No side-effect executor registered for "
            f"app_label={app_label!r}"
        )
    mod = importlib.import_module(module_path)
    return mod.execute_side_effect


class Command(BaseCommand):
    help = (
        "Retry FAILED SideEffect rows (outbox pattern). "
        "Runs every 30 minutes via CronJob (Phase 76.3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-attempts",
            type=int,
            default=getattr(
                settings,
                "MAX_SIDE_EFFECT_ATTEMPTS",
                DEFAULT_MAX_ATTEMPTS,
            ),
            help=(
                "Skip rows with attempt_count >= this value "
                f"(default: {DEFAULT_MAX_ATTEMPTS})."
            ),
        )
        parser.add_argument(
            "--retry-after-minutes",
            type=int,
            default=DEFAULT_RETRY_AFTER_MINUTES,
            help=(
                "Only retry rows updated more than this many "
                "minutes ago "
                f"(default: {DEFAULT_RETRY_AFTER_MINUTES})."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="List retryable side effects without executing.",
        )

    def handle(self, *args, **options):
        max_attempts: int = options["max_attempts"]
        retry_after_minutes: int = options["retry_after_minutes"]
        dry_run: bool = options["dry_run"]

        cutoff = timezone.now() - timedelta(
            minutes=retry_after_minutes,
        )

        retryable = SideEffect.objects.filter(
            status=SideEffectStatus.FAILED,
            attempt_count__lt=max_attempts,
            updated_at__lt=cutoff,
        ).select_related("run_content_type").order_by("created_at")

        count = retryable.count()
        if count == 0:
            logger.info("retry_failed_side_effects_none_found")
            self.stdout.write(
                self.style.SUCCESS(
                    "No retryable side effects found."
                )
            )
            return

        self.stdout.write(
            f"Found {count} retryable side effect(s)."
        )

        if dry_run:
            for se in retryable:
                self.stdout.write(
                    f"  [DRY-RUN] {se.id}"
                    f"  type={se.effect_type}"
                    f"  app={se.run_content_type.app_label}"
                    f"  attempts={se.attempt_count}"
                    f"  updated={se.updated_at.isoformat()}"
                )
            return

        retried = 0
        succeeded = 0
        for se in retryable:
            executor = _get_executor(se)
            logger.info(
                "retry_failed_side_effect",
                side_effect_id=str(se.id),
                effect_type=se.effect_type,
                app_label=se.run_content_type.app_label,
                attempt_count=se.attempt_count,
            )
            executor(se)
            retried += 1
            if se.status == SideEffectStatus.COMPLETED:
                succeeded += 1

        logger.info(
            "retry_failed_side_effects_complete",
            retried=retried,
            succeeded=succeeded,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Retried {retried} side effect(s): "
                f"{succeeded} succeeded, "
                f"{retried - succeeded} still failing."
            )
        )
