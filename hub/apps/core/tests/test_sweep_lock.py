"""
Phase 277.B.074 — sweep lock tests.
"""

import contextlib
from unittest.mock import MagicMock, patch

import pytest

from hub.apps.core.sweep_lock import (
    SweepLockHeldError,
    list_known_sweeps,
    register_sweep,
    sweep_lock,
)


class TestSweepLockRegistry:
    """Test sweep lock key registration."""

    def test_register_returns_lock_key(self):
        key = register_sweep("test-sweep", "Test sweep operation")
        assert key == "sweep:test-sweep"

    def test_registered_sweep_appears_in_list(self):
        register_sweep("unique-test-sweep", "A unique test")
        sweeps = list_known_sweeps()
        assert "sweep:unique-test-sweep" in sweeps
        assert sweeps["sweep:unique-test-sweep"] == "A unique test"

    def test_list_returns_copy(self):
        sweeps1 = list_known_sweeps()
        sweeps1["new_key"] = "modified"
        sweeps2 = list_known_sweeps()
        assert "new_key" not in sweeps2


class TestSweepLockDecorator:
    """Test the @sweep_lock decorator behaviour."""

    def test_decorator_acquires_and_releases_lock(self):
        """Normal path: lock acquired, function runs, lock released."""
        call_count = 0

        with patch("hub.apps.core.redis_pools.get_redis_cache_client") as mock_redis_factory:
            fake_redis = MagicMock()
            # SET NX returns True → acquired
            fake_redis.set.return_value = True
            # Lua eval returns 1 → released
            fake_redis.eval.return_value = 1
            mock_redis_factory.return_value = fake_redis

            @sweep_lock("test-decorator-sweep", ttl_seconds=60)
            def my_sweep(a, b=0):
                nonlocal call_count
                call_count += 1
                return a + b

            result = my_sweep(10, b=5)

        assert result == 15
        assert call_count == 1
        # Verify SET NX was called with correct key, TTL, and flags
        fake_redis.set.assert_called_once()
        set_args, set_kwargs = fake_redis.set.call_args
        assert set_args[0] == "sweep:test-decorator-sweep"
        assert set_kwargs.get("nx") is True
        assert set_kwargs.get("ex") == 60
        # Verify Lua compare-and-del was called for release
        fake_redis.eval.assert_called_once()

    def test_decorator_raises_when_lock_held(self):
        """If lock cannot be acquired, SweepLockHeldError is raised."""
        with patch("hub.apps.core.redis_pools.get_redis_cache_client") as mock_redis_factory:
            fake_redis = MagicMock()
            fake_redis.set.return_value = False  # Lock held by another
            mock_redis_factory.return_value = fake_redis

            @sweep_lock("contested-sweep")
            def contested():
                return "should not run"

            with pytest.raises(SweepLockHeldError, match="contested-sweep"):
                contested()

    def test_decorator_function_never_runs_when_lock_held(self):
        """The wrapped function must not execute when lock is unavailable."""
        ran = False

        with patch("hub.apps.core.redis_pools.get_redis_cache_client") as mock_redis_factory:
            fake_redis = MagicMock()
            fake_redis.set.return_value = False
            mock_redis_factory.return_value = fake_redis

            @sweep_lock("another-sweep")
            def should_not_run():
                nonlocal ran
                ran = True

            with contextlib.suppress(SweepLockHeldError):
                should_not_run()

        assert not ran

    def test_decorator_preserves_function_metadata(self):
        """@sweep_lock preserves __name__, __doc__, and sweep metadata."""

        @sweep_lock("metadata-sweep", ttl_seconds=42, description="Metadata test")
        def documented():
            """Docstring here."""

        assert documented.__name__ == "documented"
        assert documented.__doc__ == "Docstring here."
        assert documented._sweep_lock_key == "sweep:metadata-sweep"  # type: ignore[attr-defined]
        assert documented._sweep_lock_ttl == 42  # type: ignore[attr-defined]

    def test_lock_released_even_on_exception(self):
        """Lock is released in finally block even if function raises."""
        with patch("hub.apps.core.redis_pools.get_redis_cache_client") as mock_redis_factory:
            fake_redis = MagicMock()
            fake_redis.set.return_value = True
            fake_redis.eval.return_value = 1
            mock_redis_factory.return_value = fake_redis

            @sweep_lock("exception-sweep")
            def explode():
                raise ValueError("boom")

            with pytest.raises(ValueError, match="boom"):
                explode()

            # Release should still have been called
            assert fake_redis.eval.called

    def test_sweep_lock_error_message_is_descriptive(self):
        """Error message includes the lock key for operator diagnostics."""
        err = SweepLockHeldError("sweep:cleanup-orphan-drafts")
        assert "sweep:cleanup-orphan-drafts" in str(err)
        assert "already running" in str(err).lower()

    def test_multiple_independent_sweeps_use_different_keys(self):
        """Two sweeps with different names get different lock keys."""
        k1 = register_sweep("sweep-a", "First sweep")
        k2 = register_sweep("sweep-b", "Second sweep")
        assert k1 != k2
        assert k1 == "sweep:sweep-a"
        assert k2 == "sweep:sweep-b"
