"""
Contract Serializers

Enhanced serializers with computed fields and nested serializers for all HubContract sections (GAP-9.2.1).
"""
from rest_framework import serializers
from typing import Dict, Any, List, Optional
from drf_spectacular.utils import extend_schema_serializer, extend_schema_field, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from .models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, SecurityAuditLog
from .ref_resolver import ExternalRefHandling


class OwnerSerializer(serializers.Serializer):
    """
    Serializer for contract owner (GAP-9.2.1).

    Owners are individuals or teams responsible for the contract.
    """
    name = serializers.CharField(
        help_text="Owner name (e.g., 'Data Platform Team', 'John Doe')"
    )
    email = serializers.EmailField(
        required=False,
        allow_null=True,
        help_text="Owner email address (optional)"
    )


class QualityRuleSerializer(serializers.Serializer):
    """
    Serializer for quality rule (GAP-9.2.1).

    Quality rules define data quality checks and expectations.
    """
    rule_id = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Unique identifier for the rule (e.g., 'not_null_order_id')"
    )
    dimension = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Quality dimension (e.g., 'completeness', 'validity', 'consistency', 'accuracy', 'timeliness')"
    )
    expression = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Quality check expression (e.g., 'order_id IS NOT NULL', 'price > 0')"
    )
    severity = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Rule severity (e.g., 'ERROR', 'WARNING', 'INFO')"
    )
    field = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Field name this rule applies to (optional, for field-specific rules)"
    )


class CompliancePolicySerializer(serializers.Serializer):
    """
    Serializer for compliance policy (GAP-9.2.1).

    Compliance policy defines data privacy and regulatory compliance requirements.
    """
    contains_personal_data = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=False,
        help_text="Whether the contract contains personal data (PII)"
    )
    personal_data_categories = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Categories of personal data (e.g., 'EMAIL', 'PHONE', 'ADDRESS', 'HEALTH_DATA')"
    )
    jurisdictions = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Applicable jurisdictions (e.g., 'GDPR', 'LGPD', 'CCPA', 'HIPAA')"
    )
    legal_bases = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Legal bases for processing (e.g., 'CONSENT', 'CONTRACT', 'LEGAL_OBLIGATION')"
    )
    retention_policy = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Data retention policy (e.g., {'period': 'P5Y', 'notes': '5 years retention'})"
    )


class LifecyclePolicySerializer(serializers.Serializer):
    """
    Serializer for lifecycle policy (GAP-9.2.1).

    Lifecycle policy defines data refresh cadence and service level agreements.
    """
    data_source = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Data source identifier (e.g., 'OLTP.orders', 'data-warehouse.customers')"
    )
    refresh_cadence = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Refresh cadence (e.g., 'DAILY', 'HOURLY', 'REAL_TIME', 'WEEKLY', 'MONTHLY')"
    )
    slas = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Service level agreements (e.g., {'availability': '99.0', 'latency_ms_p95': 5000})"
    )


class MarketplacePolicySerializer(serializers.Serializer):
    """
    Serializer for marketplace policy (GAP-9.2.1).

    Marketplace policy defines how the data can be shared and used in the marketplace.
    """
    license_summary = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="License summary (e.g., 'MIT License', 'Commercial Use Allowed')"
    )
    intended_use = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Intended use cases (e.g., ['analytics', 'machine_learning', 'reporting'])"
    )
    restricted_use = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="Restricted use cases (e.g., ['resale', 'competitive_analysis'])"
    )


