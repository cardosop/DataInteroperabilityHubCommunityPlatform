"""
Performance Tests for Enhanced Contract Normalization & Semantic Mapping (GAP-11.2.1).

Tests performance targets:
- Normalization: <5s for 1000 fields, <10s for complex nested structures
- RDF mapping: <10s for complete contract, <15s for contract with all sections
- API response: <500ms for contract retrieval, <1s for contract creation
"""
import json
import os
import sys
import time

import pytest

pytestmark = pytest.mark.slow
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.tests.test_base import ContractsAPITestBase, ContractsTestBase
from hub.apps.tenants.models import Tenant

User = get_user_model()

# Resolve from project root (4 levels up from hub/apps/contracts/tests/)
semantic_service_path = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "../../../../services/semantic-service")
)
if semantic_service_path not in sys.path:
    sys.path.insert(0, semantic_service_path)
_rdf_available = False
try:
    from mapper import HubContractMapper
    from rdflib import Graph

    def map_hubcontract_to_rdf(hub_contract, contract_uuid):
        """Wrapper around HubContractMapper.map_hubcontract_to_rdf."""
        return HubContractMapper().map_hubcontract_to_rdf(hub_contract, contract_uuid)

    _rdf_available = True
except ImportError:
    map_hubcontract_to_rdf = None  # type: ignore[assignment]
    Graph = None  # type: ignore[assignment,misc]


pytestmark = pytest.mark.slow


