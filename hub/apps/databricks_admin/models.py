"""P0 (openspec add-databricks-control-plane) — Databricks control-plane models.

``DatabricksWorkspace`` is the registry entry for a customer-BYO Databricks
workspace: tenant-scoped, with host/cloud/region and a lifecycle status.
It is the RLS parent for every later control-plane model (credentials,
UC mirrors, warehouses, jobs, DLT pipelines, budgets).

Conventions follow ``hub/apps/warehouses/models.py``: UUID pk, explicit
``db_table``, per-tenant unique name, and a paired RLS policy migration
(``0002_enable_rls_databricks_workspaces.py``) per the CLAUDE.md contract.
"""

from __future__ import annotations

import logging
import uuid
from typing import ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from hub.apps.databricks_admin.validation import (
    revalidate_workspace_host,
    validate_workspace_host,
    validate_workspace_region,
)

logger = logging.getLogger(__name__)


class DatabricksWorkspaceStatus(models.TextChoices):
    """Lifecycle of a registered workspace."""

    REGISTERED = "REGISTERED", "Registered"
    CONNECTING = "CONNECTING", "Connecting"
    ACTIVE = "ACTIVE", "Active"
    ERROR = "ERROR", "Error"
    DISABLED = "DISABLED", "Disabled"


class DatabricksCloud(models.TextChoices):
    """Cloud hosting the workspace (BYO — any of the three)."""

    AWS = "AWS", "AWS"
    AZURE = "AZURE", "Azure"
    GCP = "GCP", "GCP"


class DatabricksCredentialAuthMode(models.TextChoices):
    """Credential types accepted for a workspace."""

    PAT = "PAT", "PAT"
    OAUTH_M2M = "OAUTH_M2M", "OAuth M2M"


class AdminDatabaseManager(models.Manager):
    """Manager that pins every queryset to ``DATABASES["admin"]``.

    The CLAUDE.md management-command convention extended to a MODEL
    surface: the account plane's platform tables carry no tenant scoping,
    and their only sanctioned access path is the admin DB alias
    (``meshant_admin``, BYPASSRLS). Every queryset handed out here carries
    ``_db="admin"`` — reads, writes, and aggregates alike — so
    tenant-scoped code paths can never reach a platform table through the
    default alias without an EXPLICIT ``.using(...)`` escape hatch.
    Multi-write callers must wrap ``transaction.atomic(using="admin")``
    (the request autocommit boundary covers the DEFAULT alias, not the
    admin alias).
    """

    def get_queryset(self):
        return super().get_queryset().using("admin")


class DatabricksWorkspace(models.Model):
    """A customer-BYO Databricks workspace registered with the Hub.

    Host validation (SSRF + residency) lands with task 0.4; credentials
    with task 0.3. Status changes go through transition_to() only
    (billing Subscription pattern; see the workspace-registry spec
    "Workspace Lifecycle Transitions").
    """

    # Valid status transitions — maps from_status to allowed to_statuses.
    # Used by transition_to() to prevent invalid state changes; DISABLED is
    # terminal (re-enable is a deliberate product decision, not a transition).
    VALID_TRANSITIONS: ClassVar[dict[str, list[str]]] = {
        DatabricksWorkspaceStatus.REGISTERED: [
            DatabricksWorkspaceStatus.CONNECTING,
            DatabricksWorkspaceStatus.ACTIVE,
            DatabricksWorkspaceStatus.ERROR,
            DatabricksWorkspaceStatus.DISABLED,
        ],
        DatabricksWorkspaceStatus.CONNECTING: [
            DatabricksWorkspaceStatus.ACTIVE,
            DatabricksWorkspaceStatus.ERROR,
            DatabricksWorkspaceStatus.DISABLED,
        ],
        DatabricksWorkspaceStatus.ACTIVE: [
            DatabricksWorkspaceStatus.ERROR,
            DatabricksWorkspaceStatus.DISABLED,
        ],
        DatabricksWorkspaceStatus.ERROR: [
            DatabricksWorkspaceStatus.ACTIVE,
            DatabricksWorkspaceStatus.DISABLED,
        ],
        DatabricksWorkspaceStatus.DISABLED: [],
    }

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="databricks_workspaces",
        help_text="Tenant this workspace belongs to",
    )
    name: models.CharField = models.CharField(
        max_length=255,
        help_text="Human-readable workspace name (unique per tenant)",
    )
    host: models.CharField = models.CharField(
        max_length=255,
        help_text="Workspace host, restricted to the *.cloud.databricks.com family",
    )
    cloud: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksCloud.choices,
        help_text="Cloud hosting the workspace",
    )
    region: models.CharField = models.CharField(
        max_length=64,
        help_text="Workspace region (validated against tenant residency with task 0.4)",
    )
    metastore_id: models.UUIDField = models.UUIDField(
        null=True,
        blank=True,
        help_text="Unity Catalog metastore id, when known",
    )
    status: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksWorkspaceStatus.choices,
        default=DatabricksWorkspaceStatus.REGISTERED,
        help_text="Workspace lifecycle status",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)
    last_cost_synced_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "P7 (7.3) — the max system.billing.usage start_time the cost "
            "sync has ingested; the next delta reads at-or-after this stamp"
        ),
    )

    class Meta:
        db_table = "databricks_workspaces"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="unique_databricks_workspace_name_per_tenant",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "cloud"]),
        ]

    def __str__(self):
        return f"DatabricksWorkspace {self.name} ({self.host})"

    def clean(self):
        """Task 0.4 — SSRF + residency at model validation time.

        ``full_clean()`` reaches this through Django's validation chain;
        ``save()`` calls the same validators directly (Django does not run
        ``clean()`` on plain ``save()``).
        """
        self.host = validate_workspace_host(self.host)
        validate_workspace_region(self.tenant, self.region)
        super().clean()

    def save(self, *args, **kwargs):
        # Task 0.4 — SSRF + residency guards at persist time (same pattern
        # as WarehouseConnection.save). Normalises the host as a side effect.
        # Partial saves (update_fields) skip the validators for fields they
        # do NOT write: a status-only soft-delete must not re-resolve the
        # host DNS (a decommissioned host would 500 the delete).
        update_fields = kwargs.get("update_fields")
        if update_fields is None or "host" in update_fields:
            self.host = validate_workspace_host(self.host)
        if update_fields is None or "region" in update_fields:
            validate_workspace_region(self.tenant, self.region)
        super().save(*args, **kwargs)

    def validate_for_dispatch(self) -> None:
        """Task 0.4 — dispatch-time DNS re-resolution (rebinding guard).

        Called by the API client before any outbound call to this
        workspace (task 0.5+).
        """
        revalidate_workspace_host(self.host)

    def transition_to(self, new_status: str) -> bool:
        """Validate and apply a status transition (does NOT persist).

        Returns True if applied, False for a same-status no-op. Raises
        ValidationError with code="invalid_workspace_status_transition" on
        an invalid transition; the caller saves explicitly.
        """
        if self.status == new_status:
            return False  # No-op, already in this state

        allowed = self.VALID_TRANSITIONS.get(self.status, [])
        if new_status not in allowed:
            logger.warning(
                "Invalid DatabricksWorkspace status transition",
                extra={
                    "workspace_id": str(self.id),
                    "from_status": self.status,
                    "to_status": new_status,
                },
            )
            raise ValidationError(
                f"Cannot transition DatabricksWorkspace from {self.status} to "
                f"{new_status}. Allowed transitions: {allowed}",
                code="invalid_workspace_status_transition",
            )

        self.status = new_status
        return True


class EncryptedConfigModelMixin:
    """Fernet-wrapper ``config`` column: decrypt/get + encrypt/set + the save() guard.

    Shared by ``DatabricksCredential`` (P0) and ``DatabricksAccount`` (P8):
    the column stores ``{"_encrypted": "<ciphertext>"}`` via
    ``hub/apps/integrations/encryption.py`` (KMS primary, Fernet fallback)
    and NEVER plaintext. ``save()`` rejects non-dict values outright (a
    bare JSON string/array would bypass encryption entirely) and encrypts
    any unwrapped dict with a two-phase save (pk first, then ciphertext).
    """

    def get_config(self) -> dict:
        """Decrypt and return the config.

        The column stores the MarketplaceConnection wrapper shape
        ``{"_encrypted": "<ciphertext>"}``; the unwrap lives here (the model
        layer), mirroring ``MarketplaceConnection.get_config``.
        """
        from hub.apps.integrations.encryption import decrypt_json_field

        encrypted_str = self.config
        if isinstance(encrypted_str, dict) and "_encrypted" in encrypted_str:
            encrypted_str = encrypted_str["_encrypted"]
        return decrypt_json_field(encrypted_str)

    def set_config(self, raw_config: dict) -> None:
        """Encrypt and store config (wrapper shape)."""
        from hub.apps.integrations.encryption import encrypt_json_field

        self.config = {"_encrypted": encrypt_json_field(raw_config)}

    def save(self, *args, **kwargs):
        # MarketplaceConnection guard: a plain dict without the wrapper is
        # raw input — encrypt + wrap it; an already-wrapped dict is stored
        # as-is. ANY non-dict value is REJECTED: a bare JSON string/array
        # would bypass encryption entirely (plaintext at rest) — the tables
        # using this mixin have no legacy plaintext data to preserve.
        if not isinstance(self.config, dict):
            raise ValidationError(
                f"{type(self).__name__}.config must be a JSON object (encrypted wrapper)",
                code="invalid_credential_config_shape",
            )

        if not isinstance(self.config.get("_encrypted"), str):
            raw = self.config
            self.config = {}
            super().save(*args, **kwargs)  # need pk first
            self.set_config(raw)
            kwargs.pop("force_insert", None)
            kwargs.pop("force_update", None)
            kwargs.pop("update_fields", None)  # the second write owns the fields
            super().save(update_fields=["config"], **kwargs)
            return
        super().save(*args, **kwargs)


