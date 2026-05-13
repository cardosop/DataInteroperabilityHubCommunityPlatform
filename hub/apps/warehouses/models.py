"""
Phase 275.A — Warehouse Connection models.

``WarehouseConnection`` stores per-tenant, per-warehouse credentials
encrypted via the KMS+Fernet chain (reused from integrations/encryption.py).
``WarehouseConnectionACL`` provides finer-grained-than-TENANT_ADMIN
access control for connection operations.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class WarehouseType(models.TextChoices):
    """Supported data warehouse types."""
    SNOWFLAKE = "SNOWFLAKE", "Snowflake"
    BIGQUERY = "BIGQUERY", "BigQuery"
    DATABRICKS = "DATABRICKS", "Databricks"
    ATHENA = "ATHENA", "Athena"


class WarehouseConnection(models.Model):
    """Phase 275.A.1 — per-tenant warehouse connection with encrypted credentials.

    Credential fields are stored as ``{"_encrypted": "<ciphertext>"}``
    in the ``config`` JSONField, matching the MarketplaceConnection
    pattern from ``hub/apps/integrations/encryption.py``.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="warehouse_connections",
        help_text="Tenant this connection belongs to",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable connection name",
    )
    warehouse_type = models.CharField(
        max_length=20,
        choices=WarehouseType.choices,
        help_text="Target warehouse type",
    )
    config = models.JSONField(
        default=dict,
        help_text="Encrypted connection config (host, credentials, etc.)",
    )
    region = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Warehouse region (validated against tenant compliance regime)",
    )
    private_endpoint_url = models.CharField(
        max_length=512,
        blank=True,
        default="",
        help_text="PrivateLink / PSC endpoint URL (empty = public hostname)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivation without deletion",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "warehouse_connections"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_warehouse_connection_name_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "warehouse_type"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"WarehouseConnection {self.name} ({self.warehouse_type})"

    def get_config(self) -> dict:
        """Decrypt and return the connection config."""
        from hub.apps.integrations.encryption import decrypt_json_field
        return decrypt_json_field(self.config)

    def set_config(self, raw_config: dict) -> None:
        """Encrypt and store connection config."""
        from hub.apps.integrations.encryption import encrypt_json_field
        self.config = encrypt_json_field(raw_config)

    def save(self, *args, **kwargs):
        # Phase 277.B.093 — data residency cross-validation:
        # warehouse region must be compatible with tenant residency.
        self._validate_residency()

        # Phase 275.A.1 — SSRF guard at config-save: validate any URL-like
        # fields in the raw config before encrypting. Reuses the SPARQL
        # federation validator pattern (is_safe_url + allowlist).
        if self.config and not isinstance(self.config.get("_encrypted"), str):
            self._validate_config_urls(self.config)

        # Encrypt on first save if raw config provided.
        if self.config and not isinstance(self.config.get("_encrypted"), str):
            raw = self.config
            self.config = {}
            super().save(*args, **kwargs)  # need pk first
            self.set_config(raw)
            kwargs.pop("force_insert", None)
            kwargs.pop("force_update", None)
            super().save(update_fields=["config"], **kwargs)
            return
        super().save(*args, **kwargs)

    @staticmethod
    def _validate_config_urls(config: dict) -> None:
        """Phase 275.A.1 — SSRF guard on URL-like config keys.

        Reuses the existing SSRF validation infrastructure (is_safe_url
        from hub.apps.security.url_validators) to prevent connections
        to internal/loopback addresses.
        """
        url_keys = {"host", "endpoint", "api_url", "base_url", "private_endpoint_url"}
        for key in url_keys:
            value = config.get(key)
            if value and isinstance(value, str) and value.startswith(("http://", "https://")):
                from hub.apps.security.url_validators import is_safe_url
                if not is_safe_url(value):
                    from django.core.exceptions import ValidationError
                    raise ValidationError(
                        f"URL in '{key}' is not safe: {value}. "
                        f"Internal/loopback addresses are blocked per SSRF policy."
                    )

    def _validate_residency(self) -> None:
        """Phase 277.B.093 — enforce tenant data residency on warehouse region."""
        if not self.region:
            return
        tenant = self.tenant
        residency = getattr(tenant, "data_residency_region", None)
        if not residency:
            return
        from hub.apps.warehouses.residency_validator import validate_warehouse_region
        result = validate_warehouse_region(residency, self.region)
        if not result.valid:
            from django.core.exceptions import ValidationError
            raise ValidationError(
                {
                    "region": (
                        f"Warehouse region '{self.region}' (ISO {result.warehouse_iso}) "
                        f"is not compatible with tenant data residency "
                        f"'{residency}'. Allowed ISO codes: "
                        f"{sorted(result.allowed_iso)[:10]}..."
                    ),
                },
                code="DATA_RESIDENCY_MISMATCH",
            )

    def delete(self, *args, **kwargs):
        """Phase 275.A.17 — refuse deletion while LIVE_QUERY assets reference
        this connection. Soft-delete via is_active=False instead."""
        from hub.apps.assets.models import Asset, DataStrategy
        live_assets = Asset.objects.filter(
            warehouse_connection=self,
            data_strategy=DataStrategy.LIVE_QUERY,
        )
        if live_assets.exists():
            from django.core.exceptions import ValidationError
            raise ValidationError(
                f"Cannot delete WarehouseConnection '{self.name}': "
                f"{live_assets.count()} LIVE_QUERY asset(s) still reference it. "
                f"Set is_active=False to deactivate without deletion, or reassign "
                f"the assets first."
            )
        super().delete(*args, **kwargs)


class WarehouseConnectionACL(models.Model):
    """Phase 275.A.21 — per-connection RBAC for finer-grained access.

    Default: TENANT_ADMIN inherits all. Explicit grants narrow access.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="warehouse_acls",
    )
    connection = models.ForeignKey(
        WarehouseConnection,
        on_delete=models.CASCADE,
        related_name="acls",
        help_text="Connection this ACL applies to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="warehouse_acls",
        null=True,
        blank=True,
    )
    role = models.CharField(
        max_length=50,
        default="VIEWER",
        help_text="Access role: ADMIN, OPERATOR, VIEWER",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "warehouse_connection_acls"
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "user"],
                name="unique_warehouse_acl_per_user",
            ),
        ]
