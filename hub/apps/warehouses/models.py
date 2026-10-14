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
from hub.settings import HUB_CORE_ONLY


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
    # P0 (openspec add-databricks-control-plane task 0.10) — optional
    # linkage to the control-plane registry. SET_NULL: the connection owns
    # its encrypted config; deleting the workspace/credential unlinks but
    # never destroys the connection.
    # W7.3 core-mode conditioning: the estate app is not installed in
    # core/public trees, so the FK fields exist in FULL mode only (the
    # 313.1 conditional-paid-FK contract; the W4.6 sweep owns the
    # serializer/query guards for the full-mode surface).
    if not HUB_CORE_ONLY:
        databricks_workspace = models.ForeignKey(
            "databricks_admin.DatabricksWorkspace",
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            related_name="warehouse_connections",
            help_text="Control-plane workspace this connection derives from",
        )
        databricks_credential = models.ForeignKey(
            "databricks_admin.DatabricksCredential",
            null=True,
            blank=True,
            on_delete=models.SET_NULL,
            related_name="warehouse_connections",
            help_text="Control-plane credential this connection mirrors",
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

    @classmethod
    def derive_from_databricks(
        cls,
        workspace,
        credential,
        *,
        http_path: str = "",
        name: str | None = None,
    ) -> WarehouseConnection:
        """P0 (task 0.10) — derive a ready-to-save connection from the
        control-plane registry (PAT credentials only — M2M derivation is
        not part of the P3 http_path linkage either).

        The config is encrypted through the real chain in-memory; the
        caller saves when ready.
        """
        if credential.workspace_id != workspace.id:
            raise ValueError(
                f"Credential '{credential.id}' does not belong to workspace '{workspace.id}'"
            )
        # The PAT-only contract is ENFORCED here, not just documented: an
        # M2M credential (or a token-less config) would silently derive a
        # connection with an empty pat_token that only fails later, at
        # connect time. (String comparison — the provider-boundary contract
        # forbids importing the databricks_admin enum into this app.)
        if credential.auth_mode != "PAT":
            raise ValueError(
                f"Credential '{credential.id}' is {credential.auth_mode}; "
                "derive_from_databricks supports PAT credentials only "
                "(M2M derivation lands with P3)"
            )
        token = credential.get_config().get("token", "")
        if not token:
            raise ValueError(f"Credential '{credential.id}' carries no PAT token to derive from")
        http_path = (http_path or "").strip()
        if not http_path:
            raise ValueError("http_path is required to derive a Databricks warehouse connection")
        conn = cls(
            tenant=workspace.tenant,
            name=name or f"{workspace.name} live connection",
            warehouse_type=WarehouseType.DATABRICKS,
            region=workspace.region,
            **(
                {
                    "databricks_workspace": workspace,
                    "databricks_credential": credential,
                }
                if not HUB_CORE_ONLY
                else {}
            ),
        )
        conn.set_config(
            {
                "host": workspace.host,
                "http_path": http_path,
                "pat_token": token,
            }
        )
        return conn

    @classmethod
    def derive_from_sql_warehouse(
        cls,
        workspace,
        credential,
        sql_warehouse,
        *,
        name: str | None = None,
    ) -> WarehouseConnection:
        """P3 (task 3.6) — derive a ready-to-save connection from the
        control-plane registry + a SQL warehouse MIRROR row.

        The http_path is DERIVED from the mirror's warehouse id —
        ``/sql/1.0/warehouses/{id}`` (the Databricks connector's
        canonical form): the connection stores the derived path, the
        mirror row stays the source of the id (the path is never stored
        twice — design D5).

        Duck-typed boundary: the provider-boundary contract forbids
        importing ``databricks_admin`` models into this app, so the
        warehouse row is read through its public attributes
        (``workspace_id`` / ``warehouse_id`` / ``name``) — the 0.10
        string-comparison discipline. The PAT-only contract is inherited
        from ``derive_from_databricks``.

        Guards: a foreign-workspace warehouse, an empty/blank id, or a
        slash-bearing id (which would break the canonical path shape)
        raise ValueError; a non-string id raises TypeError — all BEFORE
        any config is built.
        """
        if sql_warehouse.workspace_id != workspace.id:
            raise ValueError(
                f"SQL warehouse '{getattr(sql_warehouse, 'id', '?')}' does not belong to "
                f"workspace '{workspace.id}'"
            )
        raw_id = sql_warehouse.warehouse_id
        if not isinstance(raw_id, str):
            raise TypeError("sql_warehouse.warehouse_id must be a string")
        warehouse_id = raw_id.strip()
        if not warehouse_id:
            raise ValueError("SQL warehouse id must not be empty")
        if "/" in warehouse_id:
            # A slash would produce /sql/1.0/warehouses/<a>/<b> — a
            # structurally broken path the executor's resolve_warehouse_id
            # would mis-parse.
            raise ValueError(
                "SQL warehouse id must not contain '/' — it would break the canonical http_path"
            )
        return cls.derive_from_databricks(
            workspace,
            credential,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            name=name or f"{sql_warehouse.name} connection",
        )

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

        # W1.13 — the COLUMN check must run on EVERY save: the pre-fix
        # placement inside the raw-config branch let an update on an
        # already-encrypted connection change private_endpoint_url to an
        # internal address with no SSRF validation at all.
        self._validate_private_endpoint_url()

        # Phase 275.A.1 — SSRF guard at config-save: validate any URL-like
        # fields in the raw config before encrypting. Reuses the SPARQL
        # federation validator pattern (is_safe_url + allowlist).
        # Guard: config may be a plain string (already encrypted/serialized)
        # rather than a dict — skip SSRF validation and encryption in that case.
        _config_is_dict = isinstance(self.config, dict)

        if _config_is_dict and not isinstance(self.config.get("_encrypted"), str):
            self._validate_config_urls(self.config)

        # Encrypt on first save if raw config provided.
        if _config_is_dict and not isinstance(self.config.get("_encrypted"), str):
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

        Any value carrying a scheme (``://``) MUST pass the SSRF guard —
        non-http schemes (ftp/file/jdbc/gopher) are rejected by the
        scheme gate, never silently skipped (the pre-fix
        ``startswith(http)`` filter skipped them). Bare hostnames
        (no scheme) are warehouse-specific host configs (JDBC-style)
        and stay out of scope.

        NOTE: the pre-fix import of ``is_safe_url`` from
        ``hub.apps.security.url_validators`` was broken (that module
        defines no such symbol — the guard lives in
        ``hub.apps.webhooks.ssrf_guard``), so ANY URL-shaped config
        value crashed the save with ImportError and the check was dead
        code (pilot-readiness 4.1 root cause).
        """
        url_keys = {"host", "endpoint", "api_url", "base_url", "private_endpoint_url"}
        for key in url_keys:
            value = config.get(key)
            if value and isinstance(value, str) and "://" in value:
                from hub.apps.webhooks.ssrf_guard import is_safe_url

                if not is_safe_url(value):
                    from django.core.exceptions import ValidationError

                    raise ValidationError(
                        f"URL in '{key}' is not safe: {value}. "
                        f"Internal/loopback addresses are blocked per SSRF policy."
                    )

    def _validate_private_endpoint_url(self) -> None:
        """pilot-readiness 4.1 — the ``private_endpoint_url`` COLUMN was
        never SSRF-checked (only the same-named key inside the config
        dict was). Same gate, same policy."""
        value = self.private_endpoint_url
        if value and isinstance(value, str) and "://" in value:
            from hub.apps.webhooks.ssrf_guard import is_safe_url

            if not is_safe_url(value):
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    f"private_endpoint_url is not safe: {value}. "
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
        constraints = (
            models.UniqueConstraint(
                fields=["connection", "user"],
                name="unique_warehouse_acl_per_user",
            ),
        )
