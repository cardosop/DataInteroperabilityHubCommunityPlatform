"""
Comprehensive tests for Phase 15 API filtering endpoints.

Tests all new filtering capabilities:
- contact_email, contact_name
- server_type, server_url
- min_availability, max_latency_ms
- model_name
"""

import json

from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from tests.factories import AssetFactory


class APIFilteringPhase15TestCase(ContractsAPITestBase):
    """Test Phase 15 API filtering endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Phase 227 W1.13.4 — populate the minimum-viable structural-floor
        # shape (1 field per model, type=string, nullable=False).  The
        # filtering tests only assert on top-level fields (contact /
        # servers / servicelevels / model name lists) and don't depend
        # on field contents; the field is a pure floor satisfier so the
        # fixture remains valid under L3's unconditional enforcement.
        #
        # ``_min_fields()`` returns a fresh list-of-dicts on every call
        # so the per-fixture mutations stay isolated.  An earlier
        # iteration used ``list(_MIN_FIELDS)`` (a shallow copy that
        # shared the inner dict across all three contracts); replacing
        # it with a builder function eliminates that aliasing risk
        # without depending on ``copy.deepcopy`` being imported.
        def _min_fields():
            return [{"name": "id", "data_type": "string", "nullable": False}]

        # Create test contracts with various configurations.
        # Each contract gets its own asset to avoid unique_contract_version_per_asset constraint.
        self.contract1 = self._create_contract(
            name="Contract 1",
            contact=[{"email": "contact1@example.com", "name": "Contact One"}],
            servers=[{"type": "s3", "url": "s3://bucket1"}],
            servicelevels=[{"property": "availability", "target": 99.9}],
            models=[{"name": "model1", "fields": _min_fields()}],
        )

        self.contract2 = self._create_contract(
            name="Contract 2",
            contact=[{"email": "contact2@example.com", "name": "Contact Two"}],
            servers=[{"type": "postgres", "url": "postgresql://localhost/db"}],
            servicelevels=[{"property": "latency", "target": 100, "metric": "latency_ms"}],
            models=[{"name": "model2", "fields": _min_fields()}],
        )

        self.contract3 = self._create_contract(
            name="Contract 3",
            contact=[{"email": "contact3@example.com", "name": "Contact Three"}],
            servers=[{"type": "kafka", "url": "kafka://broker:9092"}],
            servicelevels=[
                {"property": "availability", "target": 99.5},
                {"property": "latency", "target": 50, "metric": "latency_ms"},
            ],
            models=[
                {"name": "model1", "fields": _min_fields()},
                {"name": "model3", "fields": _min_fields()},
            ],
        )

    def _create_contract(self, name, contact=None, servers=None, servicelevels=None, models=None):
        """Helper to create a contract with specific configuration.

        Each call creates its own asset so the unique constraint
        (tenant, asset, version) is never violated.
        """
        asset = AssetFactory(tenant=self.tenant)
        # Phase 227 W1.13.4 — normalise the schema field's key to
        # ``data_type`` (canonical Pydantic field name; ``type`` is
        # the back-compat alias).  The other fixture sites in setUp
        # use ``data_type`` so this keeps the helper consistent.
        hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": f"{name.lower().replace(' ', '-')}",
            "info": {"name": name},
            "schema": {"fields": [{"name": "id", "data_type": "string", "nullable": False}]},
        }

        if contact:
            hub_contract["contact"] = contact
        if servers:
            hub_contract["servers"] = servers
        if servicelevels:
            hub_contract["servicelevels"] = servicelevels
        if models:
            hub_contract["models"] = models

        return Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw=json.dumps({"id": name}),
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

    def test_filter_by_contact_email(self):
        """Test filtering contracts by contact email."""
        response = self.client.get("/api/v1/contracts/", {"contact_email": "contact1@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.contract1.id))

    def test_filter_by_contact_email_case_insensitive(self):
        """Test that contact email filtering is case-insensitive."""
        response = self.client.get("/api/v1/contracts/", {"contact_email": "CONTACT1@EXAMPLE.COM"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)

    def test_filter_by_contact_name(self):
        """Test filtering contracts by contact name."""
        response = self.client.get("/api/v1/contracts/", {"contact_name": "Contact One"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.contract1.id))

    def test_filter_by_contact_name_partial_match(self):
        """Test that contact name filtering supports partial matching."""
        response = self.client.get("/api/v1/contracts/", {"contact_name": "Contact"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertGreaterEqual(len(results), 1)

    def test_filter_by_server_type(self):
        """Test filtering contracts by server type."""
        response = self.client.get("/api/v1/contracts/", {"server_type": "s3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.contract1.id))

    def test_filter_by_server_type_multiple_matches(self):
        """Test filtering by server type when multiple contracts match."""
        # Create another contract with s3 server
        self._create_contract(name="Contract 4", servers=[{"type": "s3", "url": "s3://bucket2"}])

        response = self.client.get("/api/v1/contracts/", {"server_type": "s3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertGreaterEqual(len(results), 1)

    def test_filter_by_server_url(self):
        """Test filtering contracts by server URL."""
        response = self.client.get("/api/v1/contracts/", {"server_url": "s3://bucket1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 1)

    def test_filter_by_server_url_partial_match(self):
        """Test that server URL filtering supports partial matching."""
        response = self.client.get("/api/v1/contracts/", {"server_url": "s3://"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertGreaterEqual(len(results), 1)

    def test_filter_by_min_availability(self):
        """Test filtering contracts by minimum availability."""
        response = self.client.get("/api/v1/contracts/", {"min_availability": "99.8"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return contract1 (99.9) but not contract3 (99.5)
        contract_ids = [r["id"] for r in results]
        self.assertIn(str(self.contract1.id), contract_ids)
        self.assertNotIn(str(self.contract3.id), contract_ids)

    def test_filter_by_max_latency_ms(self):
        """Test filtering contracts by maximum latency."""
        response = self.client.get("/api/v1/contracts/", {"max_latency_ms": "75"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return contract3 (50ms) but not contract2 (100ms)
        contract_ids = [r["id"] for r in results]
        self.assertIn(str(self.contract3.id), contract_ids)
        self.assertNotIn(str(self.contract2.id), contract_ids)

    def test_filter_by_model_name(self):
        """Test filtering contracts by model name."""
        response = self.client.get("/api/v1/contracts/", {"model_name": "model1"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return contract1 and contract3 (both have model1)
        contract_ids = [r["id"] for r in results]
        self.assertIn(str(self.contract1.id), contract_ids)
        self.assertIn(str(self.contract3.id), contract_ids)
        self.assertNotIn(str(self.contract2.id), contract_ids)

    def test_filter_combination(self):
        """Test combining multiple filters."""
        response = self.client.get(
            "/api/v1/contracts/", {"server_type": "s3", "min_availability": "99.8"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return contract1 (s3 server, 99.9 availability)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], str(self.contract1.id))

    def test_filter_no_results(self):
        """Test filtering with criteria that match no contracts."""
        response = self.client.get(
            "/api/v1/contracts/", {"contact_email": "nonexistent@example.com"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        self.assertEqual(len(results), 0)

    def test_filter_invalid_min_availability(self):
        """Test filtering with invalid min_availability value."""
        response = self.client.get("/api/v1/contracts/", {"min_availability": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return empty results, not error
        self.assertEqual(len(results), 0)

    def test_filter_invalid_max_latency_ms(self):
        """Test filtering with invalid max_latency_ms value."""
        response = self.client.get("/api/v1/contracts/", {"max_latency_ms": "invalid"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should return empty results, not error
        self.assertEqual(len(results), 0)

    def test_filter_contract_without_contact(self):
        """Test filtering when contract has no contact information."""
        contract_no_contact = self._create_contract(
            name="Contract No Contact", servers=[{"type": "s3", "url": "s3://bucket"}]
        )

        response = self.client.get("/api/v1/contracts/", {"contact_email": "test@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should not include contract without contact
        contract_ids = [r["id"] for r in results]
        self.assertNotIn(str(contract_no_contact.id), contract_ids)

    def test_filter_contract_without_servers(self):
        """Test filtering when contract has no servers."""
        contract_no_servers = self._create_contract(
            name="Contract No Servers", contact=[{"email": "test@example.com"}]
        )

        response = self.client.get("/api/v1/contracts/", {"server_type": "s3"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should not include contract without servers
        contract_ids = [r["id"] for r in results]
        self.assertNotIn(str(contract_no_servers.id), contract_ids)

    def test_filter_contract_without_servicelevels(self):
        """Test filtering when contract has no servicelevels."""
        contract_no_sla = self._create_contract(
            name="Contract No SLA", contact=[{"email": "test@example.com"}]
        )

        response = self.client.get("/api/v1/contracts/", {"min_availability": "99.0"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.json().get("results", [])
        # Should not include contract without servicelevels
        contract_ids = [r["id"] for r in results]
        self.assertNotIn(str(contract_no_sla.id), contract_ids)
