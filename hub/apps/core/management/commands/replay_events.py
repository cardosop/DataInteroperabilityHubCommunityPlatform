"""
Management command for replaying events from the event store.

This command allows administrators to replay events that were previously published,
enabling recovery from failures or reprocessing of events.

Usage:
    python manage.py replay_events [--event-type TYPE] [--tenant-id ID] [--start-time TIME] [--end-time TIME] [--limit N] [--dry-run] [--batch-size N]
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import structlog

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.models import Event

logger = structlog.get_logger(__name__)


class Command(BaseCommand):
    help = 'Replay events from the event store'

    def add_arguments(self, parser):
        parser.add_argument(
            '--event-type',
            type=str,
            default=None,
            help='Filter by event type (e.g., "odps.created")'
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            default=None,
            help='Filter by tenant ID'
        )
        parser.add_argument(
            '--start-time',
            type=str,
            default=None,
            help='Start time for replay (ISO 8601 format, e.g., "2025-01-01T00:00:00Z")'
        )
        parser.add_argument(
            '--end-time',
            type=str,
            default=None,
            help='End time for replay (ISO 8601 format, e.g., "2025-01-02T00:00:00Z")'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=1000,
            help='Maximum number of events to replay (default: 1000, max: 10000)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be replayed without actually replaying events'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of events to process per batch (default: 100)'
        )
        parser.add_argument(
            '--skip-duplicates',
            action='store_true',
            default=True,
            help='Skip events that have already been replayed (idempotency, default: True)'
        )

    def handle(self, *args, **options):
        event_type = options.get('event_type')
        tenant_id = options.get('tenant_id')
        start_time_str = options.get('start_time')
        end_time_str = options.get('end_time')
        limit = options.get('limit', 1000)
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size', 100)
        skip_duplicates = options.get('skip_duplicates', True)

        # Validate limit
        if limit > 10000:
            raise CommandError(f"Limit cannot exceed 10000. Got: {limit}")

        # Parse time strings
        start_time = None
        end_time = None

        if start_time_str:
            try:
                start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            except ValueError:
                raise CommandError(f"Invalid start-time format: {start_time_str}. Use ISO 8601 format.")

        if end_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            except ValueError:
                raise CommandError(f"Invalid end-time format: {end_time_str}. Use ISO 8601 format.")

        # Validate tenant_id format if provided
        if tenant_id:
            try:
                uuid.UUID(tenant_id)
            except ValueError:
                raise CommandError(f"Invalid tenant-id format: {tenant_id}. Must be a valid UUID.")

        # Build query
        queryset = Event.objects.all()

        # Note: We don't filter out replay results at query level to avoid JSONField query issues
        # Instead, we rely on idempotency checks and marking newly created events

        if event_type:
            queryset = queryset.filter(event_type=event_type)

        if tenant_id:
            queryset = queryset.filter(tenant_id=tenant_id)

        if start_time:
            queryset = queryset.filter(timestamp__gte=start_time)

        if end_time:
            queryset = queryset.filter(timestamp__lte=end_time)

        # Order by timestamp (oldest first for replay)
        queryset = queryset.order_by('timestamp')

        # Get all events first, then filter out replay results
        all_events = list(queryset[:limit])

        # Filter out replay results before processing (don't count them as skipped)
        # This prevents infinite replay loops
        events_to_process = []
        for event_obj in all_events:
            event_tags = event_obj.metadata.get("tags", []) if event_obj.metadata else []
            if "replay_result" not in event_tags:
                events_to_process.append(event_obj)

        total_events_found = len(events_to_process)

        if total_events_found == 0:
            self.stdout.write(
                self.style.WARNING('No events found matching the specified filters.')
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f'Found {total_events_found} event(s) matching filters'
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE: No events will be replayed')
            )
            # Show first few events
            sample_events = events_to_process[:10]
            for event in sample_events:
                self.stdout.write(
                    f'  - {event.event_type} ({event.event_id}) at {event.timestamp}'
                )
            if total_events_found > 10:
                self.stdout.write(f'  ... and {total_events_found - 10} more')
            return

        # Get event bus instance
        event_bus = get_event_bus()

        # Process events in batches
        events_replayed = 0
        events_skipped = 0
        events_failed = 0
        offset = 0

        while offset < limit and offset < total_events_found:
            # Get batch
            batch = events_to_process[offset:offset + batch_size]

            if not batch:
                break

            self.stdout.write(
                f'Processing batch: {offset + 1}-{min(offset + batch_size, total_events_found)} of {total_events_found}'
            )

            for event_obj in batch:
                event_id = str(event_obj.event_id)

                # Check for duplicate (idempotency)
                if skip_duplicates:
                    if self._check_event_duplicate(event_id):
                        events_skipped += 1
                        self.stdout.write(
                            self.style.WARNING(f'  Skipped duplicate: {event_id}')
                        )
                        continue

                # Reconstruct event payload
                event_payload = {
                    "event_id": event_id,
                    "event_type": event_obj.event_type,
                    "event_version": event_obj.event_version,
                    "timestamp": event_obj.timestamp.isoformat() + "Z",
                    "source": {
                        "service": event_obj.source_service,
                        "tenant_id": str(event_obj.tenant_id) if event_obj.tenant_id else None,
                    },
                    "data": event_obj.data,
                    "metadata": event_obj.metadata or {}
                }

                if event_obj.user_id:
                    event_payload["source"]["user_id"] = str(event_obj.user_id)

                if event_obj.request_id:
                    event_payload["source"]["request_id"] = event_obj.request_id

                # Republish event
                try:
                    with transaction.atomic():
                        # Add tag to mark this as a replay result
                        replay_tags = list(event_payload.get("metadata", {}).get("tags", []))
                        if "replay_result" not in replay_tags:
                            replay_tags.append("replay_result")

                        new_event_id = event_bus.publish(
                            event_type=event_obj.event_type,
                            data=event_obj.data,
                            tenant_id=str(event_obj.tenant_id) if event_obj.tenant_id else None,
                            user_id=str(event_obj.user_id) if event_obj.user_id else None,
                            request_id=event_obj.request_id,
                            event_version=event_obj.event_version,
                            correlation_id=event_payload.get("metadata", {}).get("correlation_id"),
                            causation_id=event_payload.get("metadata", {}).get("causation_id"),
                            tags=replay_tags
                        )

                        # Mark original event as replayed (idempotency)
                        if skip_duplicates:
                            self._mark_event_replayed(event_id)
                            # Also mark the newly created event as a replay result (prevent re-replay)
                            self._mark_event_replayed(new_event_id)

                        events_replayed += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'  Replayed: {event_id} ({event_obj.event_type})')
                        )

                        logger.info(
                            "event_replayed_command",
                            event_id=event_id,
                            event_type=event_obj.event_type,
                            tenant_id=str(event_obj.tenant_id) if event_obj.tenant_id else None
                        )
                except Exception as e:
                    events_failed += 1
                    self.stdout.write(
                        self.style.ERROR(f'  Failed to replay {event_id}: {e}')
                    )
                    logger.error(
                        "event_replay_failed_command",
                        event_id=event_id,
                        event_type=event_obj.event_type,
                        error=str(e),
                        exc_info=True
                    )
                    # Continue with next event
                    continue

            offset += batch_size

            # Progress update
            self.stdout.write(
                self.style.SUCCESS(
                    f'Progress: {min(offset, total_events_found)}/{total_events_found} events processed '
                    f'(replayed: {events_replayed}, skipped: {events_skipped}, failed: {events_failed})'
                )
            )

        # Final summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nReplay completed:\n'
                f'  Total events found: {total_events_found}\n'
                f'  Events replayed: {events_replayed}\n'
                f'  Events skipped (duplicates): {events_skipped}\n'
                f'  Events failed: {events_failed}'
            )
        )

    def _check_event_duplicate(self, event_id: str) -> bool:
        """
        Check if an event has already been replayed (idempotency check).

        Uses Redis if available, falls back to Django cache.

        Args:
            event_id: Event ID to check

        Returns:
            True if event was already replayed, False otherwise
        """
        from hub.apps.core.events.deduplication import get_redis_client

        replay_key = f"event_replay:event_id:{event_id}"

        # Try Redis first
        redis_client = get_redis_client()
        if redis_client:
            try:
                exists = redis_client.exists(replay_key)
                return exists > 0
            except Exception as e:
                logger.warning(
                    "event_replay_duplicate_check_redis_error",
                    event_id=event_id,
                    error=str(e),
                    message="Redis error, falling back to Django cache"
                )

        # Fallback to Django cache if Redis is unavailable
        try:
            cached_value = cache.get(replay_key)
            return cached_value is not None
        except Exception as e:
            logger.warning(
                "event_replay_duplicate_check_cache_error",
                event_id=event_id,
                error=str(e),
                message="Cache unavailable, cannot check for duplicate replays"
            )
            return False

    def _mark_event_replayed(self, event_id: str):
        """
        Mark an event as replayed for idempotency.

        Uses Redis if available, falls back to Django cache.

        Args:
            event_id: Event ID to mark as replayed
        """
        from hub.apps.core.events.deduplication import get_redis_client

        replay_key = f"event_replay:event_id:{event_id}"
        ttl = 24 * 60 * 60  # 24 hours

        # Try Redis first
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.setex(replay_key, ttl, "1")
                return
            except Exception as e:
                logger.warning(
                    "event_replay_mark_redis_error",
                    event_id=event_id,
                    error=str(e),
                    message="Redis error, falling back to Django cache"
                )

        # Fallback to Django cache if Redis is unavailable
        try:
            cache.set(replay_key, "1", ttl)
        except Exception as e:
            logger.warning(
                "event_replay_mark_cache_error",
                event_id=event_id,
                error=str(e),
                message="Cache unavailable, cannot mark event as replayed"
            )
