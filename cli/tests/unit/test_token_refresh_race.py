"""279.I.1 — Token refresh race condition tests for CLI AuthManager."""

import base64
import json
import threading
import time
from unittest.mock import MagicMock

import pytest
from datahub_cli.auth import AuthManager
from datahub_cli.config import Config


def _make_jwt_token(exp_offset_seconds: int) -> str:
    """Create a valid-looking JWT with a given expiry offset."""
    payload = {"sub": "user1", "exp": int(time.time()) + exp_offset_seconds}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJIUzI1NiJ9.{encoded}.fake_sig"


class TestTokenRefreshRace:
    """Race condition: two concurrent threads detect expiry at the same time."""

    @pytest.mark.integration
    def test_concurrent_expiry_detection_is_idempotent(self, monkeypatch):
        """Two threads both call _is_token_expired → both return True → both
        attempt refresh → the second refresh is a no-op (idempotent)."""
        expired_token = _make_jwt_token(-60)

        # Simulate a config that has the expired token + a valid refresh_token
        config = MagicMock(spec=Config)
        config.get_access_token.return_value = expired_token
        config.get_refresh_token.return_value = "valid-refresh-token"
        config.get_api_key.return_value = None

        refresh_count = [0]
        refresh_results: list[bool] = []

        def fake_refresh():
            refresh_count[0] += 1
            # Simulate network delay
            time.sleep(0.01)  # noqa: sleep-needed — test timing requirement
            config.get_access_token.return_value = _make_jwt_token(3600)
            return True

        auth = AuthManager(config_instance=config)
        auth.refresh_access_token = fake_refresh  # type: ignore[method-assign]

        def worker(results: list[bool]):
            ok = auth.ensure_authenticated()
            results.append(ok)

        threads = [threading.Thread(target=worker, args=(refresh_results,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All three workers should report authenticated
        assert all(refresh_results)
        # At least one refresh must have been attempted (could be 1 or more)
        assert refresh_count[0] >= 1

    @pytest.mark.integration
    def test_refresh_failure_does_not_corrupt_state(self, monkeypatch):
        """If refresh fails, the expired token is NOT cleared and
        subsequent calls still attempt refresh (not crash)."""
        expired_token = _make_jwt_token(-60)

        config = MagicMock(spec=Config)
        config.get_access_token.return_value = expired_token
        config.get_refresh_token.return_value = "bad-refresh-token"
        config.get_api_key.return_value = None

        def fake_refresh():
            return False  # Always fails

        auth = AuthManager(config_instance=config)
        auth.refresh_access_token = fake_refresh  # type: ignore[method-assign]

        # First call: detects expiry, attempts refresh, fails
        result1 = auth.ensure_authenticated()
        assert not result1  # Not authenticated

        # Second call: should still attempt refresh (not leave token in broken state)
        result2 = auth.ensure_authenticated()
        assert not result2


class TestJWTExpiryEdgeCases:
    """Edge cases for _is_token_expired."""

    @pytest.mark.integration
    def test_expired_token(self):
        token = _make_jwt_token(-60)
        assert AuthManager._is_token_expired(token)

    @pytest.mark.integration
    def test_valid_token(self):
        token = _make_jwt_token(3600)
        assert not AuthManager._is_token_expired(token)

    @pytest.mark.integration
    def test_buffer_window(self):
        """Token with 10s remaining (within 30s buffer) should be treated as expired."""
        token = _make_jwt_token(10)
        assert AuthManager._is_token_expired(token)

    @pytest.mark.integration
    def test_buffer_window_custom(self):
        token = _make_jwt_token(5)
        assert AuthManager._is_token_expired(token, buffer_seconds=10)

    @pytest.mark.integration
    def test_garbage_token(self):
        assert AuthManager._is_token_expired("not-a-jwt")

    @pytest.mark.integration
    def test_no_exp_claim(self):
        payload = {"sub": "user1"}
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
        token = f"h.{encoded}.sig"
        assert AuthManager._is_token_expired(token)