class DatabricksCredential(EncryptedConfigModelMixin, models.Model):
    """A PAT or OAuth M2M credential for a registered workspace.

    Credential material is stored as ``{"_encrypted": "<ciphertext>"}`` in
    the ``config`` JSONField via ``hub/apps/integrations/encryption.py``
    (KMS primary, Fernet fallback) — the same wrapper shape as
    ``WarehouseConnection`` (implemented by ``EncryptedConfigModelMixin``).
    The model has NO tenant_id column: tenant isolation is enforced through
    the workspace parent chain by the indirect-FK RLS policy
    (``0005_enable_rls_databricks_credentials.py``).
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="credentials",
        help_text="Workspace this credential authenticates against",
    )
    auth_mode: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksCredentialAuthMode.choices,
        help_text="Credential type",
    )
    config: models.JSONField = models.JSONField(
        default=dict,
        help_text="Encrypted credential config (token / client_id+secret)",
    )
    expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Best-effort expiry of the credential (PATs may not expose one)",
    )
    last_rotated_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When rotation last rewrote this credential",
    )
    # Phase 1 (add-databricks-uc-read 1.5) — the Phase 272 access request
    # whose approver chain authorized this service credential. The UC
    # metadata sync job resolves its D12 BACKGROUND identity through it
    # (approver-chain audit linkage); a credential WITHOUT one can never
    # execute a background sync (fail-closed).
    approval_request: models.ForeignKey = models.ForeignKey(
        "governance.AccessRequest",
        on_delete=models.SET_NULL,
        related_name="databricks_credentials",
        null=True,
        blank=True,
        help_text="Access request whose approval chain authorized this credential",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_credentials"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["workspace", "auth_mode"]),
        ]

    def __str__(self):
        return f"DatabricksCredential {self.workspace.name} ({self.auth_mode})"


class DatabricksUserBinding(models.Model):
    """Hub-user ↔ Databricks-principal binding (task 0b.3).

    One row per (Hub user, workspace) AND per (workspace, Databricks sub) —
    exclusivity both ways: a Databricks principal cannot be bound to two
    Hub accounts on the same workspace (impersonation guard), and a Hub
    user has at most one principal per workspace. The same principal on a
    DIFFERENT workspace is a separate row — resolution is workspace-keyed,
    which is the model-level guarantee behind "per-workspace tokens never
    reused across workspaces" (0b.4/0b.5 consume it).

    tenant_id is stored directly: the direct-FK RLS template applies
    (CLAUDE.md RLS contract — paired policy migration).
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="databricks_user_bindings",
        help_text="Tenant the binding belongs to (mirrors the workspace's tenant)",
    )
    user: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="databricks_user_bindings",
        help_text="Hub user this binding authenticates for",
    )
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="user_bindings",
        help_text="Workspace the principal belongs to",
    )
    databricks_sub: models.CharField = models.CharField(
        max_length=255,
        help_text="Databricks principal 'sub' claim (stable identity)",
    )
    databricks_email: models.CharField = models.CharField(
        max_length=255,
        help_text="Email asserted by the Databricks id_token at last login",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_user_bindings"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["user", "workspace"],
                name="uniq_databricks_binding_user_workspace",
            ),
            models.UniqueConstraint(
                fields=["workspace", "databricks_sub"],
                name="uniq_databricks_binding_workspace_sub",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "user"]),
        ]

    def __str__(self):
        return f"DatabricksUserBinding {self.user.email} → {self.workspace.name}"


class DatabricksOBOToken(models.Model):
    """On-Behalf-Of token vault row (task 0b.4).

    ONE row per binding: the CURRENT refresh token, encrypted with the
    repo's real encryption chain (KMS primary, Fernet fallback via
    ``hub.apps/integrations/encryption``), plus the current access-token
    expiry bookkeeping. The access token itself lives ONLY in the Redis
    cache (TTL ≤ expiry) — never at rest.

    Single-use rotation: every successful refresh REPLACES the stored
    refresh ciphertext — the old token can never be replayed from the
    vault.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="databricks_obo_tokens",
        help_text="Tenant the vault row belongs to",
    )
    binding: models.ForeignKey = models.ForeignKey(
        DatabricksUserBinding,
        on_delete=models.CASCADE,
        related_name="obo_tokens",
        help_text="The (user, workspace) binding this token authenticates for",
    )
    refresh_token_encrypted: models.JSONField = models.JSONField(
        default=dict,
        help_text="Encrypted refresh token (wrapper shape, never plaintext)",
    )
    refresh_token_expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Refresh-token expiry when the workspace reports one",
    )
    access_token_expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiry of the CURRENT access token",
    )
    last_refreshed_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the access token was last refreshed",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_obo_tokens"
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "binding",
                ],
                name="uniq_databricks_obo_token_binding",
            ),
        ]

    def __str__(self):
        return f"DatabricksOBOToken {self.binding}"

    def set_refresh_token(self, raw_refresh_token: str) -> None:
        """Encrypt and store the refresh token (wrapper shape)."""
        from hub.apps.integrations.encryption import encrypt_json_field

        self.refresh_token_encrypted = {
            "_encrypted": encrypt_json_field({"refresh_token": raw_refresh_token})
        }

    def get_refresh_token(self) -> str:
        """Decrypt and return the refresh token."""
        from hub.apps.integrations.encryption import decrypt_json_field

        encrypted_str = self.refresh_token_encrypted
        if isinstance(encrypted_str, dict):
            encrypted_str = encrypted_str.get("_encrypted")
        if not encrypted_str:
            return ""
        payload = decrypt_json_field(encrypted_str)
        return str(payload.get("refresh_token") or "")


# ─────────────────────────────────────────────────────────────────────────────
# Unity Catalog mirror models (openspec add-databricks-uc-read task 1.2)
#
# READ-ONLY mirror of the workspace's UC estate — a refreshable cache. The
# Hub never writes UC metadata on the Databricks side through these rows.
# Tenant isolation: NO tenant_id column — the indirect-FK RLS policy
# resolves the tenant through the parent chain (table → schema → catalog →
# workspace → tenant), the same template as databricks_credentials.
# ─────────────────────────────────────────────────────────────────────────────


class _UCMirrorBase(models.Model):
    """Common mirror-row bookkeeping (abstract)."""

    synced_at = models.DateTimeField(
        default=timezone.now, help_text="Last sync that refreshed this row"
    )

    class Meta:
        abstract = True


class UCCatalog(_UCMirrorBase):
    """Unity Catalog catalog (workspace-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_catalogs",
        help_text="Workspace this catalog was mirrored from",
    )
    name: models.CharField = models.CharField(max_length=255)
    catalog_type: models.CharField = models.CharField(max_length=32, default="MANAGED")
    comment: models.TextField = models.TextField(blank=True, default="")
    properties: models.JSONField = models.JSONField(default=dict)
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_catalogs"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="uniq_uc_catalog_workspace_name"
            ),
        ]

    def __str__(self):
        return f"UCCatalog {self.name}"


class UCSchema(_UCMirrorBase):
    """Unity Catalog schema (catalog-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    catalog: models.ForeignKey = models.ForeignKey(
        UCCatalog,
        on_delete=models.CASCADE,
        related_name="schemas",
    )
    name: models.CharField = models.CharField(max_length=255)
    comment: models.TextField = models.TextField(blank=True, default="")
    properties: models.JSONField = models.JSONField(default=dict)
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_schemas"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["catalog", "name"], name="uniq_uc_schema_catalog_name"),
        ]

    def __str__(self):
        return f"UCSchema {self.name}"


class UCTable(_UCMirrorBase):
    """Unity Catalog table (schema-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema: models.ForeignKey = models.ForeignKey(
        UCSchema,
        on_delete=models.CASCADE,
        related_name="tables",
    )
    name: models.CharField = models.CharField(max_length=255)
    table_type: models.CharField = models.CharField(max_length=32, default="MANAGED")
    comment: models.TextField = models.TextField(blank=True, default="")
    columns: models.JSONField = models.JSONField(default=list)
    storage_location: models.CharField = models.CharField(max_length=1024, blank=True, default="")
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    tags: models.JSONField = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "The UC tables API's reported tags (list of {key, value}) — "
            "the feature_store convention reads this (12.3)"
        ),
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_tables"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["schema", "name"], name="uniq_uc_table_schema_name"),
        ]

    def __str__(self):
        return f"UCTable {self.name}"


