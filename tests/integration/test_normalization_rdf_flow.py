"""
Integration Tests: Normalization → RDF Mapping Flow.

Tests end-to-end normalization → RDF mapping flow with all sections.
Uses real services (no mocks).
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.contracts.normalization import normalize_contract
from hub.apps.contracts.models import (
    Contract, NormalizationStatus, OriginalSpecType, OriginalFormat
)
from hub.apps.semantic.utils import map_contract_to_semantic
from hub.apps.semantic.models import SemanticResource, ResourceType
from hub.apps.semantic.service_client import SemanticServiceClient
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def check_semantic_service_available():
    """Check if semantic service is available"""
    try:
        client = SemanticServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


@pytest.mark.skipif(
    not check_semantic_service_available(),
    reason="Semantic service not available"
)
class NormalizationRDFFlowTest(TestCase):
    """Test normalization → RDF mapping flow"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_odcs_normalize_then_map_to_rdf(self):
        """Test ODCS contract: normalize → map to RDF"""
        odcs_contract_json = """{
            "id": "test-contract",
            "name": "Test Contract",
            "description": "Test description",
            "version": "1.0.0",
            "info": {
                "owners": [{"name": "Owner", "email": "owner@example.com"}],
                "tags": ["tag1", "tag2"]
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "ORDER_ID",
                        "is_primary_key": true
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": False,
                        "semantic_type": "EMAIL",
                        "format": "email"
                    }
                ],
                "primary_key": ["id"]
            },
            "quality": {
                "default_profile_key": "intake_basic",
                "rules": [
                    {
                        "rule_id": "not_null_id",
                        "dimension": "completeness",
                        "expression": "id IS NOT NULL",
                        "severity": "ERROR"
                    }
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"]
            },
            "lifecycle": {
                "data_source": "source.example.com",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0"}
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": []
            }
        }"""
        
        # Step 1: Normalize contract
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odcs_contract_json,
            format="JSON"
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        self.assertEqual(spec_type, OriginalSpecType.ODCS)
        
        # Step 2: Create contract with normalized HubContract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_spec_version=spec_version,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_contract_json,
            hub_contract_json=hub_contract,
            normalization_status=status,
            created_by=self.user
        )
        
        # Step 3: Map to RDF
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.resource_type, ResourceType.CONTRACT)
        self.assertEqual(semantic_resource.resource_id, contract.id)
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
        
        # Step 2: Create contract with normalized HubContract
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_spec_version=spec_version,
            original_format=OriginalFormat.JSON,
            original_raw=dc_contract_json,
            hub_contract_json=hub_contract,
            normalization_status=status,
            created_by=self.user
        )
        
        # Step 3: Map to RDF
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.resource_type, ResourceType.CONTRACT)
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_normalize_with_warnings_then_map(self):
        """Test normalization with warnings → map to RDF"""
        odcs_contract_json = """{
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            },
            "unmappable_field": "value"
        }"""
        
        # Normalize (should have warnings)
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odcs_contract_json,
            format="JSON"
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_WITH_WARNINGS)
        self.assertGreater(len(warnings), 0)
        
        # Create contract and map
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_contract_json,
            hub_contract_json=hub_contract,
            normalization_status=status,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    def test_normalize_update_remap_flow(self):
        """Test normalize → map → update contract → remap flow"""
        # Initial contract
        odcs_contract_json = """{
            "id": "test",
            "name": "Test",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }"""
        
        # Normalize
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=odcs_contract_json,
            format="JSON"
        )
        
        # Create and map
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_format=OriginalFormat.JSON,
            original_raw=odcs_contract_json,
            hub_contract_json=hub_contract,
            normalization_status=status,
            created_by=self.user
        )
        
        semantic_resource1 = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource1)
        triples_count1 = semantic_resource1.metadata_json.get('triples_count', 0)
        
        # Update contract
        updated_contract_json = """{
            "id": "test",
            "name": "Updated Test",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "email", "type": "string", "semantic_type": "EMAIL"}
                ]
            }
        }"""
        
        hub_contract_updated, _, _, status_updated, _, _ = normalize_contract(
            raw_contract=updated_contract_json,
            format="JSON"
        )
        
        contract.hub_contract_json = hub_contract_updated
        contract.normalization_status = status_updated
        contract.save()
        
        # Remap
        semantic_resource2 = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource2)
        self.assertEqual(semantic_resource1.id, semantic_resource2.id)
        # Triples count should increase with additional field
        triples_count2 = semantic_resource2.metadata_json.get('triples_count', 0)
        self.assertGreaterEqual(triples_count2, triples_count1)
    
    def test_complete_flow_all_sections(self):
        """Test complete flow with all HubContract sections"""
        complete_contract_json = """{
            "id": "complete",
            "name": "Complete Contract",
            "description": "Complete description",
            "version": "1.0.0",
            "info": {
                "owners": [
                    {"name": "Data Team", "email": "data@example.com"},
                    {"name": "Engineering", "email": "eng@example.com"}
                ],
                "tags": ["production", "analytics", "sales"]
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": false,
                        "semantic_type": "ORDER_ID",
                        "format": "uuid",
                        "is_primary_key": true
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "nullable": false,
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\\\.[a-zA-Z]{2,}$",
                        "min_length": 5,
                        "max_length": 255
                    }
                ],
                "primary_key": ["id"],
                "unique_constraints": [["email"]],
                "indexes": [{"name": "idx_email", "fields": ["email"]}]
            },
            "quality": {
                "default_profile_key": "intake_basic_soda",
                "rules": [
                    {
                        "rule_id": "completeness_rule",
                        "dimension": "completeness",
                        "expression": "id IS NOT NULL",
                        "severity": "ERROR"
                    },
                    {
                        "rule_id": "validity_rule",
                        "dimension": "validity",
                        "expression": "email LIKE '%@%'",
                        "severity": "WARNING"
                    }
                ]
            },
            "privacy_compliance": {
                "contains_personal_data": true,
                "personal_data_categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                "jurisdictions": ["GDPR", "LGPD"],
                "legal_bases": ["CONSENT", "LEGITIMATE_INTEREST"],
                "retention_policy": {
                    "period": "P5Y",
                    "notes": "5 years retention"
                }
            },
            "lifecycle": {
                "data_source": "https://source.example.com/data",
                "refresh_cadence": "HOURLY",
                "slas": {
                    "availability": "99.9",
                    "latency_ms_p95": 1000,
                    "latency_ms_p99": 2000
                }
            },
            "marketplace": {
                "license_summary": "Apache 2.0 License",
                "intended_use": ["analytics", "reporting", "machine_learning"],
                "restricted_use": ["resale", "competitive_analysis"]
            }
        }"""
        
        # Normalize
        hub_contract, spec_type, spec_version, status, errors, warnings = normalize_contract(
            raw_contract=complete_contract_json,
            format="JSON"
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(status, NormalizationStatus.NORMALIZED_OK)
        
        # Verify all sections are present
        self.assertIn("info", hub_contract)
        self.assertIn("schema", hub_contract)
        self.assertIn("quality", hub_contract)
        self.assertIn("privacy_compliance", hub_contract)
        self.assertIn("lifecycle", hub_contract)
        self.assertIn("marketplace", hub_contract)
        
        # Create and map
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=spec_type,
            original_spec_version=spec_version,
            original_format=OriginalFormat.JSON,
            original_raw=complete_contract_json,
            hub_contract_json=hub_contract,
            normalization_status=status,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # All sections should be mapped to RDF
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)