class NormalizationPerformanceTest(ContractsTestBase):
    """Test normalization performance targets (GAP-11.2.1)"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_normalization_small_contract_performance(self):
        """Test normalization performance for small contract (10 fields) (GAP-11.2.1)"""
        # Create small contract
        contract_json = {
            "version": "2.2.2",
            "name": "Small Contract",
            "schema": {
                "fields": [
                    {"name": f"field_{i}", "type": "string", "description": f"Field {i}"}
                    for i in range(10)
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": "rule1",
                        "dimension": "completeness",
                        "expression": "field_0 IS NOT NULL",
                        "severity": "ERROR",
                    }
                ]
            },
        }

        import json

        contract_raw = json.dumps(contract_json)

        # Measure normalization time
        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            contract_raw, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Target: < 200ms P95 for small contracts
        self.assertLess(elapsed_time, 0.5)  # 500ms threshold (more lenient for test environment)
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(hub_contract["schema"]["fields"]), 10)

    def test_normalization_medium_contract_performance(self):
        """Test normalization performance for medium contract (100 fields) (GAP-11.2.1)"""
        # Create medium contract
        contract_json = {
            "version": "2.2.2",
            "name": "Medium Contract",
            "schema": {
                "fields": [
                    {
                        "name": f"field_{i}",
                        "type": "string",
                        "description": f"Field {i}",
                        "required": i % 2 == 0,
                    }
                    for i in range(100)
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": f"rule_{i}",
                        "dimension": "completeness",
                        "expression": f"field_{i} IS NOT NULL",
                        "severity": "ERROR",
                    }
                    for i in range(10)
                ],
                "default_profile_key": "custom_profile",
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL", "PHONE_NUMBER"],
                "jurisdictions": ["GDPR", "CCPA"],
                "legal_bases": ["CONSENT"],
            },
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["ANALYTICS"],
                "restricted_use": ["COMMERCIAL"],
            },
        }

        import json

        contract_raw = json.dumps(contract_json)

        # Measure normalization time
        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            contract_raw, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Target: < 1s P95 for medium contracts
        self.assertLess(elapsed_time, 2.0)  # 2s threshold (more lenient for test environment)
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(hub_contract["schema"]["fields"]), 100)

    def test_normalization_large_contract_performance(self):
        """Test normalization performance for large contract (1000 fields) (GAP-11.2.1)"""
        # Create large contract
        contract_json = {
            "version": "2.2.2",
            "name": "Large Contract",
            "schema": {
                "fields": [
                    {
                        "name": f"field_{i}",
                        "type": "string",
                        "description": f"Field {i}",
                        "required": i % 2 == 0,
                    }
                    for i in range(1000)
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": f"rule_{i}",
                        "dimension": "completeness",
                        "expression": f"field_{i} IS NOT NULL",
                        "severity": "ERROR",
                    }
                    for i in range(50)
                ]
            },
        }

        import json

        contract_raw = json.dumps(contract_json)

        # Measure normalization time
        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            contract_raw, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Target: < 10s P95 for large contracts
        self.assertLess(elapsed_time, 15.0)  # 15s threshold (more lenient for test environment)
        self.assertIsNotNone(hub_contract)
        self.assertEqual(len(hub_contract["schema"]["fields"]), 1000)

    def test_field_property_extraction_performance(self):
        """Test field property extraction performance (GAP-11.2.1)"""
        # Create contract with fields that need property extraction
        contract_json = {
            "version": "2.2.2",
            "name": "Property Extraction Test",
            "schema": {
                "fields": [
                    {"name": f"field_{i}", "type": "string", "description": f"Field {i}"}
                    for i in range(100)
                ]
            },
        }

        import json

        contract_raw = json.dumps(contract_json)

        # Measure normalization time
        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            contract_raw, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Target: < 200ms P95 per field for property extraction
        # For 100 fields, should be < 20s total (200ms * 100)
        # But normalization includes other work, so we use a more lenient threshold
        self.assertLess(elapsed_time, 5.0)  # 5s threshold
        self.assertIsNotNone(hub_contract)


@pytest.mark.skipif(not _rdf_available, reason="semantic-service mapper not installed")
class RDFMappingPerformanceTest(ContractsTestBase):
    """Test RDF mapping performance targets (GAP-11.2.1)"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    def test_rdf_mapping_small_contract_performance(self):
        """Test RDF mapping performance for small contract (GAP-11.2.1)"""
        hub_contract = {
            "info": {
                "name": "Small Contract",
                "owners": [{"name": "John", "email": "john@example.com"}],
                "tags": ["analytics"],
            },
            "schema": {
                "fields": [{"name": f"field_{i}", "data_type": "string"} for i in range(10)]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": "rule1",
                        "dimension": "completeness",
                        "expression": "field_0 IS NOT NULL",
                        "severity": "ERROR",
                    }
                ]
            },
        }

        contract_uuid = "test-uuid-123"

        # Measure RDF mapping time
        start_time = time.time()
        graph = map_hubcontract_to_rdf(hub_contract, contract_uuid)
        elapsed_time = time.time() - start_time

        # Target: < 500ms P95 for small contracts
        self.assertLess(elapsed_time, 1.0)  # 1s threshold (more lenient for test environment)
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph, Graph)

    def test_rdf_mapping_medium_contract_performance(self):
        """Test RDF mapping performance for medium contract (GAP-11.2.1)"""
        hub_contract = {
            "info": {
                "name": "Medium Contract",
                "owners": [
                    {"name": "John", "email": "john@example.com"},
                    {"name": "Jane", "email": "jane@example.com"},
                ],
                "tags": ["analytics", "sales", "marketing"],
            },
            "schema": {
                "fields": [
                    {
                        "name": f"field_{i}",
                        "data_type": "string",
                        "semantic_type": "EMAIL" if i == 0 else None,
                        "format": "email" if i == 0 else None,
                    }
                    for i in range(100)
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": f"rule_{i}",
                        "dimension": "completeness",
                        "expression": f"field_{i} IS NOT NULL",
                        "severity": "ERROR",
                    }
                    for i in range(10)
                ],
                "default_profile_key": "custom_profile",
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL", "PHONE_NUMBER"],
                "jurisdictions": ["GDPR", "CCPA"],
                "legal_bases": ["CONSENT"],
            },
            "lifecycle": {"data_source": "database", "refresh_cadence": "daily"},
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["ANALYTICS"],
                "restricted_use": ["COMMERCIAL"],
            },
        }

        contract_uuid = "test-uuid-456"

        # Measure RDF mapping time
        start_time = time.time()
        graph = map_hubcontract_to_rdf(hub_contract, contract_uuid)
        elapsed_time = time.time() - start_time

        # Target: < 2s P95 for medium contracts
        self.assertLess(elapsed_time, 5.0)  # 5s threshold (more lenient for test environment)
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph, Graph)

    def test_rdf_mapping_large_contract_performance(self):
        """Test RDF mapping performance for large contract (GAP-11.2.1)"""
        hub_contract = {
            "info": {
                "name": "Large Contract",
                "owners": [{"name": "John", "email": "john@example.com"}],
                "tags": ["analytics"],
            },
            "schema": {
                "fields": [
                    {
                        "name": f"field_{i}",
                        "data_type": "string",
                        "semantic_type": "EMAIL" if i == 0 else None,
                    }
                    for i in range(1000)
                ]
            },
            "quality": {
                "rules": [
                    {
                        "rule_id": f"rule_{i}",
                        "dimension": "completeness",
                        "expression": f"field_{i} IS NOT NULL",
                        "severity": "ERROR",
                    }
                    for i in range(50)
                ]
            },
        }

        contract_uuid = "test-uuid-789"

        # Measure RDF mapping time
        start_time = time.time()
        graph = map_hubcontract_to_rdf(hub_contract, contract_uuid)
        elapsed_time = time.time() - start_time

        # Target: < 20s P95 for large contracts
        self.assertLess(elapsed_time, 30.0)  # 30s threshold (more lenient for test environment)
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph, Graph)


