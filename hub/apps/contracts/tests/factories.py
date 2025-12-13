"""
Test Factories for Contracts

Real factories (not mocks) for creating test contracts with all HubContract sections.
"""
import uuid
from typing import Dict, Any, List, Optional
from django.contrib.auth import get_user_model
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    ValidationStatus,
    OriginalSpecType,
    OriginalFormat
)
from hub.apps.tenants.models import Tenant
from hub.apps.assets.models import Asset

User = get_user_model()


class ContractFactoryEnhanced:
    """
    Enhanced contract factory that creates contracts with all HubContract sections.
    
    This is a real factory (not a mock) that creates actual Contract instances
    with complete hub_contract_json including all sections:
    - owners
    - tags
    - quality rules
    - compliance policy
    - lifecycle policy
    - marketplace policy
    - schema fields with all properties
    """
    
    @staticmethod
    def create_hub_contract_json(
        contract_id: Optional[str] = None,
        name: Optional[str] = None,
        description: Optional[str] = None,
        version: Optional[str] = None,
        owners: Optional[List[Dict[str, str]]] = None,
        tags: Optional[List[str]] = None,
        quality_rules: Optional[List[Dict[str, Any]]] = None,
        compliance_policy: Optional[Dict[str, Any]] = None,
        lifecycle_policy: Optional[Dict[str, Any]] = None,
        marketplace_policy: Optional[Dict[str, Any]] = None,
        schema_fields: Optional[List[Dict[str, Any]]] = None,
        primary_key: Optional[List[str]] = None,
        unique_constraints: Optional[List] = None,
        indexes: Optional[List] = None,
    ) -> Dict[str, Any]:
        """
        Create a complete HubContract JSON with all sections.
        
        Args:
            contract_id: Contract identifier (default: auto-generated)
            name: Contract name (default: "Test Contract")
            description: Contract description
            version: Contract version (default: "1.0.0")
            owners: List of owner dicts with name and email
            tags: List of tags
            quality_rules: List of quality rule dicts
            compliance_policy: Compliance policy dict
            lifecycle_policy: Lifecycle policy dict
            marketplace_policy: Marketplace policy dict
            schema_fields: List of field dicts with all properties
            primary_key: List of primary key field names
            unique_constraints: List of unique constraint definitions
            indexes: List of index definitions
            
        Returns:
            Complete HubContract JSON dict
        """
        if contract_id is None:
            contract_id = f"test-contract-{uuid.uuid4().hex[:8]}"
        if name is None:
            name = "Test Contract"
        if version is None:
            version = "1.0.0"
        if owners is None:
            owners = [
                {"name": "Data Platform Team", "email": "dataplatform@example.com"}
            ]
        if tags is None:
            tags = ["analytics", "sales", "test"]
        if quality_rules is None:
            quality_rules = [
                {
                    "rule_id": "not_null_test_field",
                    "dimension": "completeness",
                    "expression": "test_field IS NOT NULL",
                    "severity": "ERROR",
                    "field": "test_field"
                }
            ]
        if compliance_policy is None:
            compliance_policy = {
                "contains_personal_data": False,
                "personal_data_categories": [],
                "jurisdictions": [],
                "legal_bases": [],
                "retention_policy": None
            }
        if lifecycle_policy is None:
            lifecycle_policy = {
                "data_source": "test.source",
                "refresh_cadence": "DAILY",
                "slas": {
                    "availability": "99.0",
                    "latency_ms_p95": 5000
                }
            }
        if marketplace_policy is None:
            marketplace_policy = {
                "license_summary": "MIT License",
                "intended_use": ["analytics"],
                "restricted_use": []
            }
        if schema_fields is None:
            schema_fields = [
                {
                    "name": "test_field",
                    "data_type": "string",
                    "nullable": False,
                    "description": "Test field",
                    "semantic_type": None,
                    "format": None,
                    "pattern": None,
                    "enum": None,
                    "default": None,
                    "min_length": None,
                    "max_length": None,
                    "minimum": None,
                    "maximum": None,
                    "metadata": {}
                }
            ]
        if primary_key is None:
            primary_key = ["test_field"]
        if unique_constraints is None:
            unique_constraints = []
        if indexes is None:
            indexes = []
        
        return {
            "hub_contract_version": "1.0.0",
            "id": contract_id,
            "info": {
                "name": name,
                "description": description,
                "version": version,
                "owners": owners,
                "tags": tags
            },
            "schema": {
                "fields": schema_fields,
                "primary_key": primary_key,
                "unique_constraints": unique_constraints,
                "indexes": indexes
            },
            "quality": {
                "default_profile_key": "intake_basic",
                "rules": quality_rules
            },
            "privacy_compliance": compliance_policy,
            "lifecycle": lifecycle_policy,
            "marketplace": marketplace_policy
        }
    
    @staticmethod
    def create_contract(
        tenant: Tenant,
        created_by: User,
        asset: Optional[Asset] = None,
        version: int = 1,
        status: ContractStatus = ContractStatus.DRAFT,
        original_spec_type: OriginalSpecType = OriginalSpecType.ODCS,
        original_spec_version: str = "3.0.2",
        original_format: OriginalFormat = OriginalFormat.JSON,
        normalization_status: NormalizationStatus = NormalizationStatus.NORMALIZED_OK,
        validation_status: Optional[ValidationStatus] = None,
        hub_contract_json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Contract:
        """
        Create a Contract instance with complete HubContract JSON.
        
        Args:
            tenant: Tenant instance
            created_by: User who created the contract
            asset: Optional Asset instance
            version: Contract version number
            status: Contract status
            original_spec_type: Original spec type
            original_spec_version: Original spec version
            original_format: Original format
            normalization_status: Normalization status
            validation_status: Validation status
            hub_contract_json: Complete HubContract JSON (if None, uses create_hub_contract_json)
            **kwargs: Additional arguments passed to create_hub_contract_json
            
        Returns:
            Contract instance
        """
        if hub_contract_json is None:
            hub_contract_json = ContractFactoryEnhanced.create_hub_contract_json(**kwargs)
        
        # Create original_raw from hub_contract_json for testing
        import json
        original_raw = json.dumps({
            "id": hub_contract_json.get("id", "test-contract"),
            "info": hub_contract_json.get("info", {}),
            "schema": hub_contract_json.get("schema", {}),
            "quality": hub_contract_json.get("quality", {}),
            "privacy_compliance": hub_contract_json.get("privacy_compliance", {}),
            "lifecycle": hub_contract_json.get("lifecycle", {}),
            "marketplace": hub_contract_json.get("marketplace", {})
        })
        
        return Contract.objects.create(
            tenant=tenant,
            asset=asset,
            version=version,
            status=status,
            original_spec_type=original_spec_type,
            original_spec_version=original_spec_version,
            original_format=original_format,
            original_raw=original_raw,
            hub_contract_version="1.0.0",
            hub_contract_json=hub_contract_json,
            normalization_status=normalization_status,
            normalization_errors=[],
            normalization_warnings=[],
            validation_status=validation_status,
            validation_errors=[],
            validation_warnings=[],
            created_by=created_by
        )
    
    @staticmethod
    def create_contract_with_all_sections(
        tenant: Tenant,
        created_by: User,
        **kwargs
    ) -> Contract:
        """
        Create a contract with all sections populated (owners, tags, quality, compliance, lifecycle, marketplace).
        
        This is a convenience method that creates a contract with comprehensive test data.
        """
        return ContractFactoryEnhanced.create_contract(
            tenant=tenant,
            created_by=created_by,
            hub_contract_json=ContractFactoryEnhanced.create_hub_contract_json(
                owners=[
                    {"name": "Data Platform Team", "email": "dataplatform@example.com"},
                    {"name": "John Doe", "email": "john.doe@example.com"}
                ],
                tags=["analytics", "sales", "orders", "customer-data"],
                quality_rules=[
                    {
                        "rule_id": "not_null_order_id",
                        "dimension": "completeness",
                        "expression": "order_id IS NOT NULL",
                        "severity": "ERROR",
                        "field": "order_id"
                    },
                    {
                        "rule_id": "valid_email_format",
                        "dimension": "validity",
                        "expression": "customer_email LIKE '%@%.%'",
                        "severity": "WARNING",
                        "field": "customer_email"
                    }
                ],
                compliance_policy={
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL", "PHONE"],
                    "jurisdictions": ["GDPR", "LGPD"],
                    "legal_bases": ["CONSENT", "CONTRACT"],
                    "retention_policy": {
                        "period": "P5Y",
                        "notes": "5 years retention after contract end"
                    }
                },
                lifecycle_policy={
                    "data_source": "OLTP.orders",
                    "refresh_cadence": "DAILY",
                    "slas": {
                        "availability": "99.0",
                        "latency_ms_p95": 5000
                    }
                },
                marketplace_policy={
                    "license_summary": "MIT License",
                    "intended_use": ["analytics", "machine_learning"],
                    "restricted_use": ["resale"]
                },
                schema_fields=[
                    {
                        "name": "order_id",
                        "data_type": "string",
                        "nullable": False,
                        "description": "Unique identifier for the order",
                        "semantic_type": "ORDER_ID",
                        "format": None,
                        "pattern": "^ORD-[0-9]{8}$",
                        "enum": None,
                        "default": None,
                        "min_length": 10,
                        "max_length": 20,
                        "minimum": None,
                        "maximum": None,
                        "metadata": {
                            "source_system": "OLTP",
                            "business_key": True
                        }
                    },
                    {
                        "name": "customer_email",
                        "data_type": "string",
                        "nullable": False,
                        "description": "Customer email address",
                        "semantic_type": "EMAIL",
                        "format": "email",
                        "pattern": None,
                        "enum": None,
                        "default": None,
                        "min_length": None,
                        "max_length": 255,
                        "minimum": None,
                        "maximum": None,
                        "metadata": {}
                    }
                ],
                primary_key=["order_id"],
                unique_constraints=[],
                indexes=[["customer_email"]]
            ),
            **kwargs
        )

