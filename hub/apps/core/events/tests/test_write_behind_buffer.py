"""Phase 88: Write-behind buffer data integrity tests."""
from unittest.mock import patch, MagicMock
from collections import deque
from django.test import TestCase

from hub.apps.core.events.write_behind import WriteBehindBuffer


class TestWriteBehindBufferRetention(TestCase):
    """Verify buffer retains events on flush failure."""

    def test_buffer_retains_events_on_flush_failure(self):
        """When _flush_events raises, events must remain in the buffer."""
        buf = WriteBehindBuffer.__new__(WriteBehindBuffer)
        # Minimal init to avoid side effects
        import threading
        buf._buffer = deque()
        buf._lock = threading.RLock()
        buf._last_flush_time = 0
        buf.buffer_size = 100
        buf.max_retries = 1

        # Add events
        buf._buffer.append({"event": "A"})
        buf._buffer.append({"event": "B"})
        buf._buffer.append({"event": "C"})

        # Mock _flush_events to raise
        with patch.object(
            buf, '_flush_events', side_effect=Exception("DB down")
        ):
            with self.assertRaises(Exception):
                buf.flush()

        # Events must still be in the buffer
        self.assertEqual(len(buf._buffer), 3)
        events = list(buf._buffer)
        self.assertEqual(events[0]["event"], "A")
        self.assertEqual(events[1]["event"], "B")
        self.assertEqual(events[2]["event"], "C")

    def test_buffer_clears_on_successful_flush(self):
        """When _flush_events succeeds, buffer must be empty."""
        buf = WriteBehindBuffer.__new__(WriteBehindBuffer)
        import threading
        buf._buffer = deque()
        buf._lock = threading.RLock()
        buf._last_flush_time = 0
        buf.buffer_size = 100
        buf.max_retries = 1

        buf._buffer.append({"event": "A"})
        buf._buffer.append({"event": "B"})

        with patch.object(buf, '_flush_events', return_value=2):
            count = buf.flush()

        self.assertEqual(count, 2)
        self.assertEqual(len(buf._buffer), 0)

    def test_events_flushed_on_next_successful_call(self):
        """After a failed flush, events should be flushed on next success."""
        buf = WriteBehindBuffer.__new__(WriteBehindBuffer)
        import threading
        buf._buffer = deque()
        buf._lock = threading.RLock()
        buf._last_flush_time = 0
        buf.buffer_size = 100
        buf.max_retries = 1

        buf._buffer.append({"event": "A"})
        buf._buffer.append({"event": "B"})

        # First flush fails
        with patch.object(
            buf, '_flush_events', side_effect=Exception("fail")
        ):
            with self.assertRaises(Exception):
                buf.flush()

        # Buffer still has events
        self.assertEqual(len(buf._buffer), 2)

        # Second flush succeeds
        captured = []

        def capture_flush(events):
            captured.extend(events)
            return len(events)

        with patch.object(
            buf, '_flush_events', side_effect=capture_flush
        ):
            count = buf.flush()

        self.assertEqual(count, 2)
        self.assertEqual(len(buf._buffer), 0)
        self.assertEqual(captured[0]["event"], "A")
        self.assertEqual(captured[1]["event"], "B")
