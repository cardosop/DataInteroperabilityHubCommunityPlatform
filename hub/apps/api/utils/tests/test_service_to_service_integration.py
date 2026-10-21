"""
Integration tests for service-to-service communication.

Tests verify that service clients can communicate with external microservices
and that endpoint construction follows best practices.
"""

from unittest.mock import Mock, patch

import httpx
from django.test import TestCase

from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.dq.service_client import DQServiceClient
from hub.apps.semantic.service_client import SemanticServiceClient


class ServiceToServiceIntegrationTest(TestCase):
    """Integration tests for service-to-service calls"""

    def setUp(self):
        """Set up test fixtures"""
        # DQ and Compliance clients use in-memory circuit breakers
        # (get_shared_circuit_breaker); Semantic uses Redis-backed
        # circuit breaker (get_redis_client from
        # core.resilience.circuit_breaker).
        with (
            patch(
                "hub.apps.core.resilience.service_breakers.get_shared_circuit_breaker",
                return_value=Mock(),
            ),
            patch("hub.apps.semantic.service_client.get_redis_client"),
        ):
            self.dq_client = DQServiceClient()
            self.compliance_client = ComplianceServiceClient()
            self.semantic_client = SemanticServiceClient()

    @patch("hub.apps.dq.service_client.sleep_with_jitter")
    @patch("hub.apps.dq.service_client.httpx.Client")
    @patch("hub.apps.dq.service_client.cache")
    def test_dq_service_integration(self, mock_cache, mock_client_class, mock_sleep):
        """Test DQ service integration"""
        mock_cache.get.return_value = None
        mock_sleep.return_value = None

        # Mock successful response — DQ client uses build_request + send.
        mock_response = Mock()
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "quality_score": 0.95,
            "checks": [],
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.send.return_value = mock_response
        mock_client_class.return_value = mock_client

        self.dq_client.client = mock_client
        self.dq_client._circuit_breaker = Mock()
        self.dq_client._circuit_breaker.call = Mock(side_effect=lambda func, fallback: func())

        # Test service call
        result = self.dq_client.run_dq(b"test data", "csv")

        # Verify request was made correctly
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_status"], "PASS")

        # Verify endpoint construction — DQ client uses build_request.
        call_args = mock_client.build_request.call_args
        self.assertEqual(call_args[0][0], "POST")  # HTTP method
        self.assertEqual(call_args[0][1], "/run")  # Endpoint
        self.assertIn("files", call_args[1])  # File upload
        self.assertIn("data", call_args[1])  # Form data

    @patch("hub.apps.compliance.service_client.httpx.Client")
    def test_compliance_service_integration(self, mock_client_class):
        """Test Compliance service integration"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "overall_status": "PASS",
            "risk_level": "LOW",
            "detected_categories": {},
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        self.compliance_client.client = mock_client
        self.compliance_client._circuit_breaker = Mock()
        self.compliance_client._circuit_breaker.call = Mock(
            side_effect=lambda func, fallback: func()
        )

        # Test service call
        result = self.compliance_client.scan_file(b"test data", "csv")

        # Verify request was made correctly
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_status"], "PASS")

        # Verify endpoint construction
        call_args = mock_client.request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/scan-file")  # Kebab-case endpoint
        self.assertIn("files", call_args[1])
        self.assertIn("data", call_args[1])

    @patch("hub.apps.semantic.service_client.httpx.Client")
    def test_semantic_service_integration(self, mock_client_class):
        """Test Semantic service integration"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {
            "contract_uri": "http://example.com/contract/123",
            "triples_count": 10,
            "semantic_status": "mapped",
        }
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        self.semantic_client.client = mock_client
        self.semantic_client._circuit_breaker = Mock()
        self.semantic_client._circuit_breaker.call = Mock(side_effect=lambda func, fallback: func())

        # Test service call
        contract_data = {"id": "123", "name": "Test Contract"}
        result = self.semantic_client.map_contract(contract_data, "contract-uuid", "asset-uuid")

        # Verify request was made correctly
        self.assertIsNotNone(result)
        self.assertIn("contract_uri", result)

        # Verify endpoint construction
        call_args = mock_client.request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/map/contract")  # Kebab-case, plural resource
        self.assertIn("json", call_args[1])

    @patch("hub.apps.semantic.service_client.httpx.Client")
    def test_semantic_service_sparql_integration(self, mock_client_class):
        """Test Semantic service SPARQL query integration"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"results": {"bindings": []}}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        self.semantic_client.client = mock_client
        self.semantic_client._circuit_breaker = Mock()
        self.semantic_client._circuit_breaker.call = Mock(side_effect=lambda func, fallback: func())

        # Test SPARQL query
        query = "SELECT * WHERE { ?s ?p ?o }"
        result = self.semantic_client.query_sparql(query)

        # Verify request was made correctly
        self.assertIsNotNone(result)
        self.assertIn("results", result)

        # Verify endpoint construction
        call_args = mock_client.request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "/query")
        self.assertIn("json", call_args[1])


class ServiceClientErrorHandlingTest(TestCase):
    """Test error handling in service clients"""

    def setUp(self):
        """Set up test fixtures"""
        # DQ client uses in-memory circuit breaker, not Redis.
        with patch(
            "hub.apps.core.resilience.service_breakers.get_shared_circuit_breaker",
            return_value=Mock(),
        ):
            self.dq_client = DQServiceClient()

    @patch("hub.apps.dq.service_client.sleep_with_jitter")
    @patch("hub.apps.dq.service_client.httpx.Client")
    @patch("hub.apps.dq.service_client.cache")
    def test_dq_service_circuit_breaker_fallback(self, mock_cache, mock_client_class, mock_sleep):
        """Test DQ service circuit breaker fallback"""
        mock_cache.get.return_value = None
        mock_sleep.return_value = None

        mock_client = Mock()
        # DQ client uses send(), not request().
        mock_client.send.side_effect = httpx.RequestError("Service unavailable")
        mock_client_class.return_value = mock_client

        self.dq_client.client = mock_client
        self.dq_client._circuit_breaker = Mock()
        # Simulate circuit breaker open
        self.dq_client._circuit_breaker.call = Mock(side_effect=lambda func, fallback: fallback())

        # Test service call with circuit breaker open
        result = self.dq_client.run_dq(b"test data", "csv")

        # Verify fallback response
        self.assertIsNotNone(result)
        self.assertEqual(result["overall_status"], "UNKNOWN")
        self.assertIn("error", result.get("metadata", {}))

    @patch("hub.apps.dq.service_client.sleep_with_jitter")
    @patch("hub.apps.dq.service_client.httpx.Client")
    @patch("hub.apps.dq.service_client.cache")
    def test_dq_service_retry_logic(self, mock_cache, mock_client_class, mock_sleep):
        """Test DQ service retry logic"""
        mock_cache.get.return_value = None
        mock_sleep.return_value = None

        # First call fails, second succeeds — DQ client uses send().
        mock_response = Mock()
        mock_response.json.return_value = {"overall_status": "PASS"}
        mock_response.raise_for_status = Mock()

        mock_client = Mock()
        mock_client.send.side_effect = [
            httpx.HTTPStatusError("500 Error", request=Mock(), response=Mock(status_code=500)),
            mock_response,
        ]
        mock_client_class.return_value = mock_client

        self.dq_client.client = mock_client
        self.dq_client._circuit_breaker = Mock()
        self.dq_client._circuit_breaker.call = Mock(side_effect=lambda func, fallback: func())

        # Test retry logic
        result = self.dq_client.run_dq(b"test data", "csv")

        # Verify retry occurred
        self.assertEqual(mock_client.send.call_count, 2)
        self.assertIsNotNone(result)