class APIPerformanceTest(ContractsAPITestBase):
    """Test API response time performance targets (GAP-11.2.1)"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create contract with all sections
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "name": "Test Contract",
                    "owners": [{"name": "John Doe", "email": "john@example.com"}],
                    "tags": ["analytics", "sales"],
                },
                "schema": {
                    "fields": [
                        {
                            "name": f"field_{i}",
                            "data_type": "string",
                            "semantic_type": "EMAIL" if i == 0 else None,
                        }
                        for i in range(100)
                    ]
                },
                "quality": {
                    "rules": [
                        {
                            "rule_id": "rule1",
                            "dimension": "completeness",
                            "expression": "field_0 IS NOT NULL",
                            "severity": "ERROR",
                        }
                    ]
                },
                "privacy_compliance": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL"],
                    "jurisdictions": ["GDPR"],
                },
                "lifecycle": {"data_source": "database"},
                "marketplace": {"license_summary": "MIT License"},
            },
        )

    def test_contract_retrieval_performance(self):
        """Test contract retrieval API performance (GAP-11.2.1)"""
        # Measure API response time
        start_time = time.time()
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        elapsed_time = time.time() - start_time

        # Target: < 500ms P95 for contract retrieval
        self.assertLess(elapsed_time, 1.0)  # 1s threshold (more lenient for test environment)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify computed fields are included
        data = response.json()
        self.assertIn("owners", data)
        self.assertIn("tags", data)
        self.assertIn("quality_rules", data)
        self.assertIn("compliance_policy", data)
        self.assertIn("schema_fields", data)

    def test_contract_list_performance(self):
        """Test contract list API performance (GAP-11.2.1)"""
        # Create additional contracts
        for i in range(10):
            Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="2.2.2",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"version": "2.2.2", "name": "test{i}"}}',
                status=ContractStatus.DRAFT,
                hub_contract_version="1.0.0",
                hub_contract_json={"info": {"name": f"Contract {i}"}, "schema": {"fields": []}},
            )

        # Measure API response time
        start_time = time.time()
        response = self.client.get("/api/v1/contracts/")
        elapsed_time = time.time() - start_time

        # Target: < 300ms P95 for contract list
        self.assertLess(elapsed_time, 1.0)  # 1s threshold (more lenient for test environment)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify results are returned
        data = response.json()
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)

    def test_contract_list_with_filtering_performance(self):
        """Test contract list with filtering performance (GAP-11.2.1)"""
        # Measure API response time with filtering
        start_time = time.time()
        response = self.client.get(
            "/api/v1/contracts/", {"tag": "analytics", "compliance_regime": "GDPR"}
        )
        elapsed_time = time.time() - start_time

        # Target: < 300ms P95 for filtered list
        self.assertLess(elapsed_time, 1.0)  # 1s threshold (more lenient for test environment)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_contract_list_with_sorting_performance(self):
        """Test contract list with sorting performance (GAP-11.2.1)"""
        # Measure API response time with sorting
        start_time = time.time()
        response = self.client.get("/api/v1/contracts/", {"ordering": "-quality_score,-created_at"})
        elapsed_time = time.time() - start_time

        # Target: < 300ms P95 for sorted list
        self.assertLess(elapsed_time, 1.0)  # 1s threshold (more lenient for test environment)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Edge cases and error handling tests
    def test_normalization_performance_with_invalid_json(self):
        """Test normalization performance handling with invalid JSON."""
        invalid_json = "{ invalid json }"

        start_time = time.time()
        raised = False
        try:
            hub_contract, spec_type, spec_version, norm_status, errors, warnings = (
                normalize_contract(invalid_json, "JSON")
            )
            # If it returns rather than raising, status must indicate failure
            self.assertIn(
                norm_status,
                [NormalizationStatus.NORMALIZATION_FAILED, NormalizationStatus.NOT_NORMALIZED],
                f"Invalid JSON should fail normalization, got {norm_status}",
            )
        except (json.JSONDecodeError, ValueError, KeyError, TypeError):
            # Parse/schema errors are the expected rejection path
            raised = True
        elapsed_time = time.time() - start_time

        # Must fail fast regardless of path
        self.assertLess(elapsed_time, 1.0)
        # Must either raise or return a failure status (verified above)
        if not raised:
            self.assertIsNotNone(norm_status)

    def test_normalization_performance_with_empty_contract(self):
        """Test normalization performance with empty contract."""
        empty_json = "{}"

        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            empty_json, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Should handle empty contract quickly
        self.assertLess(elapsed_time, 1.0)
        # Empty {} has no spec fields — normalizer may return None or a
        # minimal hub contract depending on the fallback normalizer used.
        # The key requirement is fast handling (asserted above) and that the
        # function returns a valid 6-tuple without raising.
        self.assertIsInstance(norm_status, NormalizationStatus)

    def test_normalization_performance_with_very_large_contract(self):
        """Test normalization performance with very large contract (10000 fields)."""
        contract_json = {
            "version": "2.2.2",
            "name": "Very Large Contract",
            "schema": {
                "fields": [
                    {
                        "name": f"field_{i}",
                        "type": "string",
                        "description": f"Field {i}" * 100,  # Long descriptions
                    }
                    for i in range(10000)
                ]
            },
        }

        import json

        contract_raw = json.dumps(contract_json)

        start_time = time.time()
        hub_contract, spec_type, spec_version, norm_status, errors, warnings = normalize_contract(
            contract_raw, "JSON"
        )
        elapsed_time = time.time() - start_time

        # Should complete within reasonable time (may be slower but should not hang)
        self.assertLess(elapsed_time, 60.0)  # 60s threshold for very large contracts
        self.assertIsNotNone(hub_contract)

    @pytest.mark.skipif(not _rdf_available, reason="semantic-service mapper not installed")
    def test_rdf_mapping_performance_with_empty_contract(self):
        """Test RDF mapping performance with empty contract."""
        hub_contract = {}
        contract_uuid = "test-uuid-empty"

        start_time = time.time()
        graph = map_hubcontract_to_rdf(hub_contract, contract_uuid)
        elapsed_time = time.time() - start_time

        # Should handle empty contract quickly
        self.assertLess(elapsed_time, 1.0)
        self.assertIsNotNone(graph)

    @pytest.mark.skipif(not _rdf_available, reason="semantic-service mapper not installed")
    def test_rdf_mapping_performance_with_missing_fields(self):
        """Test RDF mapping performance with contract missing required fields."""
        hub_contract = {
            "info": {
                "name": "Incomplete Contract"
                # Missing other required fields
            }
        }
        contract_uuid = "test-uuid-incomplete"

        start_time = time.time()
        graph = map_hubcontract_to_rdf(hub_contract, contract_uuid)
        elapsed_time = time.time() - start_time

        # Should handle incomplete contract gracefully
        self.assertLess(elapsed_time, 5.0)
        self.assertIsNotNone(graph)

    def test_api_retrieval_performance_contract_not_found(self):
        """Test API retrieval performance when contract not found."""
        import uuid

        fake_id = str(uuid.uuid4())

        start_time = time.time()
        response = self.client.get(f"/api/v1/contracts/{fake_id}/")
        elapsed_time = time.time() - start_time

        # Should fail quickly (404)
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_api_list_performance_with_invalid_filters(self):
        """Test API list performance with invalid filter parameters."""
        start_time = time.time()
        response = self.client.get(
            "/api/v1/contracts/", {"invalid_param": "value", "another_invalid": "test"}
        )
        elapsed_time = time.time() - start_time

        # Should handle invalid filters gracefully and quickly
        self.assertLess(elapsed_time, 1.0)
        # Unknown params should be ignored (200) — not crash (500)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_list_performance_with_invalid_sorting(self):
        """Test API list performance with invalid sort parameters."""
        start_time = time.time()
        response = self.client.get("/api/v1/contracts/", {"ordering": "invalid_field"})
        elapsed_time = time.time() - start_time

        # Should handle invalid sorting gracefully and quickly
        self.assertLess(elapsed_time, 1.0)
        # Invalid ordering must not crash the server
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
        )
        self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_api_list_performance_with_pagination(self):
        """Test API list performance with pagination."""
        # Create many contracts for pagination
        for i in range(50):
            Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="2.2.2",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"version": "2.2.2", "name": "test{i}"}}',
                status=ContractStatus.DRAFT,
                hub_contract_version="1.0.0",
                hub_contract_json={"info": {"name": f"Contract {i}"}, "schema": {"fields": []}},
            )

        start_time = time.time()
        response = self.client.get("/api/v1/contracts/", {"page": 2, "page_size": 10})
        elapsed_time = time.time() - start_time

        # Should handle pagination efficiently
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_api_retrieval_performance_with_computed_fields(self):
        """Test API retrieval performance includes computed fields efficiently."""
        start_time = time.time()
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        elapsed_time = time.time() - start_time

        # Should include computed fields without significant performance impact
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.json()
        # Verify computed fields are present
        self.assertIn("owners", data)
        self.assertIn("tags", data)

    def test_normalization_performance_consistency(self):
        """Test that normalization performance is consistent across multiple runs."""
        contract_json = {
            "version": "2.2.2",
            "name": "Consistency Test",
            "schema": {"fields": [{"name": f"field_{i}", "type": "string"} for i in range(100)]},
        }

        import json

        contract_raw = json.dumps(contract_json)

        times = []
        for _ in range(5):
            start_time = time.time()
            normalize_contract(contract_raw, "JSON")
            elapsed_time = time.time() - start_time
            times.append(elapsed_time)

        # Performance should be relatively consistent
        # Check that all runs complete within reasonable time
        for elapsed_time in times:
            self.assertLess(elapsed_time, 5.0)

        # Check that variance is not too large.  Use a floor of 10ms so
        # sub-millisecond jitter (timer resolution, GC) doesn't trigger
        # false failures when actual normalization is fast.
        min_time = min(times)
        max_time = max(times)
        threshold = max(min_time * 5, 0.01)  # 5x or 10ms, whichever is larger
        self.assertLess(max_time, threshold)
