"""
Write-Behind Pattern for Event Persistence

Implements a write-behind pattern with buffering and batch writes to optimize
PostgreSQL persistence performance. Events are buffered in memory and written
in batches to reduce database load and improve throughput.

Features:
- In-memory buffering with configurable size and time-based flushing
- Batch writes using bulk_create for efficiency
- Automatic retry on failures
- Consistency validation
- Graceful shutdown with flush
"""

import threading
import time
from collections import deque
from datetime import datetime
from typing import Any

import structlog
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Event

logger = structlog.get_logger(__name__)

# Configuration defaults
DEFAULT_BUFFER_SIZE = getattr(settings, "EVENT_BUS_WRITE_BEHIND_BUFFER_SIZE", 100)
DEFAULT_FLUSH_INTERVAL_SECONDS = getattr(settings, "EVENT_BUS_WRITE_BEHIND_FLUSH_INTERVAL", 5.0)
DEFAULT_MAX_RETRIES = getattr(settings, "EVENT_BUS_WRITE_BEHIND_MAX_RETRIES", 3)
DEFAULT_RETRY_DELAY_SECONDS = getattr(settings, "EVENT_BUS_WRITE_BEHIND_RETRY_DELAY", 1.0)


class WriteBehindBuffer:
    """
    Write-behind buffer for event persistence.

    Buffers events in memory and flushes them to PostgreSQL in batches.
    Supports both size-based and time-based flushing.
    """

    def __init__(
        self,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        flush_interval_seconds: float = DEFAULT_FLUSH_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ):
        """
        Initialize write-behind buffer.

        Args:
            buffer_size: Maximum number of events to buffer before flushing
            flush_interval_seconds: Maximum time to wait before flushing
            max_retries: Maximum retry attempts for failed writes
            retry_delay_seconds: Delay between retry attempts
        """
        self.buffer_size = buffer_size
        self.flush_interval_seconds = flush_interval_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds

        self._buffer: deque = deque()  # unbounded; explicit size check below
        self._lock = threading.RLock()
        self._last_flush_time = time.time()
        self._flush_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._is_running = False

        logger.info(
            "write_behind_buffer_initialized",
            buffer_size=buffer_size,
            flush_interval_seconds=flush_interval_seconds,
            max_retries=max_retries,
        )

    def start(self):
        """Start the background flush thread."""
        if self._is_running:
            logger.warning("write_behind_buffer_already_running")
            return

        self._is_running = True
        self._shutdown_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop, name="WriteBehindFlushThread", daemon=True
        )
        self._flush_thread.start()
        logger.info("write_behind_buffer_started")

    def stop(self, flush: bool = True):
        """
        Stop the background flush thread.

        Args:
            flush: Whether to flush remaining events before stopping
        """
        if not self._is_running:
            return

        self._is_running = False
        self._shutdown_event.set()

        if self._flush_thread:
            self._flush_thread.join(timeout=10.0)

        if flush:
            self.flush()

        logger.info("write_behind_buffer_stopped", flushed=flush)

    def add_event(self, event_data: dict[str, Any]) -> bool:
        """
        Add an event to the buffer.

        Args:
            event_data: Event dictionary to buffer

        Returns:
            True if event was added, False if buffer is full
        """
        with self._lock:
            # Hard cap: drop event rather than OOM
            max_buffer = getattr(
                settings, "EVENT_BUS_WRITE_BEHIND_MAX_BUFFER", self.buffer_size * 10
            )
            if len(self._buffer) >= max_buffer:
                logger.warning(
                    "write_behind_buffer_full",
                    buffer_size=len(self._buffer),
                    max_buffer=max_buffer,
                    event_dropped=True,
                )
                return False  # Drop event rather than OOM

            if len(self._buffer) >= self.buffer_size:
                # Buffer is full, trigger immediate flush
                logger.debug(
                    "write_behind_buffer_full",
                    buffer_size=len(self._buffer),
                    max_size=self.buffer_size,
                )
                self.flush()

            self._buffer.append(event_data)
            current_size = len(self._buffer)

            # Check if we should flush based on size
            if current_size >= self.buffer_size:
                logger.debug(
                    "write_behind_buffer_size_threshold",
                    size=current_size,
                    threshold=self.buffer_size,
                )
                self.flush()

            return True

    def flush(self) -> int:
        """Flush all buffered events to PostgreSQL.

        Events are only removed from the buffer after successful persistence.
        On failure, events are re-prepended to the buffer front.
        """
        with self._lock:
            if not self._buffer:
                return 0
            events_to_flush = list(self._buffer)
            self._buffer.clear()
            self._last_flush_time = time.time()

        if not events_to_flush:
            return 0

        try:
            count = self._flush_events(events_to_flush)
            return count
        except Exception:
            # Re-prepend events to front of buffer so they are retried
            with self._lock:
                self._buffer.extendleft(reversed(events_to_flush))
            raise

    def _flush_loop(self):
        """Background thread loop for time-based flushing."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for flush interval or shutdown signal
                if self._shutdown_event.wait(timeout=self.flush_interval_seconds):
                    # Shutdown signal received
                    break

                # Check if we need to flush based on time
                current_time = time.time()
                time_since_flush = current_time - self._last_flush_time

                if time_since_flush >= self.flush_interval_seconds:
                    with self._lock:
                        if self._buffer:
                            logger.debug(
                                "write_behind_buffer_time_flush",
                                time_since_flush=time_since_flush,
                                buffer_size=len(self._buffer),
                            )
                            self.flush()

            except Exception as e:
                logger.error("write_behind_buffer_flush_loop_error", error=str(e), exc_info=True)
                # Continue loop even on error
                time.sleep(1.0)

    def _flush_events(self, events_data: list[dict[str, Any]]) -> int:
        """
        Flush events to PostgreSQL with retry logic.

        Args:
            events_data: List of event dictionaries to persist

        Returns:
            Number of events successfully persisted
        """
        if not events_data:
            return 0

        start_time = time.time()
        retry_count = 0
        persisted_count = 0

        while retry_count <= self.max_retries:
            try:
                persisted_count = self._persist_events_batch(events_data)

                duration = time.time() - start_time
                logger.info(
                    "write_behind_buffer_flushed",
                    count=persisted_count,
                    total=len(events_data),
                    retry_count=retry_count,
                    duration=duration,
                )

                return persisted_count

            except Exception as e:
                retry_count += 1
                duration = time.time() - start_time

                if retry_count <= self.max_retries:
                    logger.warning(
                        "write_behind_buffer_flush_retry",
                        error=str(e),
                        retry_count=retry_count,
                        max_retries=self.max_retries,
                        delay=self.retry_delay_seconds,
                        duration=duration,
                    )
                    time.sleep(self.retry_delay_seconds * retry_count)  # Exponential backoff
                else:
                    logger.error(
                        "write_behind_buffer_flush_failed",
                        error=str(e),
                        retry_count=retry_count,
                        event_count=len(events_data),
                        duration=duration,
                        exc_info=True,
                    )
                    # Store failed events for manual retry or DLQ
                    self._handle_failed_events(events_data, str(e))
                    raise

        return persisted_count

    def _persist_events_batch(self, events_data: list[dict[str, Any]]) -> int:
        """
        Persist a batch of events to PostgreSQL.

        Args:
            events_data: List of event dictionaries

        Returns:
            Number of events persisted

        Raises:
            Exception: If persistence fails
        """
        events_to_create = []

        for event_data in events_data:
            event_id = event_data.get("event_id")
            event_type = event_data.get("event_type", "unknown")

            try:
                timestamp_str = event_data.get("timestamp", "")
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    timestamp = timezone.now()

                event_obj = Event(
                    event_id=event_id,
                    event_type=event_type,
                    event_version=event_data.get("event_version", "1.0.0"),
                    timestamp=timestamp,
                    source_service=event_data.get("source", {}).get("service", "hub"),
                    tenant_id=event_data.get("source", {}).get("tenant_id"),
                    user_id=event_data.get("source", {}).get("user_id"),
                    request_id=event_data.get("source", {}).get("request_id"),
                    data=event_data.get("data", {}),
                    metadata=event_data.get("metadata", {}),
                )
                events_to_create.append(event_obj)

            except Exception as e:
                logger.error(
                    "write_behind_buffer_event_parse_error",
                    event_id=event_id,
                    event_type=event_type,
                    error=str(e),
                    exc_info=True,
                )
                # Continue with other events
                continue

        if not events_to_create:
            return 0

        # Bulk create events
        with transaction.atomic():
            Event.objects.bulk_create(events_to_create, ignore_conflicts=True)
            persisted_count = len(events_to_create)

        # Validate consistency
        self._validate_consistency(events_data, persisted_count)

        return persisted_count

    def _validate_consistency(self, events_data: list[dict[str, Any]], persisted_count: int):
        """
        Validate that events were persisted correctly.

        Args:
            events_data: Original event data
            persisted_count: Number of events that were persisted
        """
        if persisted_count != len(events_data):
            logger.warning(
                "write_behind_buffer_consistency_warning",
                expected=len(events_data),
                persisted=persisted_count,
                difference=len(events_data) - persisted_count,
            )

        # Sample validation: check events exist in database
        sample_size = min(20, len(events_data))
        for i in range(sample_size):
            event_data = events_data[i]
            event_id = event_data.get("event_id")
            if event_id:
                exists = Event.objects.filter(event_id=event_id).exists()
                if not exists:
                    logger.warning(
                        "write_behind_buffer_consistency_check_failed",
                        event_id=event_id,
                        event_type=event_data.get("event_type"),
                    )

    def _handle_failed_events(self, events_data: list[dict[str, Any]], error_message: str):
        """
        Handle events that failed to persist after all retries.

        Args:
            events_data: Failed event data
            error_message: Error message
        """
        # Store failed events for manual retry or DLQ
        # In a production system, you might want to:
        # 1. Store in a separate failed events table
        # 2. Send to DLQ
        # 3. Alert monitoring system

        logger.error(
            "write_behind_buffer_failed_events",
            count=len(events_data),
            error=error_message,
            event_ids=[e.get("event_id") for e in events_data[:10]],  # Log first 10 IDs
        )

    def get_buffer_size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self._buffer)

    def get_stats(self) -> dict[str, Any]:
        """Get buffer statistics."""
        with self._lock:
            return {
                "buffer_size": len(self._buffer),
                "max_buffer_size": self.buffer_size,
                "flush_interval_seconds": self.flush_interval_seconds,
                "is_running": self._is_running,
                "time_since_last_flush": time.time() - self._last_flush_time,
            }


# Global write-behind buffer instance
_write_behind_buffer: WriteBehindBuffer | None = None
_buffer_lock = threading.Lock()


def get_write_behind_buffer() -> WriteBehindBuffer:
    """Get or create the global write-behind buffer instance."""
    global _write_behind_buffer

    with _buffer_lock:
        if _write_behind_buffer is None:
            _write_behind_buffer = WriteBehindBuffer()
            _write_behind_buffer.start()

        return _write_behind_buffer


def shutdown_write_behind_buffer(flush: bool = True):
    """Shutdown the global write-behind buffer."""
    global _write_behind_buffer

    with _buffer_lock:
        if _write_behind_buffer:
            _write_behind_buffer.stop(flush=flush)
            _write_behind_buffer = None
