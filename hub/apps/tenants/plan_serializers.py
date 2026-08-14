"""Admin serializers for the CORE TenantPlan model (Phase 313.1).

TenantPlanAdminSerializer moved here from the paid billing app: it
serializes a core model and imports nothing paid, so core views
(tenants.views plan endpoints) can import it in core-only mode.
billing.serializers keeps a compat re-export.
"""

from rest_framework import serializers

from .models import TenantPlan

class TenantPlanAdminSerializer(serializers.ModelSerializer):
    """Serializer for admin CRUD on TenantPlan.

    Validates limits_json against KNOWN_LIMIT_KEYS via the model's clean().
    """

    class Meta:
        model = TenantPlan
        fields = [
            "id",
            "name",
            "slug",
            "tier",
            "category",
            "order",
            "limits_json",
            "is_active",
            "price_amount_cents",
            "price_currency",
            "billing_interval",
            "stripe_product_id",
            "stripe_price_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_limits_json(self, value):
        """Validate limits_json keys against KNOWN_LIMIT_KEYS."""
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError("Must be a JSON object (dict).")
        known = TenantPlan.KNOWN_LIMIT_KEYS
        for key, val in value.items():
            if key not in known:
                raise serializers.ValidationError(
                    f"Unknown limit key: '{key}'. Valid: {sorted(known)}"
                )
            if val is not None:
                if not isinstance(val, int):
                    raise serializers.ValidationError(
                        f"Limit '{key}' must be int or null, got {type(val).__name__}."
                    )
                if val < 0:
                    raise serializers.ValidationError(
                        f"Limit '{key}' must be non-negative, got {val}."
                    )
        return value


