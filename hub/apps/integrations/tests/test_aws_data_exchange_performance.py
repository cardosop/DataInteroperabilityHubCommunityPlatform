"""
Performance Tests for AWS Data Exchange Connector

Tests concurrent operations, large result sets, and connection reuse using real AWS.
No mocks or stubs; requires AWS credentials. Skips entire class when credentials
are not available (same as test_aws_data_exchange_integration.py).
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pytest
from django.test import TestCase

from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.integrations.base import SyncStatus
from hub.apps.integrations.connectors.aws_data_exchange_connector import (
    AWSDataExchangeConnector,
)


def get_aws_credentials():
    """Get AWS credentials from environment; skip if not available."""
    access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    region = os.getenv("AWS_REGION", "us-east-1")
    if not access_key_id or not secret_access_key:
        pytest.skip(
            "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY required for "
            "performance integration tests"
        )
    return {
        "aws_access_key_id": access_key_id,
        "aws_secret_access_key": secret_access_key,
        "region_name": region,
    }


def verify_connection(connector):
    """Return True if connector can connect to AWS Data Exchange."""
    try:
        return connector.test_connection()
    except Exception:
        return False


@pytest.mark.integration
class TestAWSDataExchangeConnectorPerformance(TestCase):
    """
    Performance integration tests for AWS Data Exchange connector.

    Uses real AWS; no mocks. Skips when AWS credentials are not available.
    """

    connector: Optional[AWSDataExchangeConnector] = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        try:
            credentials = get_aws_credentials()
            cls.connector = AWSDataExchangeConnector(**credentials)
            cls.connector.authenticate(credentials)
            if not verify_connection(cls.connector):
                pytest.skip(
                    "Cannot connect to AWS Data Exchange - check credentials and permissions"
                )
        except Exception as e:
            pytest.skip(f"Cannot set up AWS Data Exchange connector: {e}")

    @classmethod
    def tearDownClass(cls):
        reset_circuit_breaker_by_name("aws-data-exchange-connector")
        super().tearDownClass()

    def setUp(self):
        if not hasattr(self, "connector") or not self.connector:
            self.skipTest("AWS Data Exchange connector not available")

    def test_concurrent_list_listings(self):
        """Test concurrent list_listings operations against real AWS."""
        def list_listings():
            return self.connector.list_listings(limit=10)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(list_listings) for _ in range(5)]
            results = [future.result() for future in as_completed(futures)]

        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIsInstance(result, list)
            self.assertLessEqual(len(result), 10)

    def test_concurrent_sync_pull(self):
        """Test concurrent sync_pull operations against real AWS."""
        def sync_pull():
            return self.connector.sync_pull(options={"limit": 5})

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(sync_pull) for _ in range(3)]
            results = [future.result() for future in as_completed(futures)]

        self.assertEqual(len(results), 3)
        for result in results:
            self.assertEqual(result.status, SyncStatus.COMPLETED)

    def test_large_result_sets_pagination(self):
        """Test pagination with real AWS (actual count depends on account)."""
        listings = self.connector.list_listings(limit=100)
        self.assertIsInstance(listings, list)
        self.assertLessEqual(len(listings), 100)

    def test_large_result_sets_offset(self):
        """Test offset handling with real AWS."""
        page1 = self.connector.list_listings(limit=25, offset=0)
        page2 = self.connector.list_listings(limit=25, offset=25)
        self.assertIsInstance(page1, list)
        self.assertIsInstance(page2, list)
        self.assertLessEqual(len(page1), 25)
        self.assertLessEqual(len(page2), 25)

    def test_connection_reuse(self):
        """Test that multiple list_listings calls complete (client reuse is internal)."""
        for _ in range(5):
            listings = self.connector.list_listings(limit=5)
            self.assertIsInstance(listings, list)

    def test_concurrent_authentication(self):
        """Test that multiple connector instances can be created and used."""
        credentials = get_aws_credentials()
        connectors = [
            AWSDataExchangeConnector(
                aws_access_key_id=credentials["aws_access_key_id"],
                aws_secret_access_key=credentials["aws_secret_access_key"],
                region_name=credentials["region_name"],
            )
            for _ in range(3)
        ]
        results = []
        for c in connectors:
            try:
                c.authenticate(credentials)
                results.append(c.test_connection())
            except Exception:
                results.append(False)
        self.assertEqual(len(results), 3)
        self.assertTrue(
            any(results),
            "At least one connector should connect",
        )

    def test_concurrent_operations_error_handling(self):
        """Test concurrent list_listings; all complete (errors would raise)."""
        def list_listings():
            return self.connector.list_listings(limit=5)

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(list_listings) for _ in range(5)]
            results = [future.result() for future in as_completed(futures)]

        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIsInstance(result, list)

    def test_performance_with_zero_limit(self):
        """Test list_listings with zero limit returns empty list."""
        listings = self.connector.list_listings(limit=0)
        self.assertIsInstance(listings, list)
        self.assertEqual(len(listings), 0)

    def test_performance_with_very_large_limit(self):
        """Test list_listings rejects limit > 100 (AWS Data Exchange API limit)."""
        with self.assertRaises(ValueError) as ctx:
            self.connector.list_listings(limit=10000)
        self.assertIn("100", str(ctx.exception))
