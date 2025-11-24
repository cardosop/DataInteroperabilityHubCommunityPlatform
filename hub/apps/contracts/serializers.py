"""
Contract Serializers
"""
from rest_framework import serializers
from .models import Contract, ContractStatus, OriginalSpecType, OriginalFormat


class ContractSerializer(serializers.ModelSerializer):
    """Serializer for Contract model"""
    
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
            'updated_at'
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
            'updated_at'
        ]


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


class ContractUpdateSerializer(serializers.Serializer):
    """Serializer for contract update"""
    original_raw = serializers.CharField(required=False)
    original_format = serializers.ChoiceField(choices=OriginalFormat.choices, required=False)
    status = serializers.ChoiceField(choices=ContractStatus.choices, required=False)

