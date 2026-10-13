"""Hub-user ↔ Databricks-principal binding service (task 0b.3).

First-login provisioning by (sub, email), per-workspace binding, and the
multi-workspace chooser helpers. The OBO token vault (0b.4) and the OBO
bearer resolution (0b.5) consume ``resolve_binding``; the SSO callback
(0b.12+ views) consumes ``provision_binding``.

All querysets are tenant-scoped — cross-tenant resolution returns None /
raises DoesNotExist, never a foreign row.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksUserBinding,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)


class DatabricksBindingConflict(RuntimeError):
    """The Databricks principal is already bound to a DIFFERENT Hub account
    on this workspace — first-login provisioning must not re-point it."""

    def __init__(self, workspace_name: str):
        super().__init__(
            "This Databricks account is already bound to another Hub user "
            f"on workspace '{workspace_name}'."
        )
        self.code = "DATABRICKS_PRINCIPAL_ALREADY_BOUND"


def resolve_binding(*, user, workspace) -> DatabricksUserBinding | None:
    """Return the binding for (user, workspace), if any.

    Workspace-keyed by construction — a binding on another workspace is
    never returned here (the per-workspace isolation guarantee).
    """
    return DatabricksUserBinding.objects.filter(user=user, workspace=workspace).first()


def provision_binding(
    *,
    tenant,
    user,
    workspace,
    databricks_sub: str,
    databricks_email: str,
) -> DatabricksUserBinding:
    """First-login provisioning by (sub, email); idempotent on relogin.

    - A principal already bound to a DIFFERENT Hub account on this
      workspace raises ``DatabricksBindingConflict`` (impersonation guard).
    - The same Hub user relogging-in with the same sub updates the email
      (identity continuity by email).
    - The same Hub user with a RE-CREATED principal (new sub, same email)
      updates the sub — the (user, workspace) key wins.
    """
    # Cross-tenant consistency: the row must carry the workspace's tenant
    # and belong to a user from the SAME tenant — a foreign user would
    # create an RLS-visible binding row under the wrong tenant.
    if str(getattr(user, "tenant_id", "")) != str(workspace.tenant_id) or str(tenant.id) != str(
        workspace.tenant_id
    ):
        raise ValueError(
            "provision_binding requires user and tenant to match the workspace's tenant"
        )

    # Guard: principal exclusivity per workspace.
    existing_by_sub = DatabricksUserBinding.objects.filter(
        workspace=workspace, databricks_sub=databricks_sub
    ).first()
    if existing_by_sub is not None and existing_by_sub.user_id != user.id:
        raise DatabricksBindingConflict(workspace.name)

    with transaction.atomic():
        binding = (
            DatabricksUserBinding.objects.select_for_update()
            .filter(user=user, workspace=workspace)
            .first()
        )
        if binding is None:
            try:
                binding = DatabricksUserBinding.objects.create(
                    tenant=tenant,
                    user=user,
                    workspace=workspace,
                    databricks_sub=databricks_sub,
                    databricks_email=databricks_email,
                )
            except IntegrityError:
                # TOCTOU belt-and-braces: the sub-exclusivity pre-check
                # passed but a concurrent first-login won the (workspace,
                # sub) slot — the DB constraint caught what the check
                # missed. Surface the SAME clean conflict, never a raw 500.
                raise DatabricksBindingConflict(workspace.name) from None
        elif (
            binding.databricks_sub != databricks_sub or binding.databricks_email != databricks_email
        ):
            binding.databricks_sub = databricks_sub
            binding.databricks_email = databricks_email
            binding.save(update_fields=["databricks_sub", "databricks_email", "updated_at"])
        return binding


def sso_workspace_options(tenant) -> list[DatabricksWorkspace]:
    """Workspaces eligible for the SSO chooser: this tenant's ACTIVE ones,
    EXCLUDING GCP — U2M is unsupported there (task 0b.8: the SSO attempt
    surfaces DATABRICKS_SSO_UNAVAILABLE; execution falls back to the
    PAT/M2M credential)."""
    return list(
        DatabricksWorkspace.objects.filter(
            tenant=tenant,
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        .exclude(cloud=DatabricksCloud.GCP)
        .order_by("name")
    )


def select_workspace(*, tenant, workspace_id) -> DatabricksWorkspace:
    """Resolve a chosen workspace id for the tenant — cross-tenant or
    unknown ids raise ``DatabricksWorkspace.DoesNotExist`` (RLS-scoped)."""
    return DatabricksWorkspace.objects.get(tenant=tenant, id=workspace_id)
