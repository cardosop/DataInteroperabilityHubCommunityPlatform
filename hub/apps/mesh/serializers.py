"""
Data Mesh Serializers

DRF serializers for Data Mesh API endpoints.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import (
    ComplianceReport,
    DataMeshDomain,
    DomainStatus,
    MeshComplianceStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)

User = get_user_model()


class DomainSerializer(serializers.ModelSerializer):
    """Serializer for DataMeshDomain model"""

    owner = serializers.UUIDField(source="owner.id", read_only=True, allow_null=True)
    owner_email = serializers.EmailField(source="owner.email", read_only=True, allow_null=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    status = serializers.ChoiceField(choices=DomainStatus.choices)
    boundaries = serializers.JSONField(required=False, allow_null=True)
    capabilities = serializers.JSONField(required=False, allow_null=True)
    resource_quota = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = DataMeshDomain
        fields = [
            "id",
            "name",
            "description",
            "owner",
            "owner_email",
            "tenant",
            "tenant_name",
            "boundaries",
            "capabilities",
            "resource_quota",
            "resource_usage",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "tenant",
            "tenant_name",
            "owner_email",
        ]

    def validate_name(self, value):
        """Validate domain name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Domain name cannot be empty")
        return value.strip()

    def validate_boundaries(self, value):
        """Validate boundaries is a dict"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Boundaries must be a JSON object")
        return value or {}

    def validate_capabilities(self, value):
        """Validate capabilities is a dict"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Capabilities must be a JSON object")
        return value or {}

    def validate_resource_quota(self, value):
        """Validate resource_quota is a dict with non-negative numbers"""
        if value is not None:
            if not isinstance(value, dict):
                raise serializers.ValidationError("Resource quota must be a JSON object")
            for key, val in value.items():
                if not isinstance(val, (int, float)):
                    raise serializers.ValidationError(f"Resource quota '{key}' must be a number")
                if val < 0:
                    raise serializers.ValidationError(f"Resource quota '{key}' cannot be negative")
        return value or {}


class DomainCreateSerializer(serializers.Serializer):
    """Serializer for domain creation"""

    name = serializers.CharField(max_length=255, help_text="Domain name (unique per tenant)")
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, help_text="Domain description"
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True, help_text="Owner user ID")
    boundaries = serializers.DictField(
        required=False, allow_empty=True, allow_null=True, help_text="Domain boundaries as JSON"
    )
    capabilities = serializers.DictField(
        required=False, allow_empty=True, help_text="Domain capabilities as JSON"
    )
    resource_quota = serializers.DictField(
        required=False, allow_empty=True, help_text="Resource quotas as JSON"
    )
    status = serializers.ChoiceField(
        choices=DomainStatus.choices,
        required=False,
        default=DomainStatus.ACTIVE,
        help_text="Domain status",
    )

    def validate_name(self, value):
        """Validate domain name"""
        if not value or not value.strip():
            raise serializers.ValidationError("Domain name cannot be empty")
        return value.strip()

    def validate_resource_quota(self, value):
        """Validate resource_quota values are non-negative numbers"""
        if value:
            for key, val in value.items():
                if not isinstance(val, (int, float)):
                    raise serializers.ValidationError(f"Resource quota '{key}' must be a number")
                if val < 0:
                    raise serializers.ValidationError(f"Resource quota '{key}' cannot be negative")
        return value or {}


class DomainUpdateSerializer(serializers.Serializer):
    """Serializer for domain updates"""

    name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        help_text="Domain name (empty/whitespace rejected by service layer)",
    )
    description = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, help_text="Domain description"
    )
    owner_id = serializers.UUIDField(required=False, allow_null=True, help_text="Owner user ID")
    boundaries = serializers.DictField(
        required=False, allow_empty=True, help_text="Domain boundaries as JSON"
    )
    capabilities = serializers.DictField(
        required=False, allow_empty=True, help_text="Domain capabilities as JSON"
    )
    resource_quota = serializers.DictField(
        required=False, allow_empty=True, help_text="Resource quotas as JSON"
    )
    status = serializers.ChoiceField(
        choices=DomainStatus.choices, required=False, help_text="Domain status"
    )

    def validate_name(self, value):
        """Pass through name; empty/whitespace is rejected by service layer (DataMeshBusinessRules)."""
        if value is not None and isinstance(value, str):
            return value.strip() if value.strip() else value
        return value

    def validate_resource_quota(self, value):
        """Validate resource_quota values are non-negative numbers"""
        if value:
            for key, val in value.items():
                if not isinstance(val, (int, float)):
                    raise serializers.ValidationError(f"Resource quota '{key}' must be a number")
                if val < 0:
                    raise serializers.ValidationError(f"Resource quota '{key}' cannot be negative")
        return value