class UCView(_UCMirrorBase):
    """Unity Catalog view (schema-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema: models.ForeignKey = models.ForeignKey(
        UCSchema,
        on_delete=models.CASCADE,
        related_name="views",
    )
    name: models.CharField = models.CharField(max_length=255)
    comment: models.TextField = models.TextField(blank=True, default="")
    view_definition: models.TextField = models.TextField(blank=True, default="")
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_views"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["schema", "name"], name="uniq_uc_view_schema_name"),
        ]

    def __str__(self):
        return f"UCView {self.name}"


class UCVolume(_UCMirrorBase):
    """Unity Catalog volume (schema-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema: models.ForeignKey = models.ForeignKey(
        UCSchema,
        on_delete=models.CASCADE,
        related_name="volumes",
    )
    name: models.CharField = models.CharField(max_length=255)
    volume_type: models.CharField = models.CharField(max_length=32, default="MANAGED")
    comment: models.TextField = models.TextField(blank=True, default="")
    storage_location: models.CharField = models.CharField(max_length=1024, blank=True, default="")
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_volumes"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["schema", "name"], name="uniq_uc_volume_schema_name"),
        ]

    def __str__(self):
        return f"UCVolume {self.name}"


class UCExternalLocation(_UCMirrorBase):
    """Unity Catalog external location (workspace-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_external_locations",
    )
    name: models.CharField = models.CharField(max_length=255)
    url: models.CharField = models.CharField(max_length=1024)
    credential_name: models.CharField = models.CharField(max_length=255, blank=True, default="")
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_external_locations"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="uniq_uc_external_location_workspace_name"
            ),
        ]

    def __str__(self):
        return f"UCExternalLocation {self.name}"


class UCStorageCredential(_UCMirrorBase):
    """Unity Catalog storage credential (workspace-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_storage_credentials",
    )
    name: models.CharField = models.CharField(max_length=255)
    comment: models.TextField = models.TextField(blank=True, default="")
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_storage_credentials"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="uniq_uc_storage_credential_workspace_name"
            ),
        ]

    def __str__(self):
        return f"UCStorageCredential {self.name}"


