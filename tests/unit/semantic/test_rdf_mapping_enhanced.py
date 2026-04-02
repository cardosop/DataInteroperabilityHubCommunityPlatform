"""
Enhanced Unit Tests for RDF Mapping.

Tests complete contract mapping, field validation mapping, schema constraint mapping,
quality rule mapping, compliance policy mapping, lifecycle policy mapping,
marketplace policy mapping, owner mapping, tag mapping, and semantic type mapping.
Uses real semantic service client (no mocks - skips if service unavailable).
"""
import pytest
import os
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from hub.apps.semantic.models import SemanticResource, SemanticResourceStatus, ResourceType
from hub.apps.semantic.utils import (
    map_contract_to_semantic,
    map_asset_to_semantic,
    remap_contract_if_needed,
    generate_uri
)
from hub.apps.semantic.service_client import SemanticServiceClient
from hub.apps.semantic.signals import contract_saved, asset_saved
from hub.apps.contracts.models import (
    Contract, ContractStatus, ValidationStatus, NormalizationStatus,
    OriginalSpecType, OriginalFormat
)
from hub.apps.assets.models import Asset, AssetStatus, DQStatus, ComplianceStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
import uuid

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
class EnhancedRDFMappingTest(TestCase):
    """Enhanced RDF mapping tests with real semantic service"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Disconnect signals to prevent automatic mapping during test setup
        post_save.disconnect(contract_saved, sender=Contract)
        post_save.disconnect(asset_saved, sender=Asset)
        
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def tearDown(self):
        """Reconnect signals after test"""
        post_save.connect(contract_saved, sender=Contract)
        post_save.connect(asset_saved, sender=Asset)
    
    # Complete Contract Mapping Tests
    def test_map_contract_with_all_sections(self):
        """Test mapping contract with all HubContract sections"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            contract_id="complete-contract",
            name="Complete Contract",
            owners=[
                {"name": "Data Team", "email": "data@example.com"}
            ],
            tags=["production", "analytics"],
            quality_rules=[
                {
                    "rule_id": "not_null_id",
                    "dimension": "completeness",
                    "expression": "id IS NOT NULL",
                    "severity": "ERROR"
                }
            ],
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P5Y"}
            },
            lifecycle_policy={
                "data_source": "source.example.com",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.9", "latency_ms_p95": 1000}
            },
            marketplace_policy={
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": []
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "complete-contract"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Map contract
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        # Verify semantic resource was created
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.resource_type, ResourceType.CONTRACT)
        self.assertEqual(semantic_resource.resource_id, contract.id)
        self.assertIn('contract', semantic_resource.uri.lower())
        
        # Verify metadata includes triples count
        self.assertIn('triples_count', semantic_resource.metadata_json)
        self.assertGreater(semantic_resource.metadata_json['triples_count'], 0)
    
    def test_map_contract_with_owners(self):
        """Test mapping contract with owners (FOAF mapping)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            owners=[
                {"name": "Owner 1", "email": "owner1@example.com"},
                {"name": "Owner 2", "email": "owner2@example.com"}
            ]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Owners should be mapped (verified via triples count increase)
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_tags(self):
        """Test mapping contract with tags (dcat:keyword mapping)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            tags=["tag1", "tag2", "tag3"]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Tags should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Field Validation Mapping Tests (SHACL)
    def test_map_contract_with_field_validation_properties(self):
        """Test mapping contract with field validation properties (SHACL)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "nullable": False,
                    "description": "User email",
                    "semantic_type": "EMAIL",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                    "min_length": 5,
                    "max_length": 255
                },
                {
                    "name": "age",
                    "data_type": "integer",
                    "nullable": True,
                    "minimum": 0,
                    "maximum": 150
                }
            ]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Field validation properties should be mapped (SHACL)
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_semantic_types(self):
        """Test mapping contract with semantic types (Schema.org mapping)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "semantic_type": "EMAIL"
                },
                {
                    "name": "phone",
                    "data_type": "string",
                    "semantic_type": "PHONE"
                },
                {
                    "name": "order_id",
                    "data_type": "string",
                    "semantic_type": "ORDER_ID"
                }
            ]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Semantic types should be mapped to Schema.org
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Schema Constraint Mapping Tests
    def test_map_contract_with_primary_key(self):
        """Test mapping contract with primary key constraints"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "id",
                    "data_type": "string",
                    "nullable": False,
                    "is_primary_key": True
                }
            ],
            primary_key=["id"]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Primary key should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_unique_constraints(self):
        """Test mapping contract with unique constraints"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "is_unique": True
                }
            ],
            unique_constraints=[["email"]]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Unique constraints should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_indexes(self):
        """Test mapping contract with indexes"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "is_indexed": True
                }
            ],
            indexes=[{"name": "idx_email", "fields": ["email"]}]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Indexes should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Quality Rule Mapping Tests (DQV)
    def test_map_contract_with_quality_rules_dqv(self):
        """Test mapping contract with quality rules (DQV vocabulary)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            quality_rules=[
                {
                    "rule_id": "completeness_rule",
                    "dimension": "completeness",
                    "expression": "id IS NOT NULL",
                    "severity": "ERROR"
                },
                {
                    "rule_id": "accuracy_rule",
                    "dimension": "accuracy",
                    "expression": "email LIKE '%@%'",
                    "severity": "WARNING"
                },
                {
                    "rule_id": "validity_rule",
                    "dimension": "validity",
                    "expression": "age >= 0 AND age <= 150",
                    "severity": "ERROR"
                }
            ]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Quality rules should be mapped with DQV vocabulary
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_default_quality_profile(self):
        """Test mapping contract with default quality profile"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            quality_rules=[]  # Empty rules but has default_profile_key
        )
        hub_contract["quality"]["default_profile_key"] = "intake_basic_soda"
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Default quality profile should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Compliance Policy Mapping Tests (DPV)
    def test_map_contract_with_compliance_policy_dpv(self):
        """Test mapping contract with compliance policy (DPV vocabulary)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL", "PII_DIRECT_PHONE"],
                "jurisdictions": ["GDPR", "LGPD", "CCPA"],
                "legal_bases": ["CONSENT", "LEGITIMATE_INTEREST"],
                "retention_policy": {
                    "period": "P5Y",
                    "notes": "5 years retention"
                }
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Compliance policy should be mapped with DPV vocabulary
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_no_personal_data(self):
        """Test mapping contract with no personal data"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            compliance_policy={
                "contains_personal_data": False,
                "personal_data_categories": [],
                "jurisdictions": [],
                "legal_bases": [],
                "retention_policy": None
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Even with no personal data, compliance policy should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Lifecycle Policy Mapping Tests (PROV-O)
    def test_map_contract_with_lifecycle_policy_prov(self):
        """Test mapping contract with lifecycle policy (PROV-O vocabulary)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            lifecycle_policy={
                "data_source": "https://source.example.com/data",
                "refresh_cadence": "DAILY",
                "slas": {
                    "availability": "99.9",
                    "latency_ms_p95": 1000,
                    "latency_ms_p99": 2000
                }
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Lifecycle policy should be mapped with PROV-O vocabulary
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_different_refresh_cadences(self):
        """Test mapping contract with different refresh cadences"""
        cadences = ["HOURLY", "DAILY", "WEEKLY", "MONTHLY", "ON_DEMAND"]
        
        for cadence in cadences:
            hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
                lifecycle_policy={
                    "data_source": "source.example.com",
                    "refresh_cadence": cadence,
                    "slas": {"availability": "99.0"}
                }
            )
            
            contract = Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "test-{cadence}"}}',
                hub_contract_json=hub_contract,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=self.user
            )
            
            semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
            self.assertIsNotNone(semantic_resource)
    
    # Marketplace Policy Mapping Tests (ODRL)
    def test_map_contract_with_marketplace_policy_odrl(self):
        """Test mapping contract with marketplace policy (ODRL vocabulary)"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            marketplace_policy={
                "license_summary": "Apache 2.0 License",
                "intended_use": ["analytics", "reporting", "machine_learning"],
                "restricted_use": ["resale", "competitive_analysis"]
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Marketplace policy should be mapped with ODRL vocabulary
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_with_empty_marketplace_policy(self):
        """Test mapping contract with empty marketplace policy"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            marketplace_policy={
                "license_summary": None,
                "intended_use": [],
                "restricted_use": []
            }
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Empty marketplace policy should still be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    # Complete Mapping Tests
    def test_map_contract_with_all_field_properties(self):
        """Test mapping contract with all field properties"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "complete_field",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Complete field",
                    "semantic_type": "EMAIL",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                    "enum": None,
                    "default": "test@example.com",
                    "min_length": 5,
                    "max_length": 255,
                    "minimum": None,
                    "maximum": None,
                    "metadata": {"source": "CRM"},
                    "is_primary_key": True,
                    "is_unique": True,
                    "is_indexed": True
                }
            ],
            primary_key=["complete_field"]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # All field properties should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)
    
    def test_map_contract_updates_existing_resource(self):
        """Test that mapping updates existing semantic resource"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json()
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # First mapping
        semantic_resource1 = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource1)
        triples_count1 = semantic_resource1.metadata_json.get('triples_count', 0)
        
        # Update contract
        hub_contract["info"]["name"] = "Updated Contract"
        contract.hub_contract_json = hub_contract
        contract.save()
        
        # Second mapping (should update)
        semantic_resource2 = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource2)
        self.assertEqual(semantic_resource1.id, semantic_resource2.id)
        # Triples count may change after update
        self.assertIsNotNone(semantic_resource2.metadata_json.get('triples_count'))
    
    def test_map_contract_with_asset_link(self):
        """Test mapping contract with asset link"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json()
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # Asset link should be included in mapping
        self.assertEqual(semantic_resource.metadata_json.get('asset_uuid'), str(asset.id))
    
    def test_remap_contract_if_needed_with_asset(self):
        """Test remapping contract when asset is attached"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {"name": "id", "data_type": "string", "nullable": False}
            ]
        )
        
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            created_by=self.user
        )
        
        # Initially no asset - remap should return None
        result = remap_contract_if_needed(contract, tenant=self.tenant)
        self.assertIsNone(result)
        
        # Attach asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        contract.asset = asset
        contract.save()
        
        # Now remap should work
        semantic_resource = remap_contract_if_needed(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.metadata_json.get('asset_uuid'), str(asset.id))
    
    def test_map_contract_without_hub_contract_json(self):
        """Test mapping contract without hub_contract_json returns None"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test"}',
            hub_contract_json=None,
            created_by=self.user
        )
        
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        # Should return None when no hub_contract_json
        self.assertIsNone(semantic_resource)
    
    def test_generate_uri_for_different_resource_types(self):
        """Test URI generation for different resource types"""
        test_id = "123e4567-e89b-12d3-a456-426614174000"
        
        contract_uri = generate_uri(ResourceType.CONTRACT, test_id)
        self.assertIn("contract", contract_uri.lower())
        self.assertIn(test_id, contract_uri)
        
        asset_uri = generate_uri(ResourceType.ASSET, test_id)
        self.assertIn("asset", asset_uri.lower())
        self.assertIn(test_id, asset_uri)
        
        dataset_uri = generate_uri(ResourceType.DATASET, test_id)
        self.assertIn("dataset", dataset_uri.lower())
        self.assertIn(test_id, dataset_uri)
    
    def test_map_asset_to_semantic(self):
        """Test mapping asset to semantic RDF"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test description",
            status=AssetStatus.ACTIVE,
            dq_status=DQStatus.PASS,
            compliance_status=ComplianceStatus.PASS,
            created_by=self.user
        )
        
        semantic_resource = map_asset_to_semantic(asset, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        self.assertEqual(semantic_resource.resource_type, ResourceType.ASSET)
        self.assertEqual(semantic_resource.resource_id, asset.id)
        self.assertIn('asset', semantic_resource.uri.lower())
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)

