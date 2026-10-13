"""Hybrid identity enforcement — D12 (openspec add-databricks-control-plane
task 0b.6).

One decision point for every Databricks execution:

- INTERACTIVE purposes (live queries, catalog browse, DDL execution,
  job run-now) REQUIRE an OBO provider — the per-request identity from
  the authenticated Hub session. Without one the resolution FAILS CLOSED
  (``DatabricksOBOError`` / ``DATABRICKS_OBO_REFRESH_FAILED``) even when
  an M2M credential is available; a credential passed alongside is
  ignored. UC enforces the user's grants natively; Databricks audit logs
  show the real user.
- BACKGROUND purposes (UC sync, cost sync, scheduled exports, deferred
  DDL) resolve the workspace's M2M credential WITH approver-chain audit
  linkage — the emitted audit row carries the approval-request id and the
  chain snapshot so every service-identity execution traces back to the
  human approvals (Phase 272).
- Unknown purposes default-deny.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from hub.apps.databricks_admin.client import DatabricksOBOError
from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksCredentialAuthMode

INTERACTIVE_PURPOSES = frozenset(
    {
        "live_query",
        "catalog_browse",
        "ddl_execution",
        "job_run_now",
        "grant_apply",
        # 3.7 — the SQL-warehouse lifecycle actions (start/stop) are
        # user-initiated control-plane ops: OBO required on interactive
        # paths, never a service-credential fallback.
        "warehouse_lifecycle",
    }
)
BACKGROUND_PURPOSES = frozenset(
    {
        "uc_sync",
        "cost_sync",
        "scheduled_export",
        "deferred_ddl",
        "delta_sharing_json",
        "uc_change_reaper",  # 2.5 — the stuck-EXECUTING reaper's compensating DDL
    }
)


class HybridIdentityError(RuntimeError):
    """D12 contract violation — carries a stable code for the error
    catalogue (``DATABRICKS_HYBRID_IDENTITY_VIOLATION``)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "DATABRICKS_HYBRID_IDENTITY_VIOLATION"


@dataclass
class ResolvedIdentity:
    """The outcome of the D12 decision point."""

    kind: str  # "obo" | "m2m"
    purpose: str
    workspace_id: str
    obo_provider: Any | None = None
    credential: Any | None = None
    approval_linkage: dict | None = field(default=None)

    @property
    def credential_id(self):
        return self.credential.id if self.credential is not None else None


def _approval_linkage(approval_request) -> dict:
    workflow = list(approval_request.approval_workflow or [])
    return {
        "approval_request_id": str(approval_request.id),
        "approver_chain": workflow,
    }


def _emit_resolution_audit(
    *,
    tenant,
    workspace,
    purpose: str,
    identity: ResolvedIdentity,
) -> None:
    """Best-effort audit of the identity decision (audit-DB outage never
    blocks execution)."""
    import logging

    logger = logging.getLogger(__name__)
    try:
        from hub.apps.audit.utils import create_audit_event

        details = {"purpose": purpose, "kind": identity.kind}
        if identity.approval_linkage:
            details.update(identity.approval_linkage)
        create_audit_event(
            resource_type="DATABRICKS_EXECUTION_IDENTITY",
            action="RESOLVED",
            tenant=tenant,
            resource_id=str(workspace.id),
            result="SUCCESS",
            details=details,
        )
    except Exception:
        logger.warning(
            "databricks_identity_audit_failed",
            extra={"purpose": purpose},
        )


def resolve_execution_identity(
    *,
    purpose: str,
    workspace,
    obo_provider: Any | None = None,
    credential: Any | None = None,
    approval_request: Any | None = None,
) -> ResolvedIdentity:
    """The D12 decision point. Returns the identity the caller must build
    its ``DatabricksApiClient`` from, or raises (fail-closed / violation).
    """
    if purpose in INTERACTIVE_PURPOSES:
        # GCP fallback (0b.8): U2M is unsupported — interactive execution
        # runs on the workspace PAT/M2M credential instead of OBO. The
        # credential is REQUIRED (fail-closed when absent); no approver
        # linkage is needed (this is a user-initiated action, not a
        # background job).
        if getattr(workspace, "cloud", None) == DatabricksCloud.GCP:
            if credential is None:
                raise HybridIdentityError(
                    f"Interactive purpose '{purpose}' on a GCP workspace "
                    "requires the workspace credential (U2M unsupported, "
                    "task 0b.8)."
                )
            # Same ownership guard as the background branch — a foreign
            # workspace's credential is never a valid identity. Unlike
            # background, PAT is accepted: the GCP fallback path allows
            # PAT or M2M (U2M unsupported).
            if str(getattr(credential, "workspace_id", "")) != str(workspace.id) or getattr(
                credential, "auth_mode", ""
            ) not in (
                DatabricksCredentialAuthMode.PAT,
                DatabricksCredentialAuthMode.OAUTH_M2M,
            ):
                raise HybridIdentityError(
                    f"Interactive purpose '{purpose}' on a GCP workspace "
                    "requires the workspace's own PAT/M2M credential."
                )
            identity = ResolvedIdentity(
                kind="m2m",
                purpose=purpose,
                workspace_id=str(workspace.id),
                credential=credential,
                approval_linkage={"gcp_fallback": True},
            )
            _emit_resolution_audit(
                tenant=workspace.tenant,
                workspace=workspace,
                purpose=purpose,
                identity=identity,
            )
            return identity

        # OBO REQUIRED — a service credential is never a fallback here.
        if obo_provider is None:
            raise DatabricksOBOError(
                f"Interactive purpose '{purpose}' requires an On-Behalf-Of "
                "token for this workspace — sign in with Databricks "
                "(fail-closed; no service-credential fallback)."
            )
        identity = ResolvedIdentity(
            kind="obo",
            purpose=purpose,
            workspace_id=str(workspace.id),
            obo_provider=obo_provider,
        )
        _emit_resolution_audit(
            tenant=workspace.tenant, workspace=workspace, purpose=purpose, identity=identity
        )
        return identity

    if purpose in BACKGROUND_PURPOSES:
        if credential is None:
            raise HybridIdentityError(
                f"Background purpose '{purpose}' requires the workspace M2M "
                "credential (approver-chain linkage contract, D12)."
            )
        # D12 enforcement: the service identity must be THIS workspace's OWN
        # M2M credential — a PAT or a foreign workspace's credential is not
        # a valid background execution identity (callers cannot launder an
        # interactive credential through the background path).
        if (
            str(getattr(credential, "workspace_id", "")) != str(workspace.id)
            or getattr(credential, "auth_mode", "") != DatabricksCredentialAuthMode.OAUTH_M2M
        ):
            raise HybridIdentityError(
                f"Background purpose '{purpose}' requires the workspace's own "
                "M2M credential (received a non-M2M or foreign credential)."
            )
        if approval_request is None:
            raise HybridIdentityError(
                f"Background purpose '{purpose}' requires approver-chain "
                "audit linkage (approval_request) — D12."
            )
        identity = ResolvedIdentity(
            kind="m2m",
            purpose=purpose,
            workspace_id=str(workspace.id),
            credential=credential,
            approval_linkage=_approval_linkage(approval_request),
        )
        _emit_resolution_audit(
            tenant=workspace.tenant, workspace=workspace, purpose=purpose, identity=identity
        )
        return identity

    raise HybridIdentityError(
        f"Unknown execution purpose '{purpose}' — not classified as "
        "interactive or background (default-deny, D12)."
    )
