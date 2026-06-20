"""
Tenant Serializers

DRF serializers for Tenant API.
"""

from rest_framework import serializers

from .models import KYCStatus, Tenant, TenantConfig, TenantStatus
from .validators import (
    validate_compliance_regimes,
    validate_dq_profile,
    validate_rate_limits,
)


class TenantSerializer(serializers.ModelSerializer):
    """Serializer for Tenant model"""

    status = serializers.ChoiceField(choices=TenantStatus.choices, read_only=True)
    kyc_status = serializers.ChoiceField(choices=KYCStatus.choices)

    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "kyc_status",
            "region",
            "plan",
            "deleted_at",
            # Phase 235.3 — surface the lifecycle fields so the SPA
            # can pre-disable the Deactivate button on tenants with
            # an active legal hold OR an already-scheduled hard delete.
            # Without these, the operator first sees a 422 only after
            # clicking the button — surfacing the state up-front turns
            # the deactivate flow from "click-and-toast" into a
            # visible-precondition UX.
            "scheduled_for_deletion_at",
            "legal_hold",
            # Phase 235.4 — surface impersonation opt-in + per-tenant
            # default duration so the SPA can decide locally whether
            # to render the ImpersonationButton on user-detail pages
            # and what value to pre-fill into the max_minutes field
            # of the start dialog.
            "impersonation_allowed",
            "impersonation_default_max_minutes",
            # Feature flags gating optional capabilities per tenant
            # (BaaS, marketplace integrations, ML / ODH).
            "baas_enabled",
            "marketplace_integrations_enabled",
            "ml_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "deleted_at",
            "scheduled_for_deletion_at",
            # ``legal_hold`` is intentionally NOT in read_only_fields —
            # a platform-admin endpoint (out of 235.3 scope; future
            # 235.x or runbook-driven) can PATCH it. For 235.3, the
            # serializer surfaces it as read-only via the existing
            # ModelSerializer + the absence of a write-side write
            # path; only specific endpoints will mutate it.
            "created_at",
            "updated_at",
        ]

    def validate_slug(self, value):
        """Validate slug format"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()


class TenantCreateSerializer(serializers.ModelSerializer):
    """Serializer for tenant creation"""

    slug = serializers.SlugField(max_length=255)

    class Meta:
        model = Tenant
        fields = ["name", "slug", "region"]

    def validate_slug(self, value):
        """Validate and normalize slug"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()

    def create(self, validated_data):
        """Create tenant with default status"""
        tenant = Tenant.objects.create(
            name=validated_data["name"],
            slug=validated_data["slug"],
            region=validated_data.get("region"),
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        return tenant


class TenantOnboardingSerializer(serializers.Serializer):
    """Serializer for self-service tenant onboarding"""

    name = serializers.CharField(max_length=255, help_text="Tenant name")
    slug = serializers.SlugField(max_length=255, help_text="URL-safe tenant identifier")
    plan_slug = serializers.CharField(
        max_length=50, required=False, default="free", help_text="Plan slug (defaults to 'free')"
    )
    first_user = serializers.DictField(
        help_text="First user information", child=serializers.CharField()
    )
    region = serializers.CharField(
        max_length=100, required=False, allow_null=True, help_text="Cloud region (optional)"
    )

    def validate_first_user(self, value):
        """Validate first user data"""
        required_fields = ["email", "password"]
        for field in required_fields:
            if field not in value:
                raise serializers.ValidationError(f"first_user.{field} is required")
        return value

    def validate_slug(self, value):
        """Validate and normalize slug"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()


class TenantUpdateSerializer(serializers.ModelSerializer):
    """Serializer for tenant update"""

    class Meta:
        model = Tenant
        fields = ["name", "slug", "kyc_status", "region"]

    def validate_slug(self, value):
        """Validate and normalize slug"""
        if not value.replace("-", "").replace("_", "").isalnum():
            raise serializers.ValidationError(
                "Slug must contain only lowercase letters, numbers, and hyphens."
            )
        return value.lower()


class TenantSuspendSerializer(serializers.Serializer):
    """Serializer for tenant suspension"""

    reason = serializers.CharField(
        required=False, allow_blank=True, help_text="Optional reason for suspension"
    )


class TenantReactivateSerializer(serializers.Serializer):
    """Serializer for tenant reactivation"""


class RateLimitsSerializer(serializers.Serializer):
    """Serializer for rate limits structure"""

    burst_per_10s = serializers.IntegerField(required=False, min_value=1)
    sustained_per_min = serializers.IntegerField(required=False, min_value=1)
    daily_cap = serializers.IntegerField(required=False, min_value=1)

    def validate(self, data):
        """Validate rate limits structure"""
        # At least one limit must be specified
        if not any(key in data for key in ["burst_per_10s", "sustained_per_min", "daily_cap"]):
            raise serializers.ValidationError(
                "At least one rate limit (burst_per_10s, sustained_per_min, or daily_cap) must be specified"
            )
        return data


class TenantConfigSerializer(serializers.ModelSerializer):
    """Serializer for TenantConfig model"""

    tenant_id = serializers.UUIDField(source="tenant.id", read_only=True)
    rate_limits = serializers.DictField(
        child=RateLimitsSerializer(),
        required=False,
        allow_null=True,
        help_text="Per-endpoint category rate limits",
    )
    # Phase 270.C.4.5 — surface the per-tenant strict-mode flag on
    # the TenantConfig API even though the field lives on the
    # ``Tenant`` model. Read-only here; the update path in
    # ``TenantConfigUpdateSerializer`` writes it via the related
    # Tenant. The frontend's ``TenantSettingsPage`` reads + writes
    # this field through the same ``PATCH /tenants/me/config/``
    # endpoint as every other compliance flag.
    compliance_legal_basis_strict = serializers.BooleanField(
        source="tenant.compliance_legal_basis_strict",
        read_only=True,
    )

    class Meta:
        model = TenantConfig
        fields = [
            "tenant_id",
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "compliance_risk_threshold",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
            "trust_signals_enabled",
            "versioning_enabled",
            "workflows_enabled",
            "compliance_legal_basis_strict",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["tenant_id", "created_at", "updated_at"]

    def validate_default_dq_profile(self, value):
        """Validate DQ profile"""
        if value:
            validate_dq_profile(value)
        return value

    def validate_allowed_compliance_regimes(self, value):
        """Validate allowed compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value

    def validate_default_compliance_regimes(self, value):
        """Validate default compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value

    def validate_rate_limits(self, value):
        """Validate rate limits"""
        if value:
            validate_rate_limits(value)
        return value

    def validate(self, data):
        """Validate cross-field constraints"""
        # Validate default_compliance_regimes is subset of allowed_compliance_regimes
        allowed = data.get("allowed_compliance_regimes") or []
        default = data.get("default_compliance_regimes") or []

        # If updating, get existing values from instance
        if self.instance:
            allowed = data.get(
                "allowed_compliance_regimes", self.instance.allowed_compliance_regimes or []
            )
            default = data.get(
                "default_compliance_regimes", self.instance.default_compliance_regimes or []
            )

        if default and allowed:
            default_set = set(default)
            allowed_set = set(allowed)
            if not default_set.issubset(allowed_set):
                raise serializers.ValidationError(
                    {
                        "default_compliance_regimes": "Default compliance regimes must be a subset of allowed compliance regimes."
                    }
                )

        return data


class TenantConfigUpdateSerializer(serializers.ModelSerializer):
    """Serializer for partial TenantConfig updates"""

    rate_limits = serializers.DictField(
        child=RateLimitsSerializer(),
        required=False,
        allow_null=True,
        help_text="Per-endpoint category rate limits",
    )
    # Phase 270.C.4.5 — write-through to the related ``Tenant``
    # model's ``compliance_legal_basis_strict`` field. Declared as
    # a non-model BooleanField because the value lives on Tenant
    # (not TenantConfig); ``update()`` below routes the value to
    # the right model.
    compliance_legal_basis_strict = serializers.BooleanField(
        required=False,
        allow_null=True,
    )

    class Meta:
        model = TenantConfig
        fields = [
            "default_dq_profile",
            "allowed_compliance_regimes",
            "default_compliance_regimes",
            "compliance_risk_threshold",
            "data_retention_days",
            "rate_limits",
            "max_file_size_bytes",
            "max_job_concurrency",
            "max_queued_jobs",
            "trust_signals_enabled",
            "versioning_enabled",
            "workflows_enabled",
            "compliance_legal_basis_strict",
        ]

    def update(self, instance, validated_data):
        """Phase 270.C.4.5 — handle the ``compliance_legal_basis_strict``
        cross-model write: pop the value out of validated_data, apply
        it to the related Tenant + the TenantConfig fields together
        inside a single ``transaction.atomic()`` so partial writes
        are impossible.

        Phase 270.C.4 audit-fix Gap 1 — the original implementation
        saved the Tenant FIRST then called ``super().update()``
        OUTSIDE any explicit atomic. A failure in ``super().update()``
        (DB blip, constraint violation, validation failure that
        surfaces only at the model layer) would leave the Tenant's
        ``compliance_legal_basis_strict`` flag advanced while the
        TenantConfig fields the user PATCHed remained un-applied —
        a classic half-written state. Wrapping both writes in a
        single atomic transaction makes the PATCH all-or-nothing.
        """
        from django.db import transaction as _tx

        cross_model = validated_data.pop(
            "compliance_legal_basis_strict",
            None,
        )
        with _tx.atomic():
            if cross_model is not None and instance.tenant is not None:
                tenant = instance.tenant
                tenant.compliance_legal_basis_strict = bool(cross_model)
                tenant.save(
                    update_fields=[
                        "compliance_legal_basis_strict",
                        "updated_at",
                    ]
                )
            return super().update(instance, validated_data)

    def validate_default_dq_profile(self, value):
        """Validate DQ profile"""
        if value:
            validate_dq_profile(value)
        return value

    def validate_allowed_compliance_regimes(self, value):
        """Validate allowed compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value

    def validate_default_compliance_regimes(self, value):
        """Validate default compliance regimes"""
        if value:
            validate_compliance_regimes(value)
        return value

    def validate_rate_limits(self, value):
        """Validate rate limits"""
        if value:
            validate_rate_limits(value)
        return value

    def validate(self, data):
        """Validate cross-field constraints"""
        # Get existing values from instance
        allowed = data.get(
            "allowed_compliance_regimes",
            self.instance.allowed_compliance_regimes if self.instance else [],
        )
        default = data.get(
            "default_compliance_regimes",
            self.instance.default_compliance_regimes if self.instance else [],
        )

        if default and allowed:
            default_set = set(default)
            allowed_set = set(allowed)
            if not default_set.issubset(allowed_set):
                raise serializers.ValidationError(
                    {
                        "default_compliance_regimes": "Default compliance regimes must be a subset of allowed compliance regimes."
                    }
                )

        return data


class TenantUsageSerializer(serializers.Serializer):
    """Phase 277.B.106 — serializer for tenant usage summary.

    Usage counts are dynamic (derived from RESOURCE_COUNTERS keys)
    and surfaced as ``{limit_key_prefix}_usage`` fields.
    """

    tenant_id = serializers.UUIDField(read_only=True)
    plan_limits = serializers.DictField(read_only=True)
    usage_percentages = serializers.DictField(read_only=True)
    quota_warnings = serializers.DictField(read_only=True)
    plan_slug = serializers.CharField(read_only=True, allow_null=True)
    plan_tier = serializers.CharField(read_only=True, allow_null=True)
    plan_compliance_pro_pack = serializers.BooleanField(read_only=True)

    def to_representation(self, instance):
        """Include all instance data, including dynamic ``*_usage`` keys
        derived from RESOURCE_COUNTERS (Phase 277.B.106).  DRF Serializer
        only outputs declared fields by default; we pass through any
        extra keys so that callers see ``asset_usage``, ``users_usage``,
        etc. alongside the declared envelope fields.
        """
        ret = super().to_representation(instance)
        if isinstance(instance, dict):
            for key, value in instance.items():
                if key not in ret:
                    ret[key] = value
        return ret
