"""
Management command for processing dead letter queue entries.

This command allows administrators to retry failed events from the dead letter queue,
enabling recovery from failures or reprocessing of events.

Usage:
    python manage.py process_dlq [--event-type TYPE] [--subscriber SUBSCRIBER] [--max-entries N] [--dry-run] [--batch-size N]
"""

import uuid
from datetime import timedelta

import structlog
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from hub.apps.core.events.dlq_processor import (
    DEFAULT_MAX_RETRIES,
    calculate_retry_delay,
    resolve_dlq_entry,
    retry_dlq_entry,
    should_retry_dlq_entry,
)
from hub.apps.core.events.models import DeadLetterQueue

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = "Process dead letter queue entries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-type",
            type=str,
            default=None,
            help='Filter by event type (e.g., "odps.created")',
        )
        parser.add_argument(
            "--subscriber", type=str, default=None, help="Filter by subscriber name"
        )
        parser.add_argument(
            "--max-entries",
            type=int,
            default=100,
            help="Maximum number of entries to process (default: 100)",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=10,
            help="Number of entries to process per batch (default: 10)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without actually processing entries",
        )
        parser.add_argument(
            "--max-retries",
            type=int,
            default=None,
            help=f"Maximum retries allowed (default: {DEFAULT_MAX_RETRIES})",
        )
        parser.add_argument(
            "--resolve",
            type=str,
            default=None,
            help="Resolve a specific DLQ entry by ID (marks as resolved without retrying)",
        )
        parser.add_argument(
            "--retry", type=str, default=None, help="Retry a specific DLQ entry by ID"
        )

    def handle(self, *args, **options):
        event_type = options.get("event_type")
        subscriber = options.get("subscriber")
        max_entries = options.get("max_entries", 100)
        batch_size = options.get("batch_size", 10)
        dry_run = options.get("dry_run", False)
        max_retries = options.get("max_retries")
        resolve_id = options.get("resolve")
        retry_id = options.get("retry")

        # Handle single entry operations
        if resolve_id:
            self._handle_resolve(resolve_id)
            return

        if retry_id:
            self._handle_retry(retry_id, max_retries)
            return

        # Build query
        queryset = DeadLetterQueue.objects.filter(resolved_at__isnull=True)

        if event_type:
            queryset = queryset.filter(event_type=event_type)

        if subscriber:
            queryset = queryset.filter(subscriber=subscriber)

        # Order by oldest first (oldest failures should be retried first)
        queryset = queryset.order_by("created_at")

        # Get total count
        total_entries_found = queryset.count()

        if total_entries_found == 0:
            self.stdout.write(
                self.style.WARNING(
                    "No unresolved DLQ entries found matching the specified filters."
                )
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Found {total_entries_found} unresolved DLQ entry(ies) matching filters"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE: No entries will be processed"))
            # Show first few entries
            sample_entries = queryset[:10]
            for entry in sample_entries:
                can_retry = should_retry_dlq_entry(entry, max_retries)
                status = "ready" if can_retry else "not ready"
                self.stdout.write(
                    f"  - {entry.event_type} -> {entry.subscriber} ({entry.id}) - {status}"
                )
            if total_entries_found > 10:
                self.stdout.write(f"  ... and {total_entries_found - 10} more")
            return

        # Process entries in batches
        entries_processed = 0
        entries_succeeded = 0
        entries_failed = 0
        entries_skipped = 0
        offset = 0

        while offset < max_entries and offset < total_entries_found:
            # Get batch
            batch = list(queryset[offset : offset + batch_size])

            if not batch:
                break

            self.stdout.write(
                f"Processing batch: {offset + 1}-{min(offset + batch_size, total_entries_found)} of {min(max_entries, total_entries_found)}"
            )

            for entry in batch:
                if not should_retry_dlq_entry(entry, max_retries=max_retries):
                    entries_skipped += 1
                    delay = calculate_retry_delay(entry.retry_count)
                    next_retry_time = (
                        entry.last_attempt_at + timedelta(seconds=delay)
                        if entry.last_attempt_at
                        else None
                    )
                    if next_retry_time and timezone.now() < next_retry_time:
                        wait_seconds = (next_retry_time - timezone.now()).total_seconds()
                        self.stdout.write(
                            self.style.WARNING(f"  Skipped: {entry.id} (wait {wait_seconds:.0f}s)")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  Skipped: {entry.id} (max retries exceeded)")
                        )
                    continue

                # Retry entry
                success, error_msg = retry_dlq_entry(
                    str(entry.id), user_id=None, max_retries=max_retries
                )

                entries_processed += 1
                if success:
                    entries_succeeded += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Retried: {entry.id} ({entry.event_type} -> {entry.subscriber})"
                        )
                    )
                else:
                    entries_failed += 1
                    self.stdout.write(self.style.ERROR(f"  Failed: {entry.id} - {error_msg}"))

            offset += batch_size

            # Progress update
            self.stdout.write(
                self.style.SUCCESS(
                    f"Progress: {min(offset, max_entries, total_entries_found)}/{min(max_entries, total_entries_found)} entries processed "
                    f"(succeeded: {entries_succeeded}, failed: {entries_failed}, skipped: {entries_skipped})"
                )
            )

        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nProcessing completed:\n"
                f"  Total entries found: {total_entries_found}\n"
                f"  Entries processed: {entries_processed}\n"
                f"  Entries succeeded: {entries_succeeded}\n"
                f"  Entries failed: {entries_failed}\n"
                f"  Entries skipped: {entries_skipped}"
            )
        )

    def _handle_resolve(self, entry_id: str):
        """Handle resolving a single DLQ entry."""
        try:
            uuid.UUID(entry_id)
        except ValueError:
            raise CommandError(f"Invalid entry ID format: {entry_id}. Must be a valid UUID.")

        self.stdout.write(f"Resolving DLQ entry: {entry_id}")

        success, error_msg = resolve_dlq_entry(entry_id)

        if success:
            self.stdout.write(self.style.SUCCESS(f"Successfully resolved DLQ entry: {entry_id}"))
        else:
            raise CommandError(f"Failed to resolve DLQ entry: {error_msg}")

    def _handle_retry(self, entry_id: str, max_retries: int | None):
        """Handle retrying a single DLQ entry."""
        try:
            uuid.UUID(entry_id)
        except ValueError:
            raise CommandError(f"Invalid entry ID format: {entry_id}. Must be a valid UUID.")

        self.stdout.write(f"Retrying DLQ entry: {entry_id}")

        success, error_msg = retry_dlq_entry(entry_id, max_retries=max_retries)

        if success:
            self.stdout.write(self.style.SUCCESS(f"Successfully retried DLQ entry: {entry_id}"))
        else:
            raise CommandError(f"Failed to retry DLQ entry: {error_msg}")