class UCModel(_UCMirrorBase):
    """Unity Catalog registered model (schema-scoped)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schema: models.ForeignKey = models.ForeignKey(
        UCSchema,
        on_delete=models.CASCADE,
        related_name="models",
    )
    name: models.CharField = models.CharField(max_length=255)
    comment: models.TextField = models.TextField(blank=True, default="")
    aliases: models.JSONField = models.JSONField(default=list)
    latest_version: models.IntegerField = models.IntegerField(default=0)
    owner: models.CharField = models.CharField(max_length=255, blank=True, default="")
    full_name: models.CharField = models.CharField(max_length=511, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_models"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["schema", "name"], name="uniq_uc_model_schema_name"),
        ]

    def __str__(self):
        return f"UCModel {self.name}"


class UCModelVersion(_UCMirrorBase):
    """Unity Catalog registered-model VERSION (openspec
    add-databricks-ml-assets task 12.2 — design D1).

    Model-scoped: tenant isolation resolves through the parent chain
    (model → schema → catalog → workspace — the indirect-FK RLS
    policy). The mirror carries the MLflow surface's reported version
    number, source, run link, and status — never invented."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model: models.ForeignKey = models.ForeignKey(
        UCModel,
        on_delete=models.CASCADE,
        related_name="versions",
        help_text="Registered model the version belongs to (CASCADE — versions die with the model mirror row)",
    )
    version: models.IntegerField = models.IntegerField(
        help_text="The version number as REPORTED by the MLflow surface"
    )
    source: models.CharField = models.CharField(
        max_length=1024, blank=True, default="", help_text="The MLflow source URI"
    )
    run_id: models.CharField = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="The MLflow run id that produced the version",
    )
    run_link: models.CharField = models.CharField(
        max_length=2048, blank=True, default="", help_text="The MLflow run link"
    )
    status: models.CharField = models.CharField(
        max_length=64, blank=True, default="", help_text="The version status as REPORTED by the API"
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_uc_model_versions"
        ordering = ("version",)
        constraints = [
            models.UniqueConstraint(
                fields=["model", "version"], name="uniq_uc_model_version_model_version"
            ),
        ]

    def __str__(self):
        return f"UCModelVersion {self.model_id}:{self.version}"


class DatabricksMlServingEndpointType(models.TextChoices):
    """The serving-surface kinds the 12.4 mirror carries."""

    SERVING = "SERVING", "Serving endpoint"
    VECTOR = "VECTOR", "Vector Search endpoint"


class DatabricksMlServingEndpoint(_UCMirrorBase):
    """A mirrored ML serving/vector-search endpoint (openspec
    add-databricks-ml-assets task 12.4 — design D5).

    Workspace-scoped (the indirect-FK RLS policy). The mirror carries
    the API-reported name, kind, and state — never invented."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="ml_serving_endpoints",
        help_text="Workspace the endpoint belongs to (CASCADE — the mirror dies with the registry entry)",
    )
    endpoint_type: models.CharField = models.CharField(
        max_length=16,
        choices=DatabricksMlServingEndpointType.choices,
        default=DatabricksMlServingEndpointType.SERVING,
        help_text="The surface kind (serving vs vector search)",
    )
    name: models.CharField = models.CharField(
        max_length=255, help_text="The endpoint name as REPORTED by the API"
    )
    state: models.CharField = models.CharField(
        max_length=64, blank=True, default="", help_text="The endpoint state as REPORTED by the API"
    )
    config: models.JSONField = models.JSONField(
        default=dict,
        blank=True,
        help_text="The reported endpoint config (served models / vector config)",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_ml_serving_endpoints"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "endpoint_type", "name"],
                name="uniq_ml_serving_endpoint_workspace_type_name",
            ),
        ]

    def __str__(self):
        return f"DatabricksMlServingEndpoint {self.name}"


# ─────────────────────────────────────────────────────────────────────────────
# UC change request (openspec add-databricks-control-plane task 2.2)
#
# D7: DDL via approval workflow — the highest-blast-radius write surface.
# Modeled on governance's AccessRequest (NOT a reuse — access vs mutation
# semantics). tenant_id is stored directly: the direct-FK RLS template
# applies (CLAUDE.md RLS contract — policy ships in migration 0014).


class UCChangeRequestStatus(models.TextChoices):
    """D7 spine: DRAFT→PENDING_APPROVAL→APPROVED→EXECUTING→EXECUTED/FAILED/ROLLED_BACK.

    PENDING_NEXT_APPROVER is the 272.4 intermediate between multi-step
    approvals; REJECTED is the deny terminal (AccessRequest parity).
    """

    DRAFT = "DRAFT", "Draft"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Pending Approval"
    PENDING_NEXT_APPROVER = "PENDING_NEXT_APPROVER", "Pending Next Approver"
    APPROVED = "APPROVED", "Approved"
    EXECUTING = "EXECUTING", "Executing"
    EXECUTED = "EXECUTED", "Executed"
    FAILED = "FAILED", "Failed"
    ROLLED_BACK = "ROLLED_BACK", "Rolled Back"
    REJECTED = "REJECTED", "Rejected"


class UCObjectType(models.TextChoices):
    """The UC securable surface a change targets (D5's securable-type
    language; the grants bridge's FUNCTION lands with task 2.6).

    THE canonical vocabulary — task 2.3's executor
    (``hub.apps.databricks_admin.uc_change_executor``) re-exports these
    enums, so a ``UCChangeRequest`` row's values flow into a typed
    ``UCDdlPayload`` without translation.
    """

    CATALOG = "CATALOG", "Catalog"
    SCHEMA = "SCHEMA", "Schema"
    TABLE = "TABLE", "Table"
    VIEW = "VIEW", "View"
    MATERIALIZED_VIEW = "MATERIALIZED_VIEW", "Materialized View"
    STREAMING_TABLE = "STREAMING_TABLE", "Streaming Table"
    VOLUME = "VOLUME", "Volume"
    EXTERNAL_LOCATION = "EXTERNAL_LOCATION", "External Location"
    STORAGE_CREDENTIAL = "STORAGE_CREDENTIAL", "Storage Credential"
    MODEL = "MODEL", "Model"


class UCChangeAction(models.TextChoices):
    """The DDL mutation class the request asks for (D7 / task 2.3).

    CREATE/DROP match the executor's REST DDL surface; ALTER lands when
    the executor gains it (the model's status machine is action-agnostic).
    """

    CREATE = "CREATE", "Create"
    DROP = "DROP", "Drop"


class UCChangeRequest(models.Model):
    """A tenant's request to mutate a UC object on a registered workspace.

    Lifecycle (the state machine is ``ALLOWED_TRANSITIONS`` — the single
    source of truth; ``transition_to()`` enforces it):
        DRAFT → PENDING_APPROVAL → APPROVED → EXECUTING → EXECUTED
                                      │            └──────→ FAILED → ROLLED_BACK
                                      └──────→ REJECTED

    Multi-step approval (272.4): ``required_approval_chain`` is the chain
    the request must satisfy; it is SNAPSHOTTED into ``approval_workflow``
    on FIRST approval so in-flight workflows are frozen against later
    policy edits. Delegation (272.6): approvals may be exercised through an
    active ``ApprovalDelegation`` whose delegator is authorized for the
    step (service-level, ``hub.apps.databricks_admin.uc_changes``).
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="uc_change_requests",
        help_text="Tenant this change request belongs to",
    )
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_change_requests",
        help_text="Workspace the UC object lives on",
    )
    requested_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="requested_uc_changes",
        null=True,
        blank=True,
        help_text="User who requested the change (SET_NULL — DDL history survives user deletion)",
    )
    change_type: models.CharField = models.CharField(
        max_length=10,
        choices=UCChangeAction.choices,
        help_text="DDL action (the executor's UCChangeAction vocabulary)",
    )
    securable_type: models.CharField = models.CharField(
        max_length=30,
        choices=UCObjectType.choices,
        help_text="UC securable the change targets (UCObjectType vocabulary)",
    )
    full_name: models.CharField = models.CharField(
        max_length=511,
        help_text="Fully-qualified UC object path (e.g. 'main.sales.orders_v2')",
    )
    definition: models.JSONField = models.JSONField(
        default=dict, help_text="DDL definition payload (name, options, SQL fallback hint)"
    )
    reason: models.TextField = models.TextField(
        blank=True, default="", help_text="Justification visible to approvers"
    )
    status: models.CharField = models.CharField(
        max_length=30,
        choices=UCChangeRequestStatus.choices,
        default=UCChangeRequestStatus.DRAFT,
        help_text="Lifecycle status (see ALLOWED_TRANSITIONS)",
    )
    requires_approval: models.BooleanField = models.BooleanField(
        default=True, help_text="Whether the change must pass the approval workflow"
    )
    # 272.4 multi-step approval (AccessRequest parity).
    required_approval_chain: models.JSONField = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Ordered approval steps this request must satisfy. Each step: "
            "{step: int, role: str, label: str} or {step: int, approvers: [user_id], "
            "label: str}; legacy string steps are role names. Default [] means "
            "single-step approval."
        ),
    )
    approval_workflow: models.JSONField = models.JSONField(
        default=list, blank=True, help_text="FROZEN snapshot of the chain (272.4)"
    )
    current_approval_step: models.IntegerField = models.IntegerField(
        default=0, help_text="Current approval step index"
    )
    approved_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="approved_uc_changes",
        null=True,
        blank=True,
        help_text="User whose approval completed the workflow (last approver)",
    )
    approved_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text="When the workflow completed"
    )
    rejection_reason: models.TextField = models.TextField(
        null=True, blank=True, help_text="Reason for rejection (required at reject)"
    )
    rejected_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="rejected_uc_changes",
        null=True,
        blank=True,
        help_text="User who rejected the request",
    )
    rejected_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text="When the request was rejected"
    )
    # Execution bookkeeping (task 2.3's executor consumes the guarded hooks).
    executing_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When the request entered EXECUTING — the 2.5 reaper's lease "
            "anchor (NULL while not executing; an EXECUTING row with no "
            "anchor is treated as abandoned)."
        ),
    )
    executed_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="executed_uc_changes",
        null=True,
        blank=True,
        help_text="User who executed the change",
    )
    executed_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text="When execution completed"
    )
    execution_error: models.TextField = models.TextField(
        null=True, blank=True, help_text="Execution failure detail (FAILED state)"
    )
    rolled_back_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="rolled_back_uc_changes",
        null=True,
        blank=True,
        help_text="User who rolled the change back",
    )
    rolled_back_at: models.DateTimeField = models.DateTimeField(
        null=True, blank=True, help_text="When the rollback completed"
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    # D7 state machine — the single source of truth. DRAFT→APPROVED is the
    # requires_approval=False submit shortcut; everything else follows the
    # documented spine. Terminal states have no outgoing edges.
    ALLOWED_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        UCChangeRequestStatus.DRAFT: {
            UCChangeRequestStatus.PENDING_APPROVAL,
            UCChangeRequestStatus.APPROVED,
        },
        UCChangeRequestStatus.PENDING_APPROVAL: {
            UCChangeRequestStatus.PENDING_NEXT_APPROVER,
            UCChangeRequestStatus.APPROVED,
            UCChangeRequestStatus.REJECTED,
        },
        UCChangeRequestStatus.PENDING_NEXT_APPROVER: {
            UCChangeRequestStatus.PENDING_NEXT_APPROVER,
            UCChangeRequestStatus.APPROVED,
            UCChangeRequestStatus.REJECTED,
        },
        UCChangeRequestStatus.APPROVED: {UCChangeRequestStatus.EXECUTING},
        # 2.5: EXECUTING → ROLLED_BACK is the reaper's resolution hop (a
        # stuck CREATE is rolled back best-effort through the machine).
        UCChangeRequestStatus.EXECUTING: {
            UCChangeRequestStatus.EXECUTED,
            UCChangeRequestStatus.FAILED,
            UCChangeRequestStatus.ROLLED_BACK,
        },
        UCChangeRequestStatus.FAILED: {UCChangeRequestStatus.ROLLED_BACK},
        UCChangeRequestStatus.EXECUTED: set(),
        UCChangeRequestStatus.ROLLED_BACK: set(),
        UCChangeRequestStatus.REJECTED: set(),
    }

    class Meta:
        db_table = "databricks_uc_change_requests"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "workspace"]),
            models.Index(fields=["workspace", "full_name"]),
        ]

    def __str__(self):
        return f"UCChangeRequest {self.change_type} {self.full_name} ({self.status})"

    def clean(self):
        super().clean()
        if not (self.full_name or "").strip():
            raise ValidationError(
                "full_name must be a non-empty UC object path", code="invalid_uc_change_full_name"
            )
        if not isinstance(self.definition, dict):
            raise ValidationError(
                "definition must be a JSON object", code="invalid_uc_change_definition"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def transition_to(self, new_status: str) -> bool:
        """Validate and apply a status transition (does NOT persist).

        Same contract as ``DatabricksWorkspace.transition_to``: True if
        applied, False for a same-status no-op, ValidationError
        (code="invalid_uc_change_status_transition") on an illegal hop;
        the caller saves explicitly.
        """
        if self.status == new_status:
            return False

        allowed = self.ALLOWED_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition UCChangeRequest from {self.status} to {new_status}. "
                f"Allowed transitions: {sorted(allowed)}",
                code="invalid_uc_change_status_transition",
            )

        self.status = new_status
        return True


class DatabricksSqlWarehouseState(models.TextChoices):
    """The compute API's warehouse lifecycle states (3.2 — the mirror
    maps them verbatim; the Hub never invents one)."""

    STARTING = "STARTING", "Starting"
    RUNNING = "RUNNING", "Running"
    STOPPING = "STOPPING", "Stopping"
    STOPPED = "STOPPED", "Stopped"
    DELETING = "DELETING", "Deleting"


