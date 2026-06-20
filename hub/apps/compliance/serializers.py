"""
Compliance Serializers
"""

from rest_framework import serializers

from .models import ComplianceRun


class ComplianceRunSerializer(serializers.ModelSerializer):
    """Serializer for ComplianceRun model — exposes all v2 output fields."""

    # Computed fields sourced from regulation_mapping_json (19.10.3)
    estimated_population_ratio = serializers.SerializerMethodField()
    schema_version = serializers.SerializerMethodField()
    regulation_summaries = serializers.SerializerMethodField()

    class Meta:
        model = ComplianceRun
        fields = [
            "id",
            "tenant",
            "asset",
            "dataset",
            "file",
            "job",
            "regulations",
            "status",
            "overall_status",
            "risk_level",
            "allowed_to_store",
            "detected_categories_json",
            "column_findings_json",
            "regulation_mapping_json",
            # Phase 213.G.2 — surface metadata_json so the POLL_TIMEOUT
            # path (which writes metadata_json["error_code"]) is visible
            # to API consumers, not just to backend logs.
            "metadata_json",
            # v2 fields (19.10.1)
            "cross_border_alert",
            "localisation_alert",
            "legal_basis_violations",
            # v2 computed fields (19.10.3)
            "estimated_population_ratio",
            "schema_version",
            "regulation_summaries",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "job",
            "status",
            "overall_status",
            "risk_level",
            "allowed_to_store",
            "detected_categories_json",
            "column_findings_json",
            "regulation_mapping_json",
            "metadata_json",
            "cross_border_alert",
            "localisation_alert",
            "legal_basis_violations",
            "estimated_population_ratio",
            "schema_version",
            "regulation_summaries",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]

    def get_estimated_population_ratio(self, obj):
        """Read from regulation_mapping_json.metadata."""
        mapping = obj.regulation_mapping_json or {}
        return mapping.get("metadata", {}).get("estimated_population_ratio")

    def get_schema_version(self, obj):
        """Read schema_version stored in regulation_mapping_json."""
        mapping = obj.regulation_mapping_json or {}
        return mapping.get("schema_version")

    def get_regulation_summaries(self, obj):
        """Read from regulation_mapping_json.regulation_summary."""
        mapping = obj.regulation_mapping_json or {}
        return mapping.get("regulation_summary")


class ComplianceRunCreateSerializer(serializers.Serializer):
    """Serializer for creating a compliance run."""

    asset_id = serializers.UUIDField(required=False, help_text="Asset ID (optional)")
    dataset_id = serializers.UUIDField(required=False, help_text="Dataset ID (optional)")
    file_id = serializers.UUIDField(
        required=False,
        help_text="File ID (optional, scan-only)",
    )
    scan_mode = serializers.ChoiceField(
        choices=["internal", "external"],
        default="internal",
        help_text=("Scan mode: 'internal' for stored data, 'external' for scan-only"),
    )
    applicable_regulations = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        help_text=(
            "List of regulations to check (e.g., ['GDPR', 'HIPAA']). "
            "Defaults to tenant/platform regimes when omitted."
        ),
    )
    # v2 write-only fields (19.10.2)
    legal_basis = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        help_text=(
            "Legal basis for processing (e.g. 'CONSENT', 'CONTRACT'). "
            "Forwarded to compliance service for legal-basis checks."
        ),
    )
    destination_jurisdiction = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        write_only=True,
        help_text=("Destination jurisdiction for cross-border transfer checks (e.g. 'US', 'CN')."),
    )

    def validate(self, data):
        """Resource presence validated by ComplianceBusinessRules in service."""
        return data
