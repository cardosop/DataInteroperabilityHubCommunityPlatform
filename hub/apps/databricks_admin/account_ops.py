"""P8 (openspec add-databricks-account-plane task 8.3, design D3/D4) — the
provisioning service: metastore ops + workspace provisioning through the
account API.

The D3 triple — EVERY provisioning request is refused with 403
``DATABRICKS_PROVISIONING_SIGNOFF_MISSING`` / ``DATABRICKS_WORKSPACE_PROVISIONING_DISABLED``
and ZERO network calls unless BOTH the target tenant's
``databricks_workspace_provisioning_enabled`` flag is ON and a COMPLETE
DPO/Legal signoff is recorded on the account row (the signoff check runs
FIRST — the legal prerequisite; creating external infrastructure is a
legal act, not an admin convenience). The gate is uniform across the
metastore and workspace surfaces.

A provisioned workspace attaches to the tenant through the EXISTING
registry validation — the ``DatabricksWorkspace`` row is built from the
account API's envelope and saved under ``tenant_context`` (the RLS WITH
CHECK sees the target tenant's GUC) with ``full_clean()`` running the
host SSRF + region residency validators — never bypassed.

The sanctioned transport seam is ``client_factory`` (the 7.3
``_local_client_factory`` pattern): the production default builds the
``DatabricksAccountClient`` against the ACCOUNT host from the account's
decrypted credential; tests inject a factory pointing the SAME client at
a real local account-API server.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import structlog
from rest_framework.exceptions import PermissionDenied

logger = structlog.get_logger(__name__)

from hub.apps.databricks_admin.account_client import DatabricksAccountClient
from hub.apps.databricks_admin.client import DatabricksApiError

# The uniform refusal codes (catalogued in docs/api/error-codes.md).
CODE_SIGNOFF_MISSING = "DATABRICKS_PROVISIONING_SIGNOFF_MISSING"
CODE_PROVISIONING_DISABLED = "DATABRICKS_WORKSPACE_PROVISIONING_DISABLED"


class ProvisioningSignoffMissing(PermissionDenied):
    """403 — the account row carries no COMPLETE DPO/Legal signoff.

    The code is a CLASS attribute (the warehouses ``_WarehouseTypeDisabled``
    convention): DRF 3.16 dropped the instance ``code`` attribute, and the
    repo's exception handler reads the class attribute into the envelope —
    a constructor ``code=`` kwarg would collapse to ``AUTH_FORBIDDEN``.
    """

    status_code = 403
    code = CODE_SIGNOFF_MISSING
    default_detail = (
        "Databricks workspace provisioning requires a recorded DPO/Legal "
        "signoff on the account row (design D3)."
    )


class ProvisioningDisabled(PermissionDenied):
    """403 — the target tenant's provisioning flag is OFF."""

    status_code = 403
    code = CODE_PROVISIONING_DISABLED
    default_detail = (
        "Databricks workspace provisioning is not enabled for this tenant "
        "(design D3 — registration-first stays the default)."
    )


def _default_client_factory(account) -> DatabricksAccountClient:
    """The production transport — the ACCOUNT host with the account's
    decrypted credential. A module-level seam so tests redirect the same
    client at a real local account-API server (the 7.4 recorder
    convention)."""
    return DatabricksAccountClient(str(account.account_id), account.get_config())


def _build_client(account, client_factory=None) -> DatabricksAccountClient:
    factory = client_factory or _default_client_factory
    return factory(account)


def _emit_audit(*, resource_type, action, tenant, resource_id, details, result="SUCCESS") -> None:
    """D5 — best-effort audit emission: an audit-DB outage never blocks
    the operation (the Phase 273 discipline; the workspace surface's
    ``_emit_audit`` pattern)."""
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type=resource_type,
            action=action,
            tenant=tenant,
            resource_id=resource_id,
            result=result,
            details=details,
        )
    except Exception:
        logger.warning("databricks_account_audit_failed", action=action)