class DatabricksSqlWarehouse(models.Model):
    """A mirrored SQL warehouse of a registered workspace (3.2).

    The mirror is a READ cache of the Databricks-owned state: rows are
    refreshed from the compute API (`sql_warehouses.refresh_sql_warehouse_mirror`)
    and never written by the Hub's own lifecycle actions directly (the
    3.3 client mutates the workspace; the mirror follows)."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="sql_warehouses",
        help_text="Workspace the warehouse belongs to (CASCADE — the mirror dies with the registry entry)",
    )
    warehouse_id: models.CharField = models.CharField(
        max_length=64,
        help_text="The Databricks-side warehouse id (the compute API's identity)",
    )
    name: models.CharField = models.CharField(
        max_length=255, help_text="Warehouse name (unique per workspace)"
    )
    state: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksSqlWarehouseState.choices,
        help_text="Lifecycle state as REPORTED by the compute API (never invented)",
    )
    serverless: models.BooleanField = models.BooleanField(
        default=False, help_text="Whether the warehouse is serverless"
    )
    size: models.CharField = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Classic size tier (XS/S/M/L/XL/2XL/3XL/4XL); NULL for serverless",
    )
    auto_stop_mins: models.IntegerField = models.IntegerField(
        default=30, help_text="Auto-stop after N idle minutes (the compute API's field)"
    )
    synced_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="Last refresh that touched this row (the freshness stamp)"
    )

    class Meta:
        db_table = "databricks_sql_warehouses"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "warehouse_id"],
                name="uniq_sql_warehouse_workspace_id",
            ),
            models.UniqueConstraint(
                fields=["workspace", "name"],
                name="uniq_sql_warehouse_workspace_name",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "state"]),
        ]

    def clean(self):
        super().clean()
        if self.state not in DatabricksSqlWarehouseState.values:
            raise ValidationError(
                f"Unknown warehouse state {self.state!r} — the mirror never "
                "invents a state the compute API did not report",
                code="invalid_sql_warehouse_state",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksSqlWarehouse {self.name} ({self.state})"


class UCChangeRequestComment(models.Model):
    """An approver/requester comment on a UC change request (U4 timeline).

    Request-scoped (tenant resolved through the request's workspace —
    the indirect-FK RLS chain); comments are append-only."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request: models.ForeignKey = models.ForeignKey(
        UCChangeRequest,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="The change request this comment belongs to",
    )
    author: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="uc_change_comments",
        null=True,
        blank=True,
        help_text="Comment author (SET_NULL — comments survive user deletion)",
    )
    body: models.TextField = models.TextField(help_text="Comment body (non-empty)")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "databricks_uc_change_request_comments"
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=["request", "created_at"]),
        ]

    def __str__(self):
        return f"UCChangeRequestComment on {self.request_id}"

    def clean(self):
        super().clean()
        if not (self.body or "").strip():
            raise ValidationError(
                "Comment body must be non-empty", code="invalid_uc_change_comment_body"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class UCPPrincipalType(models.TextChoices):
    """UC principal kinds the grants bridge addresses."""

    USER = "USER", "User"
    GROUP = "GROUP", "Group"
    SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL", "Service Principal"


class UCPPrincipal(models.Model):
    """A UC principal (user/group/service-principal) the bridge plans for.

    Workspace-scoped (direct workspace FK — the RLS policy resolves the
    tenant from it); (workspace, name) unique.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_principals",
    )
    name: models.CharField = models.CharField(max_length=255)
    principal_type: models.CharField = models.CharField(
        max_length=32, choices=UCPPrincipalType.choices
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "uc_principals"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "name"], name="uniq_uc_principal_workspace_name"
            ),
        ]


class UCGrantSecurableType(models.TextChoices):
    """The UC securable kinds a grant targets (the FUNCTION securable is
    UC's registered-model grant convention — D5)."""

    CATALOG = "CATALOG", "Catalog"
    SCHEMA = "SCHEMA", "Schema"
    TABLE = "TABLE", "Table"
    VIEW = "VIEW", "View"
    VOLUME = "VOLUME", "Volume"
    FUNCTION = "FUNCTION", "Function (registered model)"
    MODEL = "MODEL", "Model"


class UCGrantBindingStatus(models.TextChoices):
    """The bridge's binding lifecycle.

    OUT_OF_SYNC is the policy-shadow marker (D5): the attribute policy
    can no longer produce the grant — the operator sees the divergence,
    the bridge never guesses.
    """

    PLANNED = "PLANNED", "Planned"
    APPLIED = "APPLIED", "Applied"
    OUT_OF_SYNC = "OUT_OF_SYNC", "Out of sync (policy shadow)"
    REVOKED = "REVOKED", "Revoked"


class UCGrantBinding(models.Model):
    """An intended UC grant: principal + securable + privilege, sourced
    from an ABAC policy (``source_policy_id``) and reconciled by the
    bridge (plan → diff → apply → verify).

    One row per (workspace, principal, securable, privilege) — the
    bridge's diff operates on this grain.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="uc_grant_bindings",
    )
    principal: models.ForeignKey = models.ForeignKey(
        UCPPrincipal,
        on_delete=models.CASCADE,
        related_name="grant_bindings",
    )
    securable_type: models.CharField = models.CharField(
        max_length=32, choices=UCGrantSecurableType.choices
    )
    securable_full_name: models.CharField = models.CharField(max_length=511)
    privilege: models.CharField = models.CharField(max_length=32)
    status: models.CharField = models.CharField(
        max_length=32, choices=UCGrantBindingStatus.choices, default=UCGrantBindingStatus.PLANNED
    )
    source_policy_id: models.CharField = models.CharField(max_length=64, blank=True, default="")
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "uc_grant_bindings"
        ordering = ("securable_full_name", "principal__name", "privilege")
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "workspace",
                    "principal",
                    "securable_type",
                    "securable_full_name",
                    "privilege",
                ),
                name="uniq_uc_grant_binding_grain",
            ),
        ]


class DatabricksJobRunLifecycleState(models.TextChoices):
    """The jobs API's run lifecycle states (4.2 — the mirror maps them
    verbatim; the Hub never invents one)."""

    PENDING = "PENDING", "Pending"
    QUEUED = "QUEUED", "Queued"
    RUNNING = "RUNNING", "Running"
    TERMINATING = "TERMINATING", "Terminating"
    TERMINATED = "TERMINATED", "Terminated"
    SKIPPED = "SKIPPED", "Skipped"
    INTERNAL_ERROR = "INTERNAL_ERROR", "Internal Error"
    WAITING_FOR_RETRY = "WAITING_FOR_RETRY", "Waiting for Retry"
    BLOCKED = "BLOCKED", "Blocked"


class DatabricksJobRunResultState(models.TextChoices):
    """The jobs API's terminal result states (4.2 — reported verbatim
    when a run terminates; never invented)."""

    SUCCESS = "SUCCESS", "Success"
    FAILED = "FAILED", "Failed"
    TIMEDOUT = "TIMEDOUT", "Timed Out"
    CANCELED = "CANCELED", "Canceled"
    MAXIMUM_CONCURRENT_RUNS_REACHED = (
        "MAXIMUM_CONCURRENT_RUNS_REACHED",
        "Maximum Concurrent Runs Reached",
    )
    EXCLUDED = "EXCLUDED", "Excluded"
    SUCCESS_WITH_FAILURES = "SUCCESS_WITH_FAILURES", "Success with Failures"
    UPSTREAM_FAILED = "UPSTREAM_FAILED", "Upstream Failed"
    UPSTREAM_CANCELED = "UPSTREAM_CANCELED", "Upstream Canceled"


class DatabricksJob(models.Model):
    """A mirrored job of a registered workspace (4.2).

    The mirror is a READ cache of the Databricks-owned state: rows are
    refreshed from the jobs API (`jobs_mirror.refresh_jobs_mirror`) and
    carry the Databricks-side identity, name, task configuration, and
    schedule exactly as reported — the Hub never invents one."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="jobs",
        help_text="Workspace the job belongs to (CASCADE — the mirror dies with the registry entry)",
    )
    job_id: models.CharField = models.CharField(
        max_length=64,
        help_text="The Databricks-side job id (the jobs API's identity)",
    )
    name: models.CharField = models.CharField(
        max_length=255, help_text="Job name (the jobs API's settings.name)"
    )
    task_config: models.JSONField = models.JSONField(
        default=list,
        blank=True,
        help_text="The reported task configuration (settings.tasks)",
    )
    schedule: models.JSONField = models.JSONField(
        null=True,
        blank=True,
        help_text="The reported schedule object; NULL when unscheduled",
    )
    synced_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="Last refresh that touched this row (the freshness stamp)"
    )

    class Meta:
        db_table = "databricks_jobs"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "job_id"],
                name="uniq_databricks_job_workspace_id",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "workspace",
                ]
            ),
        ]

    def clean(self):
        super().clean()
        if not (self.job_id or "").strip():
            raise ValidationError(
                "job_id is the Databricks-side identity and must be non-empty",
                code="invalid_databricks_job_id",
            )
        if not (self.name or "").strip():
            raise ValidationError("Job name must be non-empty", code="invalid_databricks_job_name")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksJob {self.name} ({self.job_id})"


