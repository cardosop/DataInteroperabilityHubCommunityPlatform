"""
Tests for DQ service client caching behaviour.

Mocks the HTTP layer to verify cache-miss, cache-hit, different cache keys
for different contracts, and cache-disabled bypass.
"""

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.dq.service_client import DQServiceClient
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

# Sample file content for cache key generation
_FILE_CONTENT = b"col1,col2\nval1,val2\n"
_FILE_FORMAT = "csv"
_PROFILE_KEY = "intake_basic_gx"


def _mock_dq_result():
    return {
        "overall_status": "PASS",
        "quality_score": 100.0,
        "checks": [],
        "engine_type": "GX",
        "engine_version": "0.18.0",
        "profile_key": _PROFILE_KEY,
        "metadata": {},
    }


class TestServiceClientCache(TestCase):
    """Tests for DQServiceClient caching logic."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    # ------------------------------------------------------------------
    # 1. Cache miss → service is called, result returned
    # ------------------------------------------------------------------
    @patch.object(DQServiceClient, "_request_with_retry")
    @patch.object(DQServiceClient, "__init__", lambda self: None)
    def test_cache_miss_calls_service(self, mock_request):
        """On cache miss the HTTP layer is called and the result is returned."""
        client = DQServiceClient.__new__(DQServiceClient)
        client.base_url = "http://localhost:8083"
        client.timeout = 120
        client.max_retries = 0
        client.backoff_factor = 0

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_dq_result()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        # Bypass circuit breaker
        client._circuit_breaker = MagicMock()
        client._circuit_breaker.call.side_effect = lambda fn, fallback=None: fn()
        client.client = MagicMock()
        client.client.request = mock_request

        result = client.run_dq(
            file_content=_FILE_CONTENT,
            file_format=_FILE_FORMAT,
            profile_key=_PROFILE_KEY,
            use_cache=True,
        )

        self.assertEqual(result["overall_status"], "PASS")
        # The circuit breaker call was invoked (meaning service was called)
        client._circuit_breaker.call.assert_called_once()

    # ------------------------------------------------------------------
    # 2. Cache hit → service NOT called on second invocation
    # ------------------------------------------------------------------
    @patch.object(DQServiceClient, "__init__", lambda self: None)
    def test_cache_hit_returns_cached(self):
        """Second call returns cached result without calling the service."""
        client = DQServiceClient.__new__(DQServiceClient)
        client.base_url = "http://localhost:8083"
        client.timeout = 120
        client.max_retries = 0
        client.backoff_factor = 0
        client._circuit_breaker = MagicMock()
        client._circuit_breaker.call.side_effect = lambda fn, fallback=None: fn()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_dq_result()
        mock_response.raise_for_status = MagicMock()
        client.client.request.return_value = mock_response

        # First call: populates cache
        result1 = client.run_dq(
            file_content=_FILE_CONTENT,
            file_format=_FILE_FORMAT,
            profile_key=_PROFILE_KEY,
            use_cache=True,
        )
        first_call_count = client._circuit_breaker.call.call_count

        # Second call: should hit cache
        result2 = client.run_dq(
            file_content=_FILE_CONTENT,
            file_format=_FILE_FORMAT,
            profile_key=_PROFILE_KEY,
            use_cache=True,
        )

        self.assertEqual(result1, result2)
        # Circuit breaker should NOT have been called again
        self.assertEqual(client._circuit_breaker.call.call_count, first_call_count)

    # ------------------------------------------------------------------
    # 3. Different contracts → different cache keys
    # ------------------------------------------------------------------
    @patch.object(DQServiceClient, "__init__", lambda self: None)
    def test_different_contracts_different_cache_keys(self):
        """Same file content + different contract → different cache keys → both call service."""
        client = DQServiceClient.__new__(DQServiceClient)
        client.base_url = "http://localhost:8083"
        client.timeout = 120
        client.max_retries = 0
        client.backoff_factor = 0
        client._circuit_breaker = MagicMock()
        client._circuit_breaker.call.side_effect = lambda fn, fallback=None: fn()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_dq_result()
        mock_response.raise_for_status = MagicMock()
        client.client.request.return_value = mock_response

        # Build two mock contracts; checks must be JSON-serializable (see service_client.run_dq).
        contract_a = MagicMock()
        contract_b = MagicMock()

        def _serializable_check(check_id: str, name: str):
            return SimpleNamespace(
                check_id=check_id,
                name=name,
                category=SimpleNamespace(value="DQ"),
                severity=SimpleNamespace(value="MEDIUM"),
                expectation_type="expect_column_values_to_not_be_null",
                params={},
                target_level="column",
                target_column="c1",
                target_pattern=None,
            )

        with patch(
            "hub.apps.dq.contract_integration.ContractQualityRulesExtractor"
        ) as MockExtractor:
            MockExtractor.get_contract_quality_checks.return_value = [
                _serializable_check("a", "rule_a")
            ]
            MockExtractor.get_contract_profile_key.return_value = _PROFILE_KEY

            client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
                contract=contract_a,
            )
            first_call_count = client._circuit_breaker.call.call_count

            MockExtractor.get_contract_quality_checks.return_value = [
                _serializable_check("b", "rule_b")
            ]

            client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
                contract=contract_b,
            )

        # Both calls should have hit the service (different cache keys)
        self.assertEqual(client._circuit_breaker.call.call_count, first_call_count + 1)

    # ------------------------------------------------------------------
    # 4. use_cache=False → always calls service
    # ------------------------------------------------------------------
    @patch.object(DQServiceClient, "__init__", lambda self: None)
    def test_cache_disabled_always_calls_service(self):
        """use_cache=False bypasses cache entirely."""
        client = DQServiceClient.__new__(DQServiceClient)
        client.base_url = "http://localhost:8083"
        client.timeout = 120
        client.max_retries = 0
        client.backoff_factor = 0
        client._circuit_breaker = MagicMock()
        client._circuit_breaker.call.side_effect = lambda fn, fallback=None: fn()
        client.client = MagicMock()

        mock_response = MagicMock()
        mock_response.json.return_value = _mock_dq_result()
        mock_response.raise_for_status = MagicMock()
        client.client.request.return_value = mock_response

        # Call twice with use_cache=False
        client.run_dq(
            file_content=_FILE_CONTENT,
            file_format=_FILE_FORMAT,
            profile_key=_PROFILE_KEY,
            use_cache=False,
        )
        client.run_dq(
            file_content=_FILE_CONTENT,
            file_format=_FILE_FORMAT,
            profile_key=_PROFILE_KEY,
            use_cache=False,
        )

        # Both calls should have hit the service
        self.assertEqual(client._circuit_breaker.call.call_count, 2)
