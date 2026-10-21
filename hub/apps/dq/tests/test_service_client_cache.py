"""
Tests for DQ service client caching behaviour.

Uses real DQServiceClient construction (no __init__ bypass) and patches
only the HTTP boundary (client.send) to keep the constructor, circuit
breaker, and attribute initialization exercised.  This follows the
pattern established in test_service_client_circuit_breaker.py.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.dq.service_client import DQServiceClient

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

# Sample file content for cache key generation
_FILE_CONTENT = b"col1,col2\nval1,val2\n"
_FILE_FORMAT = "csv"
_PROFILE_KEY = "intake_basic_gx"


def _mock_response(json_body=None):
    """Build a mock httpx response with json() returning the given body."""
    resp = MagicMock()
    resp.json.return_value = json_body or {
        "overall_status": "PASS",
        "quality_score": 100.0,
        "checks": [],
        "engine_type": "GX",
        "engine_version": "0.18.0",
        "profile_key": _PROFILE_KEY,
        "metadata": {},
    }
    resp.raise_for_status = MagicMock()
    return resp


class TestServiceClientCache(TestCase):
    """Tests for DQServiceClient caching logic with real construction."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def tearDown(self):
        cache.clear()
        super().tearDown()

    # ------------------------------------------------------------------
    # 1. Cache miss → service is called, result returned
    # ------------------------------------------------------------------
    def test_cache_miss_calls_service(self):
        """On cache miss the HTTP layer is called and the result is returned."""
        client = DQServiceClient()
        mock_resp = _mock_response()

        with patch.object(client.client, "send", return_value=mock_resp):
            result = client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
            )

        self.assertEqual(result["overall_status"], "PASS")
        self.assertEqual(result["quality_score"], 100.0)

    # ------------------------------------------------------------------
    # 2. Cache hit → service NOT called on second invocation
    # ------------------------------------------------------------------
    def test_cache_hit_returns_cached(self):
        """Second call returns cached result without calling the service."""
        client = DQServiceClient()
        mock_resp = _mock_response()

        with patch.object(client.client, "send", return_value=mock_resp) as mock_send:
            # First call: populates cache
            result1 = client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
            )
            call_count_after_first = mock_send.call_count

            # Second call: should hit cache, no additional HTTP call
            result2 = client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
            )

            self.assertEqual(result1, result2)
            self.assertEqual(mock_send.call_count, call_count_after_first)

    # ------------------------------------------------------------------
    # 3. Different contracts → different cache keys
    # ------------------------------------------------------------------
    def test_different_contracts_different_cache_keys(self):
        """Same file content + different contract → different cache keys → both call service."""
        client = DQServiceClient()
        mock_resp = _mock_response()

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

        # Build two mock contracts
        import hub.apps.dq.contract_integration as ci_module

        with (
            patch.object(
                ci_module.ContractQualityRulesExtractor, "get_contract_quality_checks"
            ) as mock_checks,
            patch.object(
                ci_module.ContractQualityRulesExtractor, "get_contract_profile_key"
            ) as mock_profile,
            patch.object(
                client.client,
                "send",
                return_value=mock_resp,
            ) as mock_send,
        ):
            mock_profile.return_value = _PROFILE_KEY

            mock_checks.return_value = [_serializable_check("a", "rule_a")]
            client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
                contract=MagicMock(),
            )
            first_call_count = mock_send.call_count

            mock_checks.return_value = [_serializable_check("b", "rule_b")]
            client.run_dq(
                file_content=_FILE_CONTENT,
                file_format=_FILE_FORMAT,
                profile_key=_PROFILE_KEY,
                use_cache=True,
                contract=MagicMock(),
            )

        # Both calls should have hit the service (different cache keys)
        self.assertEqual(mock_send.call_count, first_call_count + 1)

    # ------------------------------------------------------------------
    # 4. use_cache=False → always calls service
    # ------------------------------------------------------------------
    def test_cache_disabled_always_calls_service(self):
        """use_cache=False bypasses cache entirely."""
        client = DQServiceClient()
        mock_resp = _mock_response()

        with patch.object(client.client, "send", return_value=mock_resp) as mock_send:
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
        self.assertEqual(mock_send.call_count, 2)