class DatabricksJobRun(models.Model):
    """A mirrored run of a mirrored job (4.2).

    Job-scoped (tenant resolved through job → workspace — the indirect-FK
    RLS chain). Lifecycle/result states are the jobs API's vocabulary
    mapped verbatim; a state the vocabulary does not know is refused —
    the mirror never invents one."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job: models.ForeignKey = models.ForeignKey(
        DatabricksJob,
        on_delete=models.CASCADE,
        related_name="runs",
        help_text="Job the run belongs to (CASCADE — runs die with the job mirror row)",
    )
    run_id: models.CharField = models.CharField(
        max_length=64,
        help_text="The Databricks-side run id (the jobs API's identity)",
    )
    lifecycle_state: models.CharField = models.CharField(
        max_length=32,
        choices=DatabricksJobRunLifecycleState.choices,
        help_text="Run lifecycle state as REPORTED by the jobs API (never invented)",
    )
    result_state: models.CharField = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        choices=DatabricksJobRunResultState.choices,
        help_text="Terminal result state as REPORTED; NULL before termination",
    )
    duration_ms: models.BigIntegerField = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Reported run_duration in milliseconds; NULL pre-terminal",
    )
    error_message: models.TextField = models.TextField(
        null=True,
        blank=True,
        help_text="The jobs API's reported state message on failure",
    )
    synced_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="Last refresh that touched this row (the freshness stamp)"
    )

    class Meta:
        db_table = "databricks_job_runs"
        ordering = ("run_id",)
        constraints = [
            models.UniqueConstraint(
                fields=["job", "run_id"],
                name="uniq_databricks_job_run_job_id",
            ),
        ]
        indexes = [
            models.Index(fields=["job", "lifecycle_state"]),
        ]

    def clean(self):
        super().clean()
        if self.lifecycle_state not in DatabricksJobRunLifecycleState.values:
            raise ValidationError(
                f"Unknown run lifecycle state {self.lifecycle_state!r} — the mirror never "
                "invents a state the jobs API did not report",
                code="invalid_databricks_job_run_lifecycle_state",
            )
        if (
            self.result_state is not None
            and self.result_state not in DatabricksJobRunResultState.values
        ):
            raise ValidationError(
                f"Unknown run result state {self.result_state!r} — the mirror never "
                "invents a state the jobs API did not report",
                code="invalid_databricks_job_run_result_state",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksJobRun {self.run_id} ({self.lifecycle_state})"


class DatabricksDltPipelineState(models.TextChoices):
    """Pipeline lifecycle as REPORTED by the pipelines API (never invented)."""

    IDLE = "IDLE", "Idle"
    ACTIVE = "ACTIVE", "Active"
    DELETING = "DELETING", "Deleting"
    FAILED = "FAILED", "Failed"
    DELETED = "DELETED", "Deleted"


class DatabricksDltChannel(models.TextChoices):
    """The DLT release channel reported by the pipelines API (10.4's
    allowlist validates it on the create path)."""

    CURRENT = "CURRENT", "Current"
    PREVIEW = "PREVIEW", "Preview"


class DatabricksDltPipeline(models.Model):
    """A mirrored DLT pipeline of a registered workspace (10.2).

    The mirror is a READ cache of the Databricks-owned state: rows are
    refreshed from the pipelines API (the 10.3 client's sync) and carry
    the Databricks-side identity, name, settings, channel, and state
    exactly as reported — the Hub never invents one."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.CASCADE,
        related_name="dlt_pipelines",
        help_text="Workspace the pipeline belongs to (CASCADE — the mirror dies with the registry entry)",
    )
    pipeline_id: models.CharField = models.CharField(
        max_length=64,
        help_text="The Databricks-side pipeline id (the pipelines API's identity)",
    )
    name: models.CharField = models.CharField(
        max_length=255, help_text="Pipeline name (the settings.name the API reports)"
    )
    state: models.CharField = models.CharField(
        max_length=32,
        choices=DatabricksDltPipelineState.choices,
        help_text="Pipeline state as REPORTED by the pipelines API (never invented)",
    )
    settings: models.JSONField = models.JSONField(
        default=dict,
        blank=True,
        help_text="The reported pipeline settings (edition/clusters/libraries/target/continuous/development/photon/notifications/catalog)",
    )
    channel: models.CharField = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        choices=DatabricksDltChannel.choices,
        help_text="The reported release channel (CURRENT/PREVIEW); NULL when the API does not report one",
    )
    synced_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="Last refresh that touched this row (the freshness stamp)"
    )

    class Meta:
        db_table = "databricks_dlt_pipelines"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "pipeline_id"],
                name="uniq_dlt_pipeline_workspace_id",
            ),
        ]
        indexes = [
            models.Index(fields=["workspace", "state"]),
        ]

    def clean(self):
        super().clean()
        if self.state not in DatabricksDltPipelineState.values:
            raise ValidationError(
                f"Unknown DLT pipeline state {self.state!r} — the mirror never "
                "invents a state the pipelines API did not report",
                code="invalid_dlt_pipeline_state",
            )
        if self.channel is not None and self.channel not in DatabricksDltChannel.values:
            raise ValidationError(
                f"Unknown DLT channel {self.channel!r} — the mirror never "
                "invents a channel the pipelines API did not report",
                code="invalid_dlt_channel",
            )
        if not (self.pipeline_id or "").strip():
            raise ValidationError(
                "pipeline_id is the Databricks-side identity and must be non-empty",
                code="invalid_dlt_pipeline_id",
            )
        if not (self.name or "").strip():
            raise ValidationError(
                "Pipeline name must be non-empty", code="invalid_dlt_pipeline_name"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksDltPipeline {self.name} ({self.pipeline_id})"


class DatabricksDltPipelineUpdateState(models.TextChoices):
    """Update lifecycle as REPORTED by the pipelines updates API (never
    invented)."""

    CREATING = "CREATING", "Creating"
    QUEUED = "QUEUED", "Queued"
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES", "Waiting for resources"
    SETTING_UP_TABLES = "SETTING_UP_TABLES", "Setting up tables"
    MAINTENANCE = "MAINTENANCE", "Maintenance"
    RUNNING = "RUNNING", "Running"
    STOPPING = "STOPPING", "Stopping"
    CANCELING = "CANCELING", "Canceling"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"
    CANCELED = "CANCELED", "Canceled"
    TIMED_OUT = "TIMED_OUT", "Timed out"


class DatabricksDltPipelineUpdate(models.Model):
    """A mirrored update of a mirrored DLT pipeline (10.2).

    Pipeline-scoped (tenant resolved through pipeline → workspace — the
    indirect-FK RLS chain). The update carries the updates API's
    reported state, the refresh semantics (full_refresh /
    refresh_selection), the events-derived DBU (10.6 fills it into the
    P7 ledger), and the reported failure message."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline: models.ForeignKey = models.ForeignKey(
        DatabricksDltPipeline,
        on_delete=models.CASCADE,
        related_name="updates",
        help_text="Pipeline the update belongs to (CASCADE — updates die with the pipeline mirror row)",
    )
    update_id: models.CharField = models.CharField(
        max_length=64,
        help_text="The Databricks-side update id (the updates API's identity)",
    )
    state: models.CharField = models.CharField(
        max_length=32,
        choices=DatabricksDltPipelineUpdateState.choices,
        help_text="Update state as REPORTED by the updates API (never invented)",
    )
    full_refresh: models.BooleanField = models.BooleanField(
        default=False, help_text="The update's full_refresh flag (10.3's start surface)"
    )
    refresh_selection: models.JSONField = models.JSONField(
        null=True,
        blank=True,
        help_text="The update's refresh_selection (selective refresh); NULL for a full pipeline refresh",
    )
    dbu: models.DecimalField = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="DBU consumed by this update as reported via the pipeline events (10.6 feeds the P7 ledger)",
    )
    error_message: models.TextField = models.TextField(
        null=True,
        blank=True,
        help_text="The updates API's reported state message on failure",
    )
    synced_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now, help_text="Last refresh that touched this row (the freshness stamp)"
    )

    class Meta:
        db_table = "databricks_dlt_pipeline_updates"
        ordering = ("update_id",)
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline", "update_id"],
                name="uniq_dlt_pipeline_update_pipeline_id",
            ),
        ]
        indexes = [
            models.Index(fields=["pipeline", "state"]),
        ]

    def clean(self):
        super().clean()
        if self.state not in DatabricksDltPipelineUpdateState.values:
            raise ValidationError(
                f"Unknown DLT update state {self.state!r} — the mirror never "
                "invents a state the updates API did not report",
                code="invalid_dlt_update_state",
            )
        if not (self.update_id or "").strip():
            raise ValidationError(
                "update_id is the Databricks-side identity and must be non-empty",
                code="invalid_dlt_update_id",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksDltPipelineUpdate {self.update_id} ({self.state})"


class DeltaShareRecipient(models.Model):
    """A named consumer recipient of the Delta Sharing server (task 5.2).

    Tenant-scoped (direct FK — the 5.1 design D1): the recipient registry
    is Hub-owned; a recipient is who a share is served TO. The tenant/name
    pair is unique per tenant. RLS: direct-FK policy, paired migration
    (0025) per the CLAUDE.md contract."""

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="databricks_delta_share_recipients",
        help_text="Owning tenant (PROTECT — a tenant with recipients cannot be deleted)",
    )
    name: models.CharField = models.CharField(
        max_length=255,
        help_text="Recipient name (unique per tenant)",
    )
    comment: models.TextField = models.TextField(
        blank=True,
        default="",
        help_text="Free-form note (who the consumer is, what they receive)",
    )
    created_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Hub user who provisioned the recipient",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_delta_share_recipients"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"],
                name="uniq_datashare_recipient_tenant_name",
            ),
        ]

    def clean(self):
        super().clean()
        if not (self.name or "").strip():
            raise ValidationError(
                "Recipient name must be non-empty",
                code="invalid_datashare_recipient_name",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DeltaShareRecipient {self.name} ({self.tenant_id})"


class DeltaShareToken(models.Model):
    """A bearer token for a Delta Sharing recipient (task 5.2).

    The API-key store pattern: the PLAINTEXT is generated by ``issue()``
    and returned EXACTLY ONCE; the row stores only ``sha256_hex(plaintext)``
    (``token_hash``) plus the first 8 plaintext chars as a display prefix
    (``token_prefix`` — never sufficient to authenticate). The scope is a
    share/schema/table triple: ``schema_name``/``table_name`` are NULL
    wildcards (NULL schema = every schema in the share; a table scope
    requires its schema). ``tenant`` is DENORMALIZED from the recipient
    for the direct-FK RLS policy — ``clean()`` pins the two equal, so the
    denormalized copy can never drift.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="databricks_delta_share_tokens",
        help_text=(
            "Denormalized tenant copy (must equal recipient.tenant) — direct-FK RLS on this table"
        ),
    )
    recipient: models.ForeignKey = models.ForeignKey(
        DeltaShareRecipient,
        on_delete=models.CASCADE,
        related_name="tokens",
        help_text="Owning recipient (CASCADE — tokens die with the recipient)",
    )
    token_hash: models.CharField = models.CharField(
        max_length=64,
        help_text="sha256 hex of the bearer token — the plaintext is never stored",
    )
    token_prefix: models.CharField = models.CharField(
        max_length=8,
        help_text="First 8 plaintext chars, for display only (never authenticates)",
    )
    share_name: models.CharField = models.CharField(
        max_length=255,
        help_text="The share this token may read",
    )
    schema_name: models.CharField = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Schema scope; NULL = every schema in the share",
    )
    table_name: models.CharField = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Table scope (requires a schema scope); NULL = every table in the schema",
    )
    created_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The Hub user who issued the token",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Expiry; NULL = never expires (the auth layer enforces)",
    )
    last_used_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last authenticated use (stamped by the 5.3 auth layer)",
    )

    class Meta:
        db_table = "databricks_delta_share_tokens"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "token_hash",
                ],
                name="uniq_datashare_token_hash",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "recipient",
                ]
            ),
        ]

    def clean(self):
        super().clean()
        # Only comparable when the recipient carries its tenant (a saved
        # recipient); an unsaved recipient skips the consistency guard.
        if self.recipient.tenant_id is not None and self.tenant_id != self.recipient.tenant_id:
            raise ValidationError(
                "The token's tenant must equal the recipient's tenant — the "
                "denormalized copy feeds the RLS policy and can never drift",
                code="invalid_datashare_token_tenant",
            )
        if len(self.token_hash) != 64 or any(c not in "0123456789abcdef" for c in self.token_hash):
            raise ValidationError(
                "token_hash must be the 64-char lowercase sha256 hex digest",
                code="invalid_datashare_token_hash",
            )
        if len(self.token_prefix or "") != 8:
            raise ValidationError(
                "token_prefix must be exactly the first 8 plaintext chars",
                code="invalid_datashare_token_prefix",
            )
        if not (self.share_name or "").strip():
            raise ValidationError(
                "share_name must be non-empty — a token always names its share",
                code="invalid_datashare_share_name",
            )
        if not self.schema_name and self.table_name:
            raise ValidationError(
                "A table scope requires a schema scope (schema_name cannot be "
                "NULL while table_name is set)",
                code="invalid_datashare_token_scope",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @classmethod
    def issue(
        cls,
        *,
        recipient: DeltaShareRecipient,
        share_name: str,
        schema_name: str | None = None,
        table_name: str | None = None,
        tenant=None,
        created_by=None,
        expires_at=None,
    ) -> tuple[DeltaShareToken, str]:
        """Issue a token: generate the plaintext, store ONLY its sha256
        hash + the display prefix, and return the plaintext exactly once
        (the API-key store pattern)."""
        import secrets

        from hub.apps.auth.utils import sha256_hex

        plaintext = secrets.token_urlsafe(32)
        token = cls.objects.create(
            tenant=tenant or recipient.tenant,
            recipient=recipient,
            token_hash=sha256_hex(plaintext),
            token_prefix=plaintext[:8],
            share_name=share_name,
            schema_name=schema_name,
            table_name=table_name,
            created_by=created_by,
            expires_at=expires_at,
        )
        return token, plaintext

    @classmethod
    def resolve(cls, plaintext: str) -> DeltaShareToken | None:
        """Resolve a presented bearer token to its row by hashing the
        plaintext (the ONLY lookup path — the plaintext is never stored).
        Expiry is NOT checked here: the auth layer (5.3) owns that
        decision; this lookup is pure identity resolution."""
        from hub.apps.auth.utils import sha256_hex

        return (
            cls.objects.select_related("recipient").filter(token_hash=sha256_hex(plaintext)).first()
        )

    def __str__(self):
        return f"DeltaShareToken {self.token_prefix}… ({self.recipient.name})"


class DeltaShareSnapshot(models.Model):
    """A materialized Parquet snapshot of a share table (task 5.3).

    The DATA-mode substrate: task 5.4's snapshot job (JobType
    DATABRICKS_DELTA_SHARE_SNAPSHOT) materializes Parquet + delta-log
    into Hub S3 and stamps this row; the 5.3 version endpoint serves the
    row's files as presigned URL actions. TTL discipline: ``expires_at``
    bounds serving — a NULL expires_at is treated as EXPIRED by the
    serving side (fail-closed: a snapshot without a TTL stamp is never
    served). Tenant-scoped direct FK with a paired RLS policy (0027).
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.PROTECT,
        related_name="databricks_delta_share_snapshots",
        help_text="Owning tenant (direct-FK RLS)",
    )
    share_name: models.CharField = models.CharField(
        max_length=255,
        help_text="The share this snapshot serves",
    )
    schema_name: models.CharField = models.CharField(
        max_length=255,
        help_text="The schema (the asset's id.hex)",
    )
    table_name: models.CharField = models.CharField(
        max_length=255,
        help_text="The table (the asset's external table ref)",
    )
    version: models.BigIntegerField = models.BigIntegerField(
        help_text="The materialized source version (the delta-table-version header)",
    )
    files: models.JSONField = models.JSONField(
        default=list,
        blank=True,
        help_text="Snapshot files: [{id, path, size, partition_values}] in Hub S3",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    expires_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="TTL stamp; NULL is treated as EXPIRED by the serving side (fail-closed)",
    )

    class Meta:
        db_table = "databricks_delta_share_snapshots"
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(
                fields=["share_name", "schema_name", "table_name", "version"],
                name="uniq_datashare_snapshot_grain",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "share_name", "schema_name", "table_name"]),
        ]

    def clean(self):
        super().clean()
        if not (self.share_name or "").strip():
            raise ValidationError(
                "share_name must be non-empty",
                code="invalid_datashare_snapshot_share",
            )
        if not (self.schema_name or "").strip():
            raise ValidationError(
                "schema_name must be non-empty",
                code="invalid_datashare_snapshot_schema",
            )
        if not (self.table_name or "").strip():
            raise ValidationError(
                "table_name must be non-empty",
                code="invalid_datashare_snapshot_table",
            )
        if self.version < 0:
            raise ValidationError(
                "version must be a non-negative integer",
                code="invalid_datashare_snapshot_version",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"DeltaShareSnapshot {self.share_name}/{self.schema_name[:8]}/"
            f"{self.table_name} v{self.version}"
        )


# ── P7 — Databricks cost guardrails (openspec add-databricks-cost-guardrails 7.2) ──


class DatabricksCostBudgetEnforcementMode(models.TextChoices):
    """The per-budget enforcement mode (design D3 — the mode rides the
    budget row, no new tenant flags)."""

    BLOCK = "BLOCK", "Block queries over budget"
    ALERT = "ALERT", "Alert only (never block)"


class DatabricksCostBudget(models.Model):
    """P7 (7.2) — a per-tenant Databricks cost budget (design D1).

    ``budget_units_per_hour`` NULL = unlimited (the default). A
    warehouse-scoped row budgets ONLY that warehouse; a tenant-wide row
    (``warehouse`` NULL) covers the whole tenant — the (tenant, warehouse)
    pair is unique with NULLS NOT DISTINCT so exactly one tenant-wide row
    can exist. The tenant FK is the direct RLS key (the CLAUDE.md pairing
    contract — the policy ships in the same migration).
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="databricks_cost_budgets",
        help_text="Tenant the budget governs (the direct RLS key)",
    )
    warehouse: models.ForeignKey = models.ForeignKey(
        DatabricksSqlWarehouse,
        on_delete=models.SET_NULL,
        related_name="cost_budgets",
        null=True,
        blank=True,
        help_text="Per-warehouse scope; NULL = tenant-wide",
    )
    budget_units_per_hour: models.DecimalField = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Budget units per rolling hour; NULL = unlimited",
    )
    unit_label: models.CharField = models.CharField(
        max_length=32,
        default="DBU",
        help_text="The billing unit the budget counts (Databricks DBU by default)",
    )
    enforcement_mode: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksCostBudgetEnforcementMode.choices,
        default=DatabricksCostBudgetEnforcementMode.BLOCK,
        help_text="BLOCK (429 fail-closed over budget) or ALERT (warn-only)",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "databricks_cost_budgets"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "warehouse"],
                nulls_distinct=False,
                name="uniq_cost_budget_tenant_warehouse",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "warehouse"]),
        ]

    def clean(self):
        super().clean()
        if self.budget_units_per_hour is not None and self.budget_units_per_hour <= 0:
            raise ValidationError(
                "budget_units_per_hour must be positive (or NULL for unlimited)",
                code="invalid_cost_budget_units",
            )
        if self.enforcement_mode not in DatabricksCostBudgetEnforcementMode.values:
            raise ValidationError(
                f"Unknown enforcement mode {self.enforcement_mode!r}",
                code="invalid_cost_budget_enforcement_mode",
            )
        if self.warehouse_id and self.warehouse.workspace.tenant_id != self.tenant_id:
            raise ValidationError(
                "the budget's warehouse must belong to the budget's tenant",
                code="cross_tenant_cost_budget_warehouse",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        scope = str(self.warehouse_id) if self.warehouse_id else "tenant-wide"
        return f"DatabricksCostBudget {scope} ({self.budget_units_per_hour})"


class DatabricksCostLedgerSource(models.TextChoices):
    """The ledger's source attribution (design D1/D4 — one row per
    executed query, tagged by the movement source)."""

    QUERY = "query", "Warehouse query"
    EXPORT = "export", "dlt export"
    INGESTION = "ingestion", "dlt ingestion"
    JOB = "job", "Databricks job"
    BILLING_SYNC = "billing_sync", "system.billing.usage sync"
    DLT_UPDATE = "dlt_update", "DLT update estimate"
    # Phase 11 (run-transformation-on-databricks 11.4) — the dbt run's
    # stored estimate (one row per run, the transformation cost leg).
    DBT_RUN = "dbt_run", "dbt run estimate"


class DatabricksCostLedger(models.Model):
    """P7 (7.2) — the append-only cost ledger (design D1/D4).

    ONE row per executed query with the source attribution; the
    ``system.billing.usage`` sync appends the billed truth. The ledger is
    the SINGLE source of truth for every cost decision. Append-only by
    contract — production code has no update path (the rows are only ever
    created). The tenant FK is the direct RLS key.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant: models.ForeignKey = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="databricks_cost_ledger",
        help_text="Tenant the cost belongs to (the direct RLS key)",
    )
    workspace: models.ForeignKey = models.ForeignKey(
        DatabricksWorkspace,
        on_delete=models.SET_NULL,
        related_name="cost_ledger",
        null=True,
        blank=True,
        help_text="The workspace that burned the cost (SET_NULL preserves the ledger)",
    )
    warehouse: models.ForeignKey = models.ForeignKey(
        DatabricksSqlWarehouse,
        on_delete=models.SET_NULL,
        related_name="cost_ledger",
        null=True,
        blank=True,
        help_text="The SQL warehouse that burned the cost (SET_NULL preserves the ledger)",
    )
    source: models.CharField = models.CharField(
        max_length=20,
        choices=DatabricksCostLedgerSource.choices,
        help_text=("The attribution source (query/export/ingestion/job/billing_sync/dlt_update)"),
    )
    units: models.DecimalField = models.DecimalField(
        max_digits=18, decimal_places=6, help_text="Cost units consumed"
    )
    unit_label: models.CharField = models.CharField(
        max_length=32, default="DBU", help_text="The billing unit label"
    )
    recorded_at: models.DateTimeField = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the cost was recorded (the window reads this)",
    )
    meta: models.JSONField = models.JSONField(
        null=True, blank=True, default=dict, help_text="Attribution payload (query id, run id, ...)"
    )

    class Meta:
        db_table = "databricks_cost_ledger"
        ordering = ("recorded_at",)
        indexes = [
            models.Index(fields=["tenant", "recorded_at"]),
            models.Index(fields=["tenant", "warehouse", "recorded_at"]),
            models.Index(fields=["workspace", "recorded_at"]),
        ]

    def clean(self):
        super().clean()
        if self.source not in DatabricksCostLedgerSource.values:
            raise ValidationError(
                f"Unknown cost source {self.source!r}",
                code="invalid_cost_ledger_source",
            )
        if self.units < 0:
            raise ValidationError(
                "units must be non-negative",
                code="invalid_cost_ledger_units",
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"DatabricksCostLedger {self.source} {self.units} {self.unit_label}"


class DatabricksAccount(EncryptedConfigModelMixin, models.Model):
    """P8 (openspec add-databricks-account-plane task 8.2) — the platform's
    link to a Databricks ACCOUNT (the account console, above workspaces).

    PLATFORM table — deliberately NO tenant FK and therefore NO RLS policy.
    The CLAUDE.md pairing contract scopes to models WITH ``tenant_id``; this
    table is exempt BY DESIGN, not by omission: one Databricks account hosts
    many tenants' workspaces, so tenant RLS has nothing to filter on. The
    safety boundary is admin-DB confinement — every read/write routes
    through ``DATABASES["admin"]`` (meshant_admin, BYPASSRLS) via the
    forced-alias ``AdminDatabaseManager`` below — plus the platform-admin
    RBAC gate on the account API surface (tasks 8.3+). Tenant-scoped code
    paths MUST never read this table; this docstring is the documented
    exemption the design (D1) pins.

    The account-level admin credential is stored encrypted at rest (the
    workspace-credential Fernet convention — ciphertext in the ``config``
    column via ``EncryptedConfigModelMixin``, decrypted only at
    client-build time through ``get_config()``). The provisioning signoff
    (design D3) is recorded on the row: provisioning external infrastructure
    requires BOTH the tenant flag and a complete DPO/Legal signoff record —
    ``record_provisioning_signoff()`` writes the attribution fields
    (refusing a blank evidence URL) and ``has_provisioning_signoff()`` is
    the 8.3 refusal gate's completeness predicate.
    """

    id: models.UUIDField = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account_id: models.UUIDField = models.UUIDField(
        unique=True,
        help_text="The Databricks account UUID (account console) — the platform link key",
    )
    display_name: models.CharField = models.CharField(
        max_length=255,
        help_text="Human-readable account name shown to platform admins",
    )
    config: models.JSONField = models.JSONField(
        default=dict,
        help_text="Encrypted account-level admin credential (Fernet wrapper — never plaintext)",
    )
    provisioning_signoff_by: models.ForeignKey = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        related_name="databricks_account_signoffs",
        null=True,
        blank=True,
        help_text="The platform admin who recorded the DPO/Legal signoff (SET_NULL keeps the legal record if the user is deleted)",
    )
    provisioning_signoff_at: models.DateTimeField = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the DPO/Legal signoff was recorded (design D3)",
    )
    provisioning_signoff_evidence_url: models.CharField = models.CharField(
        max_length=1024,
        blank=True,
        default="",
        help_text="Link to the DPO/Legal signoff evidence (ticket/approval document)",
    )
    created_at: models.DateTimeField = models.DateTimeField(auto_now_add=True)
    updated_at: models.DateTimeField = models.DateTimeField(auto_now=True)

    objects = AdminDatabaseManager()

    class Meta:
        db_table = "databricks_accounts"
        ordering = ("-created_at",)

    def __str__(self):
        return f"DatabricksAccount {self.display_name} ({self.account_id})"

    def record_provisioning_signoff(self, user, evidence_url: str) -> None:
        """Design D3 — record the DPO/Legal signoff attribution on the row.

        Fail-closed at RECORD time: a blank evidence URL is refused (an
        unstructured signoff fails the "documented" requirement). Persists
        the three fields; the caller owns the admin-alias atomic boundary.
        """
        evidence_url = (evidence_url or "").strip()
        if not evidence_url:
            raise ValueError(
                "DatabricksAccount provisioning signoff requires an evidence URL (design D3)"
            )
        self.provisioning_signoff_by = user
        self.provisioning_signoff_at = timezone.now()
        self.provisioning_signoff_evidence_url = evidence_url
        self.save(
            update_fields=[
                "provisioning_signoff_by",
                "provisioning_signoff_at",
                "provisioning_signoff_evidence_url",
            ]
        )

    def has_provisioning_signoff(self) -> bool:
        """True when a COMPLETE DPO/Legal signoff record exists (design D3 —
        all three fields; the 8.3 refusal gate fails closed on anything less)."""
        return (
            self.provisioning_signoff_by_id is not None
            and self.provisioning_signoff_at is not None
            and bool(self.provisioning_signoff_evidence_url)
        )
