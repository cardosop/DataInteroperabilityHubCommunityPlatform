"""
Unit Tests for Standard Vocabulary Mappings.

Tests DQV, DPV, PROV-O, ODRL, SHACL, Schema.org, and FOAF vocabulary mappings.
Uses real semantic service client (no mocks - skips if service unavailable).
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

from hub.apps.semantic.service_client import SemanticServiceClient
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, NormalizationStatus
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
class StandardVocabularyTest(TestCase):
    """Test standard vocabulary mappings"""
    
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
    
    # DQV Vocabulary Tests
    def test_dqv_completeness_dimension_mapping(self):
        """Test DQV completeness dimension mapping"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            quality_rules=[
                {
                    "rule_id": "completeness_rule",
                    "dimension": "completeness",
                    "expression": "id IS NOT NULL",
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
        
        # Verify contract can be mapped (DQV completeness should be used)
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    def test_dqv_accuracy_dimension_mapping(self):
        """Test DQV accuracy dimension mapping"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            quality_rules=[
                {
                    "rule_id": "accuracy_rule",
                    "dimension": "accuracy",
                    "expression": "email LIKE '%@%'",
                    "severity": "WARNING"
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    def test_dqv_all_dimensions_mapping(self):
        """Test all DQV dimensions mapping"""
        dimensions = ["completeness", "accuracy", "consistency", "timeliness", "validity", "uniqueness"]
        
        for dimension in dimensions:
            hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
                quality_rules=[
                    {
                        "rule_id": f"{dimension}_rule",
                        "dimension": dimension,
                        "expression": "test IS NOT NULL",
                        "severity": "ERROR"
                    }
                ]
            )
            
            contract = Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "test-{dimension}"}}',
                hub_contract_json=hub_contract,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=self.user
            )
            
            from hub.apps.semantic.utils import map_contract_to_semantic
            semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
            self.assertIsNotNone(semantic_resource)
    
    # DPV Vocabulary Tests
    def test_dpv_email_address_category_mapping(self):
        """Test DPV email address category mapping"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"]
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    def test_dpv_jurisdiction_mapping(self):
        """Test DPV jurisdiction mapping"""
        jurisdictions = ["GDPR", "LGPD", "CCPA", "HIPAA", "SOX"]
        
        for jurisdiction in jurisdictions:
            hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
                compliance_policy={
                    "contains_personal_data": True,
                    "personal_data_categories": [],
                    "jurisdictions": [jurisdiction],
                    "legal_bases": ["CONSENT"]
                }
            )
            
            contract = Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "test-{jurisdiction}"}}',
                hub_contract_json=hub_contract,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=self.user
            )
            
            from hub.apps.semantic.utils import map_contract_to_semantic
            semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
            self.assertIsNotNone(semantic_resource)
    
    def test_dpv_legal_basis_mapping(self):
        """Test DPV legal basis mapping"""
        legal_bases = ["CONSENT", "LEGITIMATE_INTEREST", "CONTRACT", "LEGAL_OBLIGATION"]
        
        for legal_basis in legal_bases:
            hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
                compliance_policy={
                    "contains_personal_data": True,
                    "personal_data_categories": [],
                    "jurisdictions": ["GDPR"],
                    "legal_bases": [legal_basis]
                }
            )
            
            contract = Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "test-{legal_basis}"}}',
                hub_contract_json=hub_contract,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=self.user
            )
            
            from hub.apps.semantic.utils import map_contract_to_semantic
            semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
            self.assertIsNotNone(semantic_resource)
    
    # PROV-O Vocabulary Tests
    def test_prov_was_derived_from_mapping(self):
        """Test PROV-O wasDerivedFrom mapping for data source"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            lifecycle_policy={
                "data_source": "https://source.example.com/data",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0"}
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    # ODRL Vocabulary Tests
    def test_odrl_permission_mapping(self):
        """Test ODRL permission mapping for intended use"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            marketplace_policy={
                "license_summary": "MIT License",
                "intended_use": ["analytics", "reporting"],
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    def test_odrl_prohibition_mapping(self):
        """Test ODRL prohibition mapping for restricted use"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            marketplace_policy={
                "license_summary": "MIT License",
                "intended_use": [],
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    # SHACL Vocabulary Tests
    def test_shacl_validation_mapping(self):
        """Test SHACL validation mapping for field constraints"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "nullable": False,
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
                    "min_length": 5,
                    "max_length": 255
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    # Schema.org Vocabulary Tests
    def test_schema_org_type_mapping(self):
        """Test Schema.org type mapping for semantic types"""
        semantic_types = ["EMAIL", "PHONE", "ORDER_ID", "CURRENCY", "DATE", "DATETIME"]
        
        for semantic_type in semantic_types:
            hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
                schema_fields=[
                    {
                        "name": f"field_{semantic_type.lower()}",
                        "data_type": "string",
                        "semantic_type": semantic_type
                    }
                ]
            )
            
            contract = Contract.objects.create(
                tenant=self.tenant,
                original_spec_type=OriginalSpecType.ODCS,
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "test-{semantic_type}"}}',
                hub_contract_json=hub_contract,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                created_by=self.user
            )
            
            from hub.apps.semantic.utils import map_contract_to_semantic
            semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
            self.assertIsNotNone(semantic_resource)
    
    # FOAF Vocabulary Tests
    def test_foaf_owner_mapping(self):
        """Test FOAF owner mapping"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            owners=[
                {"name": "Data Team", "email": "data@example.com"},
                {"name": "Engineering Team", "email": "eng@example.com"}
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        self.assertIsNotNone(semantic_resource)
    
    # Combined Vocabulary Tests
    def test_all_vocabularies_combined(self):
        """Test all standard vocabularies combined in one contract"""
        hub_contract = ContractFactoryEnhanced.create_hub_contract_json(
            owners=[{"name": "Owner", "email": "owner@example.com"}],
            tags=["tag1", "tag2"],
            quality_rules=[
                {
                    "rule_id": "completeness_rule",
                    "dimension": "completeness",
                    "expression": "id IS NOT NULL",
                    "severity": "ERROR"
                }
            ],
            compliance_policy={
                "contains_personal_data": True,
                "personal_data_categories": ["PII_DIRECT_EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"]
            },
            lifecycle_policy={
                "data_source": "source.example.com",
                "refresh_cadence": "DAILY",
                "slas": {"availability": "99.0"}
            },
            marketplace_policy={
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": []
            },
            schema_fields=[
                {
                    "name": "email",
                    "data_type": "string",
                    "semantic_type": "EMAIL",
                    "format": "email",
                    "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
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
        
        from hub.apps.semantic.utils import map_contract_to_semantic
        semantic_resource = map_contract_to_semantic(contract, tenant=self.tenant)
        
        self.assertIsNotNone(semantic_resource)
        # All vocabularies should be mapped
        self.assertGreater(semantic_resource.metadata_json.get('triples_count', 0), 0)

