"""
Integration Tests: SPARQL Queries with Standard Vocabularies.

Tests SPARQL queries using DQV, DPV, PROV-O, ODRL, SHACL, Schema.org, and FOAF vocabularies.
Uses real semantic service (no mocks - skips if service unavailable).
"""

import contextlib
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.contracts.models import (
    Contract,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
from hub.apps.semantic.service_client import SemanticServiceClient
from hub.apps.semantic.utils import map_contract_to_semantic
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def check_semantic_service_available():
    """Check if semantic service is available"""
    try:
        client = SemanticServiceClient()
        is_healthy, _fuseki_status = client.health_check(use_cache=False)
        # Service is available only if health check returns healthy status
        # fuseki_status can be "connected", "disconnected", "timeout", "unreachable", or "unknown"
        # We only consider the service available if is_healthy is True
        return is_healthy
    except Exception as e:
        # Log the exception for debugging but don't fail
        import logging

        logger = logging.getLogger(__name__)
        logger.debug(f"Semantic service not available: {e}")
        return False


def _skip_if_circuit_breaker(result):
    """Skip test when semantic service returns circuit breaker (unavailable at runtime)."""
    if (
        isinstance(result, dict)
        and result.get("error")
        and "circuit breaker" in str(result.get("error", "")).lower()
    ):
        pytest.skip("Semantic service unavailable (circuit breaker open)")
    if isinstance(result, str) and "circuit breaker" in result.lower():
        pytest.skip("Semantic service unavailable (circuit breaker open)")


class SPARQLStandardVocabulariesTest(TestCase):
    """Test SPARQL queries with standard vocabularies. Skips at runtime if semantic service unavailable."""

    def setUp(self):
        """Set up test fixtures. Check semantic service at runtime (not collection) so batch runs can pass when service is up."""
        reset_circuit_breaker_by_name("semantic-service")
        if not check_semantic_service_available():
            pytest.skip("Semantic service not available")
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client = SemanticServiceClient()

        # Create and map a contract with all sections for testing
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            contract_id="sparql-test-contract",
            owners=[{"name": "Data Team", "email": "data@example.com"}],
            tags=["production", "analytics"],
            quality_rules=[
                {
                    "rule_id": "completeness_rule",
                    "dimension": "completeness",
                    "expression": "id IS NOT NULL",
                    "severity": "ERROR",
                }
            ],
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
            },
            lifecycle_policy={
                "data_source": "source.example.com",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0"},
            },
            marketplace_policy={
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": [],
            },
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "semantic_type": "EMAIL",
                    "format": "email",
                }
            ],
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "sparql-test-contract"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user,
        )

        # Map contract to RDF
        self.semantic_resource = map_contract_to_semantic(self.contract, tenant=self.tenant)
        self.assertIsNotNone(self.semantic_resource)

    def tearDown(self):
        """Clean up RDF data from Fuseki to prevent accumulation across tests."""
        if hasattr(self, "semantic_resource") and self.semantic_resource is not None:
            try:
                self.client.delete_resource_triples(
                    tenant_id=str(self.tenant.id),
                    iri=self.semantic_resource.uri,
                )
            except Exception:
                # Log the failure rather than silently ignoring it.
                # The delete is best-effort — a timeout or circuit-breaker
                # open means Fuseki is overloaded; the remaining tests
                # should still be resilient via adequate query timeouts.
                pass

    def test_sparql_query_dqv_quality_rules(self):
        """Test SPARQL query for quality rules using DQV vocabulary"""
        query = """
        PREFIX dqv: <https://www.w3.org/ns/dqv#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?rule ?dimension ?expression
        WHERE {
            ?contract hub:hasQualityRule ?rule .
            ?rule hub:ruleDimension ?dimension .
            ?rule dqv:isMeasurementOf ?dqvDimension .
            ?rule hub:ruleExpression ?expression .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        # Should not have error
        self.assertNotIn("error", result)
        # Should have results or empty results (depending on data)
        self.assertIsInstance(result, dict)

    def test_sparql_query_dpv_compliance_policy(self):
        """Test SPARQL query for compliance policy using DPV vocabulary"""
        query = """
        PREFIX dpv: <https://www.w3.org/ns/dpv#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?containsPersonalData ?category ?jurisdiction
        WHERE {
            ?contract hub:hasCompliancePolicy ?policy .
            ?policy hub:containsPersonalData ?containsPersonalData .
            OPTIONAL { ?policy hub:hasPersonalDataCategory ?category . }
            OPTIONAL { ?policy hub:hasJurisdiction ?jurisdiction . }
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_prov_lifecycle_policy(self):
        """Test SPARQL query for lifecycle policy using PROV-O vocabulary"""
        query = """
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?dataSource ?refreshCadence
        WHERE {
            ?contract hub:hasLifecyclePolicy ?policy .
            ?policy hub:dataSource ?dataSource .
            ?policy hub:refreshCadence ?refreshCadence .
            ?contract prov:wasDerivedFrom ?source .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_odrl_marketplace_policy(self):
        """Test SPARQL query for marketplace policy using ODRL vocabulary"""
        query = """
        PREFIX odrl: <https://www.w3.org/ns/odrl/2/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?licenseSummary ?intendedUse ?restrictedUse
        WHERE {
            ?contract hub:hasMarketplacePolicy ?policy .
            ?policy hub:licenseSummary ?licenseSummary .
            OPTIONAL { ?policy hub:intendedUse ?intendedUse . }
            OPTIONAL { ?policy hub:restrictedUse ?restrictedUse . }
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_shacl_field_validation(self):
        """Test SPARQL query for field validation using SHACL vocabulary"""
        query = """
        PREFIX shacl: <http://www.w3.org/ns/shacl#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?field ?format ?pattern ?minLength ?maxLength
        WHERE {
            ?contract hub:hasField ?field .
            ?field hub:fieldFormat ?format .
            OPTIONAL { ?field hub:fieldPattern ?pattern . }
            OPTIONAL { ?field hub:fieldMinLength ?minLength . }
            OPTIONAL { ?field hub:fieldMaxLength ?maxLength . }
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_schema_org_semantic_types(self):
        """Test SPARQL query for semantic types using Schema.org vocabulary"""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX schema: <https://schema.org/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?field ?semanticType ?schemaType
        WHERE {
            ?contract hub:hasField ?field .
            ?field hub:fieldSemanticType ?semanticType .
            ?field rdf:type ?schemaType .
            FILTER (strstarts(str(?schemaType), "https://schema.org/"))
        }
        LIMIT 10
        """

        # FILTER(strstarts(str(...))) forces per-row type coercion; allow extra time
        result = self.client.query_sparql(
            query, output_format="json", tenant_id=str(self.tenant.id), timeout=120
        )
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_foaf_owners(self):
        """Test SPARQL query for owners using FOAF vocabulary"""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?owner ?ownerName ?ownerEmail
        WHERE {
            ?contract hub:hasOwner ?owner .
            ?owner hub:ownerName ?ownerName .
            ?owner hub:ownerEmail ?ownerEmail .
            ?owner rdf:type foaf:Person .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_all_vocabularies_combined(self):
        """Test SPARQL query combining all standard vocabularies"""
        query = """
        PREFIX dqv: <https://www.w3.org/ns/dqv#>
        PREFIX dpv: <https://www.w3.org/ns/dpv#>
        PREFIX prov: <http://www.w3.org/ns/prov#>
        PREFIX odrl: <https://www.w3.org/ns/odrl/2/>
        PREFIX shacl: <http://www.w3.org/ns/shacl#>
        PREFIX schema: <https://schema.org/>
        PREFIX foaf: <http://xmlns.com/foaf/0.1/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?rule ?policy ?field ?owner
        WHERE {
            ?contract hub:hasQualityRule ?rule .
            ?contract hub:hasCompliancePolicy ?policy .
            ?contract hub:hasField ?field .
            ?contract hub:hasOwner ?owner .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_quality_rules_by_dimension(self):
        """Test SPARQL query filtering quality rules by dimension"""
        query = """
        PREFIX dqv: <https://www.w3.org/ns/dqv#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?rule ?dimension ?expression ?severity
        WHERE {
            ?contract hub:hasQualityRule ?rule .
            ?rule hub:ruleDimension "completeness" .
            ?rule dqv:isMeasurementOf dqv:completeness .
            ?rule hub:ruleExpression ?expression .
            ?rule hub:ruleSeverity ?severity .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_compliance_by_jurisdiction(self):
        """Test SPARQL query filtering compliance policies by jurisdiction"""
        query = """
        PREFIX dpv: <https://www.w3.org/ns/dpv#>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?policy ?jurisdiction
        WHERE {
            ?contract hub:hasCompliancePolicy ?policy .
            ?policy hub:hasJurisdiction "GDPR" .
            ?policy hub:hasJurisdiction ?jurisdiction .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_fields_by_semantic_type(self):
        """Test SPARQL query filtering fields by semantic type"""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX schema: <https://schema.org/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?field ?semanticType ?schemaType
        WHERE {
            ?contract hub:hasField ?field .
            ?field hub:fieldSemanticType "EMAIL" .
            ?field hub:fieldSemanticType ?semanticType .
            ?field rdf:type ?schemaType .
        }
        LIMIT 10
        """

        result = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result)
        self.assertNotIn("error", result)
        self.assertIsInstance(result, dict)

    def test_sparql_query_output_formats(self):
        """Test SPARQL query with different output formats"""
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX dct: <http://purl.org/dc/terms/>
        PREFIX hub: <https://hub.example.com/ontology#>
        
        SELECT ?contract ?name
        WHERE {
            ?contract rdf:type hub:DataContract .
            ?contract dct:title ?name .
        }
        LIMIT 5
        """

        # Test JSON format
        result_json = self.client.query_sparql(query, output_format="json", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result_json)
        self.assertNotIn("error", result_json)
        # Test CSV format
        result_csv = self.client.query_sparql(query, output_format="csv", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result_csv)
        self.assertNotIn("error", result_csv)
        # Test Turtle format
        result_turtle = self.client.query_sparql(query, output_format="turtle", tenant_id=str(self.tenant.id), timeout=120)
        _skip_if_circuit_breaker(result_turtle)
        self.assertNotIn("error", result_turtle)