class FieldPropertySerializer(serializers.Serializer):
    """
    Serializer for field properties (GAP-9.2.1).

    Field properties define the structure, constraints, and semantics of data fields.
    """
    name = serializers.CharField(
        help_text="Field name (e.g., 'order_id', 'customer_email')"
    )
    data_type = serializers.CharField(
        help_text="Data type (e.g., 'string', 'integer', 'number', 'boolean', 'date', 'datetime')"
    )
    nullable = serializers.BooleanField(
        help_text="Whether the field can be null"
    )
    description = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Field description"
    )
    semantic_type = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Semantic type (e.g., 'EMAIL', 'PHONE', 'ORDER_ID', 'CURRENCY', 'DATE')"
    )
    format = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Format specification (e.g., 'email', 'uri', 'date-time', 'uuid')"
    )
    pattern = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Regex pattern for validation (e.g., '^[A-Z0-9]{8}$')"
    )
    enum = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        help_text="Allowed enum values (e.g., ['ACTIVE', 'INACTIVE', 'PENDING'])"
    )
    default = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Default value"
    )
    min_length = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Minimum string length"
    )
    max_length = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Maximum string length"
    )
    minimum = serializers.FloatField(
        required=False,
        allow_null=True,
        help_text="Minimum numeric value"
    )
    maximum = serializers.FloatField(
        required=False,
        allow_null=True,
        help_text="Maximum numeric value"
    )
    metadata = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Additional metadata (e.g., {'source_system': 'OLTP', 'business_key': true})"
    )
    is_primary_key = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether this field is part of the primary key"
    )
    is_unique = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether this field has a unique constraint"
    )
    is_indexed = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether this field is indexed"
    )


