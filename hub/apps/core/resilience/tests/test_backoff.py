"""
Tests for ``hub.apps.core.resilience.backoff`` — exponential backoff with jitter.
"""

import random
from unittest import mock

from django.test import SimpleTestCase

from hub.apps.core.resilience.backoff import backoff_with_jitter, sleep_with_jitter


class BackoffWithJitterTests(SimpleTestCase):
    """Tests for backoff_with_jitter()."""

    def test_attempt_zero_returns_small_delay(self):
        """Attempt 0 with default base=1.0 returns delay in [0, 1.0]."""
        for _ in range(20):
            delay = backoff_with_jitter(0)
            assert 0.0 <= delay <= 1.0

    def test_delay_increases_with_attempts(self):
        """Higher attempt numbers produce larger upper bounds."""
        random.seed(42)

        # Collect max delays across many trials per attempt level
        def max_trial(attempt, trials=100):
            return max(backoff_with_jitter(attempt) for _ in range(trials))

        max_0 = max_trial(0)
        max_2 = max_trial(2)
        max_5 = max_trial(5)

        # Max delay for attempt 5 should exceed attempt 2 should exceed attempt 0
        assert max_5 >= max_2 >= max_0

    def test_respects_max_delay(self):
        """Delay never exceeds max_delay even at high attempt counts."""
        for attempt in (10, 20, 50, 100):
            for _ in range(20):
                delay = backoff_with_jitter(attempt, max_delay=5.0)
                assert delay <= 5.0

    def test_zero_max_delay_returns_zero(self):
        """With max_delay=0, all delays are 0."""
        for _ in range(10):
            assert backoff_with_jitter(5, max_delay=0.0) == 0.0

    def test_zero_base_delay_returns_zero(self):
        """With base_delay=0, all delays are 0."""
        for _ in range(10):
            assert backoff_with_jitter(5, base_delay=0.0) == 0.0

    def test_custom_base_delay_scales_upper_bound(self):
        """base_delay=5.0 at attempt 0 gives [0, 5] range."""
        for _ in range(20):
            delay = backoff_with_jitter(0, base_delay=5.0)
            assert 0.0 <= delay <= 5.0

    def test_delay_always_non_negative(self):
        """Result is always >= 0 for any input."""
        for attempt in (-1, 0, 1, 10):
            for _ in range(10):
                assert backoff_with_jitter(attempt) >= 0.0


class SleepWithJitterTests(SimpleTestCase):
    """Tests for sleep_with_jitter()."""

    @mock.patch("time.sleep")
    def test_sleep_with_jitter_calls_time_sleep(self, mock_sleep):
        """Verifies time.sleep is called with computed delay."""
        delay = sleep_with_jitter(attempt=0, base_delay=0.5, max_delay=10.0)
        mock_sleep.assert_called_once()
        assert delay == mock_sleep.call_args[0][0]

    @mock.patch("time.sleep")
    def test_sleep_returns_delay(self, mock_sleep):
        """sleep_with_jitter returns the computed delay (for logging)."""
        delay = sleep_with_jitter(attempt=2)
        assert isinstance(delay, float)
        assert delay >= 0.0