class TransferOwnershipSerializer(serializers.Serializer):
    """Serializer for ownership transfer"""

    new_owner_id = serializers.UUIDField(
        required=False, allow_null=True, help_text="New owner user ID (null to remove owner)"
    )

    def validate_new_owner_id(self, value):
        """Validate new owner ID"""
        # None is valid (removes owner)
        if value is None:
            return value

        # Validate user exists and belongs to tenant
        # This will be checked in the view/service layer
        return value


class DomainAnalyticsSerializer(serializers.Serializer):
    """Serializer for domain analytics response"""

    domain_id = serializers.UUIDField()
    domain_name = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    # Resource usage statistics
    resource_usage = serializers.DictField()
    resource_quota = serializers.DictField()
    resource_usage_percentages = serializers.DictField()

    # Policy statistics
    total_policies = serializers.IntegerField()
    applied_policies = serializers.IntegerField()
    pending_policies = serializers.IntegerField()

    # Compliance statistics
    compliance_status = serializers.CharField(allow_null=True)
    violation_count = serializers.IntegerField()
    last_compliance_check = serializers.DateTimeField(allow_null=True)

    # Boundary and capability statistics
    boundaries_count = serializers.IntegerField()
    capabilities_count = serializers.IntegerField()

    # Health metrics (if available)
    health_score = serializers.FloatField(allow_null=True)
    health_status = serializers.CharField(allow_null=True)


class PolicyApplicationSerializer(serializers.ModelSerializer):
    """Serializer for PolicyApplication model"""

    policy_id = serializers.UUIDField(source="policy.id", read_only=True, allow_null=True)
    policy_name = serializers.CharField(source="policy.name", read_only=True, allow_null=True)
    applied_by_id = serializers.UUIDField(source="applied_by.id", read_only=True, allow_null=True)
    applied_by_email = serializers.EmailField(
        source="applied_by.email", read_only=True, allow_null=True
    )
    domain_id = serializers.UUIDField(source="domain.id", read_only=True)
    domain_name = serializers.CharField(source="domain.name", read_only=True)
    status = serializers.ChoiceField(choices=PolicyApplicationStatus.choices)

    class Meta:
        model = PolicyApplication
        fields = [
            "id",
            "domain_id",
            "domain_name",
            "policy_id",
            "policy_name",
            "applied_by_id",
            "applied_by_email",
            "overrides",
            "status",
            "applied_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "domain_id",
            "domain_name",
            "policy_id",
            "policy_name",
            "applied_by_id",
            "applied_by_email",
            "status",
            "applied_at",
            "created_at",
            "updated_at",
        ]


class ApplyPolicySerializer(serializers.Serializer):
    """Serializer for applying a policy to a domain"""

    policy_id = serializers.UUIDField(help_text="Policy ID to apply to the domain")
    overrides = serializers.DictField(
        required=False,
        allow_null=True,
        allow_empty=True,
        default=dict,
        help_text="Policy overrides as JSON (conditions, effect, priority, etc.)",
    )

    def validate_overrides(self, value):
        """Validate overrides is a dict"""
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Overrides must be a JSON object")
        return value or {}


class ComplianceReportSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceReport model"""

    domain_id = serializers.UUIDField(source="domain.id", read_only=True)
    domain_name = serializers.CharField(source="domain.name", read_only=True)
    asset_id = serializers.UUIDField(source="asset.id", read_only=True, allow_null=True)
    asset_name = serializers.CharField(source="asset.name", read_only=True, allow_null=True)
    compliance_status = serializers.ChoiceField(choices=MeshComplianceStatus.choices)
    violation_count = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceReport
        fields = [
            "id",
            "domain_id",
            "domain_name",
            "asset_id",
            "asset_name",
            "compliance_status",
            "violations",
            "violation_count",
            "generated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "domain_id",
            "domain_name",
            "asset_id",
            "asset_name",
            "compliance_status",
            "violations",
            "violation_count",
            "generated_at",
            "created_at",
            "updated_at",
        ]

    def get_violation_count(self, obj):
        """Get violation count from violations dict"""
        if obj.violations and isinstance(obj.violations, dict):
            # Violations can be stored as a list in 'items' key or as a dict
            if "items" in obj.violations and isinstance(obj.violations["items"], list):
                return len(obj.violations["items"])
            # If violations is a dict with keys, count them
            if isinstance(obj.violations, dict):
                return len([k for k, v in obj.violations.items() if v])
        return 0


class CheckComplianceSerializer(serializers.Serializer):
    """Serializer for compliance check request"""

    asset_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional asset ID for asset-specific compliance check",
    )


class HealthMetricsSerializer(serializers.Serializer):
    """Serializer for domain health metrics"""

    health_score = serializers.IntegerField(min_value=0, max_value=100, help_text="Health score (0-100)")
    policy_count = serializers.IntegerField(help_text="Number of applied policies")
    compliance_status = serializers.ChoiceField(
        choices=MeshComplianceStatus.choices, help_text="Compliance status"
    )
    violation_count = serializers.IntegerField(help_text="Number of violations")
    is_active = serializers.BooleanField(help_text="Whether domain is active")


class TopologyNodeSerializer(serializers.Serializer):
    """Serializer for topology node (domain)"""

    id = serializers.UUIDField(help_text="Domain ID")
    name = serializers.CharField(help_text="Domain name")
    description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, help_text="Domain description"
    )
    status = serializers.CharField(help_text="Domain status")
    owner_id = serializers.UUIDField(required=False, allow_null=True, help_text="Owner user ID")
    created_at = serializers.DateTimeField(
        required=False, allow_null=True, help_text="Domain creation timestamp"
    )
    health_metrics = HealthMetricsSerializer(
        required=False, allow_null=True, help_text="Health metrics (if include_health_metrics=true)"
    )


class TopologyEdgeSerializer(serializers.Serializer):
    """Serializer for topology edge (relationship)"""

    source = serializers.UUIDField(help_text="Source domain ID")
    target = serializers.UUIDField(help_text="Target domain ID")
    type = serializers.CharField(help_text="Relationship type (e.g., SHARED_POLICY)")
    weight = serializers.IntegerField(help_text="Relationship weight/strength")


class TopologyMetadataSerializer(serializers.Serializer):
    """Serializer for topology metadata"""

    tenant_id = serializers.UUIDField(help_text="Tenant ID")
    domain_count = serializers.IntegerField(help_text="Number of domains")
    relationship_count = serializers.IntegerField(help_text="Number of relationships")
    generated_at = serializers.DateTimeField(help_text="Topology generation timestamp")


class TopologySummarySerializer(serializers.Serializer):
    """Serializer for topology summary statistics"""

    total_domains = serializers.IntegerField(help_text="Total number of domains")
    active_domains = serializers.IntegerField(help_text="Number of active domains")
    total_relationships = serializers.IntegerField(help_text="Total number of relationships")
    average_health_score = serializers.FloatField(
        allow_null=True, help_text="Average health score across all domains"
    )


class TopologySerializer(serializers.Serializer):
    """Serializer for full mesh topology response"""

    nodes = TopologyNodeSerializer(many=True, help_text="List of domain nodes")
    edges = TopologyEdgeSerializer(many=True, help_text="List of domain relationships")
    metadata = TopologyMetadataSerializer(help_text="Topology metadata")
    summary = TopologySummarySerializer(help_text="Summary statistics")


class DomainTopologySerializer(serializers.Serializer):
    """Serializer for single domain topology view"""

    domain = TopologyNodeSerializer(help_text="Domain node")
    relationships = TopologyEdgeSerializer(many=True, help_text="Relationships for this domain")
    health_metrics = HealthMetricsSerializer(help_text="Domain health metrics")


class MeshHealthSerializer(serializers.Serializer):
    """Serializer for mesh health response"""

    overall_health_score = serializers.FloatField(
        allow_null=True, help_text="Overall mesh health score (0-100)"
    )
    total_domains = serializers.IntegerField(help_text="Total number of domains")
    active_domains = serializers.IntegerField(help_text="Number of active domains")
    compliant_domains = serializers.IntegerField(help_text="Number of compliant domains")
    non_compliant_domains = serializers.IntegerField(help_text="Number of non-compliant domains")
    domains_with_violations = serializers.IntegerField(
        help_text="Number of domains with violations"
    )
    domain_health = serializers.ListField(
        child=serializers.DictField(), help_text="Health metrics per domain"
    )


class DomainRelationshipSerializer(serializers.Serializer):
    """Serializer for domain relationships response"""

    relationships = TopologyEdgeSerializer(many=True, help_text="List of domain relationships")
    total_count = serializers.IntegerField(help_text="Total number of relationships")
    relationship_types = serializers.DictField(help_text="Count of relationships by type")