def link_account(*, account_id: str, display_name: str, credential_config: dict):
    """D1 — link the platform's Databricks account: the row (encrypted
    credential via the shared mixin) + the ``DATABRICKS_ACCOUNT_LINKED``
    event with the account ids."""
    from hub.apps.audit.event_types import DATABRICKS_ACCOUNT_LINKED
    from hub.apps.databricks_admin.models import DatabricksAccount

    if not isinstance(account_id, str) or not account_id.strip():
        raise ValueError("account_id is required to link an account")
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("display_name is required to link an account")
    if (
        not isinstance(credential_config, dict)
        or not (credential_config.get("token") or "").strip()
    ):
        raise ValueError("the account credential config requires a 'token' value")

    account = DatabricksAccount(account_id=account_id.strip(), display_name=display_name.strip())
    account.set_config(dict(credential_config))
    account.save()
    _emit_audit(
        resource_type="DATABRICKS_ACCOUNT",
        action=DATABRICKS_ACCOUNT_LINKED,
        tenant=None,
        resource_id=str(account.id),
        details={"account_id": str(account.account_id), "display_name": account.display_name},
    )
    return account


def check_provisioning_allowed(account, tenant) -> None:
    """The D3 triple. Raises the classified 403 — NEVER a network call.
    The signoff check runs FIRST (the legal prerequisite); the flag check
    runs second."""
    if not account.has_provisioning_signoff():
        raise ProvisioningSignoffMissing()
    if not bool(getattr(tenant, "databricks_workspace_provisioning_enabled", False)):
        raise ProvisioningDisabled()


def provision_metastore(
    account,
    tenant,
    *,
    name: str,
    region: str,
    storage_root: str | None = None,
    client_factory=None,
) -> dict:
    """Create a metastore through the account API (the uniform D3 gate),
    then emit ``DATABRICKS_METASTORE_CREATED`` (D5, best-effort)."""
    check_provisioning_allowed(account, tenant)
    envelope = _build_client(account, client_factory).create_metastore(name, region, storage_root)
    _emit_audit(
        resource_type="DATABRICKS_ACCOUNT",
        action="DATABRICKS_METASTORE_CREATED",
        tenant=None,
        resource_id=str(account.id),
        details={
            "account_id": str(account.account_id),
            "metastore_id": envelope.get("metastore_id"),
            "name": envelope.get("name", name),
            "region": envelope.get("region", region),
            "tenant_id": str(tenant.id),
        },
    )
    return envelope


def provision_workspace(
    account,
    tenant,
    *,
    workspace_name: str,
    aws_region: str,
    deployment_name: str | None = None,
    pricing_tier: str | None = None,
    client_factory=None,
):
    """Provision a workspace through the account API and attach the
    registry row to the target tenant (the EXISTING validation chain —
    host SSRF + region residency — never bypassed)."""
    if not isinstance(aws_region, str) or not aws_region.strip():
        raise ValueError("aws_region is required to provision a workspace")
    check_provisioning_allowed(account, tenant)
    envelope = _build_client(account, client_factory).create_workspace(
        workspace_name,
        deployment_name=deployment_name,
        aws_region=aws_region.strip(),
        pricing_tier=pricing_tier,
    )
    workspace = _attach_workspace(
        tenant, envelope, workspace_name=workspace_name, aws_region=aws_region
    )
    _emit_audit(
        resource_type="DATABRICKS_WORKSPACE",
        action="DATABRICKS_WORKSPACE_PROVISIONED",
        tenant=workspace.tenant,
        resource_id=str(workspace.id),
        details={
            "account_id": str(account.account_id),
            "workspace_id": envelope.get("workspace_id"),
            "deployment_name": envelope.get("deployment_name"),
            "tenant_id": str(tenant.id),
        },
    )
    return workspace


def _attach_workspace(tenant, envelope: dict, *, workspace_name: str, aws_region: str):
    """Build + persist the registry row from the account API envelope.

    The envelope's ``workspace_url`` is the ONLY transport value trusted
    from the remote — and it still passes the registry's host validators
    (the *.cloud.databricks.com family + DNS re-resolution) exactly like a
    BYO registration. The save runs under ``tenant_context`` so the
    workspace table's RLS WITH CHECK sees the target tenant's GUC (the
    CLAUDE.md worker contract).
    """
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace
    from hub.apps.tenants.request_tenant import tenant_context

    workspace_url = envelope.get("workspace_url") or ""
    host = urlsplit(workspace_url).hostname or ""
    if not host:
        raise DatabricksApiError(
            "the account API's workspace envelope carries no usable workspace_url",
        )
    workspace = DatabricksWorkspace(
        tenant=tenant,
        name=workspace_name.strip(),
        host=host,
        cloud=DatabricksCloud.AWS,
        region=aws_region.strip(),
    )
    with tenant_context(str(tenant.id)):
        workspace.full_clean()  # SSRF + residency — the EXISTING registry validation
        workspace.save()
    return workspace