@extend_schema_serializer(
    examples=[
        OpenApiExample(
            'Complete Contract Example',
            value={
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant": "123e4567-e89b-12d3-a456-426614174001",
                "asset": "123e4567-e89b-12d3-a456-426614174002",
                "version": 1,
                "status": "DRAFT",
                "original_spec_type": "ODCS",
                "original_spec_version": "3.0.2",
                "original_format": "JSON",
                "hub_contract_version": "1.0.0",
                "normalization_status": "NORMALIZED_OK",
                "validation_status": "VALID",
                "owners": [
                    {"name": "Data Platform Team", "email": "dataplatform@example.com"}
                ],
                "tags": ["analytics", "sales", "orders"],
                "quality_rules": [
                    {
                        "rule_id": "not_null_order_id",
                        "dimension": "completeness",
                        "expression": "order_id IS NOT NULL",
                        "severity": "ERROR",
                        "field": "order_id"
                    }
                ],
                "compliance_policy": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL", "PHONE"],
                    "jurisdictions": ["GDPR", "LGPD"],
                    "legal_bases": ["CONSENT", "CONTRACT"],
                    "retention_policy": {"period": "P5Y", "notes": "5 years retention"}
                },
                "lifecycle_policy": {
                    "data_source": "OLTP.orders",
                    "refresh_cadence": "DAILY",
                    "slas": {"availability": "99.0", "latency_ms_p95": 5000}
                },
                "marketplace_policy": {
                    "license_summary": "MIT License",
                    "intended_use": ["analytics", "machine_learning"],
                    "restricted_use": ["resale"]
                },
                "schema_fields": [
                    {
                        "name": "order_id",
                        "data_type": "string",
                        "nullable": False,
                        "description": "Unique identifier for the order",
                        "semantic_type": "ORDER_ID",
                        "pattern": "^ORD-[0-9]{8}$",
                        "is_primary_key": True,
                        "is_unique": True,
                        "is_indexed": True
                    }
                ]
            },
            request_only=False,
            response_only=True
        )
    ]
)
class ContractSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer for Contract model with computed fields (GAP-9.2.1).

    **Computed Fields:**
    All computed fields are extracted from `hub_contract_json`:
    - `owners`: From `info.owners`
    - `tags`: From `info.tags`
    - `quality_rules`: From `quality.rules`
    - `compliance_policy`: From `privacy_compliance`
    - `lifecycle_policy`: From `lifecycle`
    - `marketplace_policy`: From `marketplace`
    - `schema_fields`: From `schema.fields` with constraint flags (is_primary_key, is_unique, is_indexed)
    """

    # Computed fields from hub_contract_json (GAP-9.2.1)
    owners = serializers.SerializerMethodField(
        help_text="Array of contract owners (extracted from info.owners)"
    )
    tags = serializers.SerializerMethodField(
        help_text="Array of tags (extracted from info.tags)"
    )
    quality_rules = serializers.SerializerMethodField(
        help_text="Array of quality rules (extracted from quality.rules)"
    )
    compliance_policy = serializers.SerializerMethodField(
        help_text="Compliance policy (extracted from privacy_compliance)"
    )
    lifecycle_policy = serializers.SerializerMethodField(
        help_text="Lifecycle policy (extracted from lifecycle)"
    )
    marketplace_policy = serializers.SerializerMethodField(
        help_text="Marketplace policy (extracted from marketplace)"
    )
    schema_fields = serializers.SerializerMethodField(
        help_text="Array of schema fields with all properties and constraint flags"
    )
    contact = serializers.SerializerMethodField(
        help_text="Support/contact channels extracted from contact"
    )
    support = serializers.SerializerMethodField(
        help_text="Support channels extracted from support"
    )
    servers = serializers.SerializerMethodField(
        help_text="Server endpoints extracted from servers"
    )
    servicelevels = serializers.SerializerMethodField(
        help_text="Service level objectives extracted from servicelevels"
    )
    terms = serializers.SerializerMethodField(
        help_text="Terms of use extracted from terms"
    )
    definitions = serializers.SerializerMethodField(
        help_text="Definitions extracted from definitions"
    )
    models = serializers.SerializerMethodField(
        help_text="Models extracted from models"
    )
    roles = serializers.SerializerMethodField(
        help_text="Access roles extracted from roles"
    )
    team = serializers.SerializerMethodField(
        help_text="Team memberships extracted from team"
    )
    pricing = serializers.SerializerMethodField(
        help_text="Pricing information extracted from price/pricing"
    )
    lineage = serializers.SerializerMethodField(
        help_text="Lineage extracted from transformSourceObjects/transformLogic"
    )
    quality_type = serializers.SerializerMethodField(
        help_text="Quality framework type extracted from quality.type"
    )
    quality_specification = serializers.SerializerMethodField(
        help_text="Quality specification extracted from quality.specification"
    )

    class Meta:
        model = Contract
        fields = [
            'id',
            'tenant',
            'asset',
            'version',
            'status',
            'original_spec_type',
            'original_spec_version',
            'original_format',
            'original_raw',
            'hub_contract_version',
            'hub_contract_json',
            'normalization_status',
            'normalization_errors',
            'normalization_warnings',
            'validation_status',
            'validation_errors',
            'validation_warnings',
            'cli_version',
            'last_validated_at',
            'created_by',
            'created_at',
            'updated_at',
            # Computed fields (GAP-9.2.1)
            'owners',
            'tags',
            'quality_rules',
            'compliance_policy',
            'lifecycle_policy',
            'marketplace_policy',
            'schema_fields',
            'contact',
            'support',
            'servers',
            'servicelevels',
            'terms',
            'definitions',
            'models',
            'roles',
            'team',
            'pricing',
            'lineage',
            'quality_type',
            'quality_specification'
        ]
        read_only_fields = [
            'id',
            'tenant',
            'version',
            'hub_contract_version',
            'hub_contract_json',
            'normalization_status',
            'normalization_errors',
            'normalization_warnings',
            'validation_status',
            'validation_errors',
            'validation_warnings',
            'cli_version',
            'last_validated_at',
            'created_by',
            'created_at',
            'updated_at',
            # Computed fields are read-only
            'owners',
            'tags',
            'quality_rules',
            'compliance_policy',
            'lifecycle_policy',
            'marketplace_policy',
            'schema_fields',
            'contact',
            'support',
            'servers',
            'servicelevels',
            'terms',
            'definitions',
            'models',
            'roles',
            'team',
            'pricing',
            'lineage',
            'quality_type',
            'quality_specification'
        ]

    def get_owners(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract owners from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        info = hub_contract.get('info', {})
        owners = info.get('owners', [])
        if not owners:
            return []
        result = []
        for owner in owners:
            try:
                # OwnerSerializer requires 'name' field, handle missing gracefully
                if isinstance(owner, dict) and owner.get('name'):
                    result.append(OwnerSerializer(owner).data)
                elif isinstance(owner, dict):
                    # If owner dict doesn't have name, create minimal representation
                    result.append({'name': owner.get('name', 'Unknown'), 'email': owner.get('email')})
                else:
                    # If owner is not a dict, skip it
                    continue
            except Exception as e:
                # Log but don't fail serialization if individual owner fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to serialize owner {owner}: {e}")
                # Add minimal representation
                if isinstance(owner, dict):
                    result.append({'name': owner.get('name', 'Unknown'), 'email': owner.get('email')})
        return result

    def get_tags(self, obj: Contract) -> List[str]:
        """Extract tags from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        info = hub_contract.get('info', {})
        return info.get('tags', [])

    def get_quality_rules(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract quality rules from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        quality = hub_contract.get('quality', {})
        rules = quality.get('rules', [])
        return [QualityRuleSerializer(rule).data for rule in rules] if rules else []

    def get_compliance_policy(self, obj: Contract) -> Optional[Dict[str, Any]]:
        """Extract compliance policy from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        compliance = hub_contract.get('privacy_compliance', {})
        if not compliance:
            return None
        # Ensure contains_personal_data has a default if missing
        if 'contains_personal_data' not in compliance:
            compliance = {**compliance, 'contains_personal_data': False}
        try:
            return CompliancePolicySerializer(compliance).data
        except Exception as e:
            # If serialization fails, return None to prevent breaking the contract view
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to serialize compliance policy: {e}", exc_info=True)
            return None

    def get_lifecycle_policy(self, obj: Contract) -> Optional[Dict[str, Any]]:
        """Extract lifecycle policy from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        lifecycle = hub_contract.get('lifecycle', {})
        if not lifecycle:
            return None
        return LifecyclePolicySerializer(lifecycle).data

    def get_marketplace_policy(self, obj: Contract) -> Optional[Dict[str, Any]]:
        """Extract marketplace policy from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        marketplace = hub_contract.get('marketplace', {})
        if not marketplace:
            return None
        return MarketplacePolicySerializer(marketplace).data

    def get_schema_fields(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract schema fields with all properties from hub_contract_json (GAP-9.2.1)"""
        hub_contract = obj.hub_contract_json or {}
        schema = hub_contract.get('schema', {})
        fields = schema.get('fields', [])
        primary_key = schema.get('primary_key', [])
        unique_constraints = schema.get('unique_constraints', [])
        indexes = schema.get('indexes', [])

        # Build set of primary key fields
        primary_key_set = set(primary_key)

        # Build set of unique constraint fields
        unique_fields_set = set()
        for constraint in unique_constraints:
            if isinstance(constraint, list):
                unique_fields_set.update(constraint)
            elif isinstance(constraint, dict) and 'fields' in constraint:
                unique_fields_set.update(constraint['fields'])

        # Build set of indexed fields
        indexed_fields_set = set()
        for index in indexes:
            if isinstance(index, list):
                indexed_fields_set.update(index)
            elif isinstance(index, dict) and 'fields' in index:
                indexed_fields_set.update(index['fields'])

        # Serialize fields with enhanced properties
        serialized_fields = []
        for field in fields:
            field_data = FieldPropertySerializer(field).data
            # Add constraint flags
            field_name = field.get('name', '')
            field_data['is_primary_key'] = field_name in primary_key_set
            field_data['is_unique'] = field_name in unique_fields_set
            field_data['is_indexed'] = field_name in indexed_fields_set
            serialized_fields.append(field_data)

        return serialized_fields

    def get_contact(self, obj: Contract) -> List[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        contact = hub_contract.get('contact', [])
        return contact if isinstance(contact, list) else []

    def get_servers(self, obj: Contract) -> List[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        servers = hub_contract.get('servers', [])
        return servers if isinstance(servers, list) else []

    def get_servicelevels(self, obj: Contract) -> List[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        servicelevels = hub_contract.get('servicelevels', [])
        return servicelevels if isinstance(servicelevels, list) else []

    def get_terms(self, obj: Contract) -> Optional[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        terms = hub_contract.get('terms')
        return terms if isinstance(terms, dict) else None

    def get_roles(self, obj: Contract) -> List[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        roles = hub_contract.get('roles', [])
        return roles if isinstance(roles, list) else []

    def get_team(self, obj: Contract) -> List[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        team = hub_contract.get('team', [])
        return team if isinstance(team, list) else []

    def get_pricing(self, obj: Contract) -> Optional[Dict[str, Any]]:
        hub_contract = obj.hub_contract_json or {}
        pricing = hub_contract.get('pricing') or hub_contract.get('price')
        return pricing if isinstance(pricing, dict) else None

    def get_lineage(self, obj: Contract) -> Dict[str, Any]:
        """Extract multi-level lineage from hub_contract_json."""
        hub_contract = obj.hub_contract_json or {}
        lineage = hub_contract.get('lineage', {})
        return lineage if isinstance(lineage, dict) else {}

    def get_quality_type(self, obj: Contract) -> Optional[str]:
        hub_contract = obj.hub_contract_json or {}
        quality = hub_contract.get('quality', {})
        return quality.get('type')

    def get_quality_specification(self, obj: Contract) -> Optional[str]:
        hub_contract = obj.hub_contract_json or {}
        quality = hub_contract.get('quality', {})
        return quality.get('specification')

    def get_support(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract support channels from hub_contract_json."""
        hub_contract = obj.hub_contract_json or {}
        support = hub_contract.get('support', [])
        return support if isinstance(support, list) else []

    def get_definitions(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract definitions from hub_contract_json."""
        hub_contract = obj.hub_contract_json or {}
        definitions = hub_contract.get('definitions', [])
        return definitions if isinstance(definitions, list) else []

    def get_models(self, obj: Contract) -> List[Dict[str, Any]]:
        """Extract models from hub_contract_json."""
        hub_contract = obj.hub_contract_json or {}
        models = hub_contract.get('models', [])
        return models if isinstance(models, list) else []


class ContractCreateSerializer(serializers.Serializer):
    """Serializer for contract creation"""
    asset_id = serializers.UUIDField(required=False, allow_null=True)
    original_raw = serializers.CharField(help_text="Original contract content (JSON or YAML)")
    original_format = serializers.ChoiceField(choices=OriginalFormat.choices)
    original_spec_type = serializers.ChoiceField(
        choices=OriginalSpecType.choices,
        required=False,
        help_text="Optional: will be auto-detected if not provided"
    )
    disable_external_refs = serializers.BooleanField(
        required=False,
        default=False,
        help_text="If True, external $ref references will be disabled (raises error if found). "
                  "If False, external refs will be resolved normally."
    )
    remove_external_refs = serializers.BooleanField(
        required=False,
        default=False,
        help_text="If True, external $ref references will be removed from the document. "
                  "If False, external refs will be resolved and replaced with their content."
    )


class ContractUpdateSerializer(serializers.Serializer):
    """Serializer for contract update"""
    original_raw = serializers.CharField(required=False)
    original_format = serializers.ChoiceField(choices=OriginalFormat.choices, required=False)
    status = serializers.ChoiceField(choices=ContractStatus.choices, required=False)
    remove_external_refs = serializers.BooleanField(
        required=False,
        default=False,
        help_text="If True, external $ref references will be removed from the document. "
                  "If False, external refs will be resolved and replaced with their content."
    )


class ProductCreateSerializer(serializers.Serializer):
    """Serializer for Product-First creation (ODPS)"""
    original_raw = serializers.CharField(
        help_text="ODPS document content (JSON or YAML)"
    )
    original_format = serializers.ChoiceField(
        choices=OriginalFormat.choices,
        help_text="ODPS document format: JSON or YAML"
    )
    resolve_external_refs = serializers.BooleanField(
        required=False,
        default=True,
        help_text="If True, external $ref references will be resolved. "
                  "If False, external refs will be disabled (raises error if found)."
    )
    asset_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional asset ID to link contracts to"
    )


class SecurityAuditLogSerializer(serializers.ModelSerializer):
    """Serializer for SecurityAuditLog model."""

    tenant_id = serializers.UUIDField(source='tenant.id', read_only=True, allow_null=True)
    tenant_name = serializers.CharField(source='tenant.name', read_only=True, allow_null=True)
    user_id = serializers.UUIDField(source='user.id', read_only=True, allow_null=True)
    user_email = serializers.CharField(source='user.email', read_only=True, allow_null=True)
    contract_id = serializers.UUIDField(source='contract.id', read_only=True, allow_null=True)

    class Meta:
        model = SecurityAuditLog
        fields = [
            'id',
            'event_type',
            'timestamp',
            'severity',
            'ref_type',
            'ref_path',
            'resolved_path',
            'rate_limit_level',
            'cache_operation',
            'cache_key',
            'eviction_reason',
            'violation_type',
            'attempted_path',
            'attempted_url',
            'description',
            'metadata_json',
            'request_id',
            'ip_address',
            'user_agent',
            'tenant_id',
            'tenant_name',
            'user_id',
            'user_email',
            'contract_id',
        ]
        read_only_fields = fields


class ODPSLinkSerializer(serializers.Serializer):
    """Serializer for ODPS linking request"""
    odps_contract_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Existing ODPS contract ID to link (mutually exclusive with original_raw)"
    )
    original_raw = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="ODPS document content (JSON or YAML) - mutually exclusive with odps_contract_id"
    )
    original_format = serializers.ChoiceField(
        choices=OriginalFormat.choices,
        required=False,
        allow_null=True,
        help_text="ODPS document format: JSON or YAML (required if original_raw is provided)"
    )
    resolve_external_refs = serializers.BooleanField(
        required=False,
        default=True,
        help_text="If True, external $ref references will be resolved. "
                  "If False, external refs will be disabled (raises error if found). "
                  "Only used if original_raw is provided."
    )

    def validate(self, attrs):
        """Validate that either odps_contract_id or original_raw is provided, but not both"""
        odps_contract_id = attrs.get("odps_contract_id")
        original_raw = attrs.get("original_raw")
        original_format = attrs.get("original_format")

        if not odps_contract_id and not original_raw:
            raise serializers.ValidationError(
                "Either 'odps_contract_id' or 'original_raw' must be provided"
            )

        if odps_contract_id and original_raw:
            raise serializers.ValidationError(
                "Cannot provide both 'odps_contract_id' and 'original_raw'. "
                "Provide either an existing ODPS contract ID or a new ODPS document."
            )

        if original_raw and not original_format:
            raise serializers.ValidationError(
                "'original_format' is required when 'original_raw' is provided"
            )

        return attrs


class SecurityIncidentSerializer(serializers.ModelSerializer):
    """Serializer for SecurityIncident model"""
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    resolved_by_email = serializers.CharField(source='resolved_by.email', read_only=True)

    class Meta:
        from .models import SecurityIncident
        model = SecurityIncident
        fields = [
            'id',
            'title',
            'description',
            'severity',
            'status',
            'event_type',
            'violation_count',
            'first_detected_at',
            'last_updated_at',
            'resolved_at',
            'resolution_notes',
            'tenant',
            'tenant_name',
            'user',
            'user_email',
            'contract',
            'resolved_by',
            'resolved_by_email',
            'metadata_json',
        ]
        read_only_fields = [
            'id',
            'first_detected_at',
            'last_updated_at',
        ]


class SecurityIncidentResolveSerializer(serializers.Serializer):
    """Serializer for resolving security incidents"""
    resolution_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Notes about how the incident was resolved"
    )
