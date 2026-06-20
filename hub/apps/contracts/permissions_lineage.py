"""
Phase 228.F2 (F2.10) — RBAC for the field-level lineage editor.

The lineage edit endpoint requires **one of**:

* The caller is a platform admin.
* The caller is a tenant admin in the contract's tenant.
* The caller has the explicit ``EDIT_LINEAGE`` permission in the
  contract's tenant (granted via the standard role-permission
  surface).
* The caller is the contract's owner (``Contract.created_by``
  matches ``request.user``).

Cross-tenant edits are NEVER allowed by F2 v1.  A consumer who
purchased a listing can read the lineage (F1) but cannot edit the
provider's lineage.  This is the documented v1 non-goal in the
F2.33 doc update.

Why a function not a DRF permission class
-----------------------------------------
The lineage edit endpoint already delegates the permission check
to a function (mirroring `require_entitlement_or_summary` from F1).
Class-based permissions return True/False; this surface needs to
emit a typed PermissionDenied with a `code` field for the API
contract — easier as a function.
"""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import PermissionDenied


def require_edit_lineage(user: Any, contract: Any) -> None:
    """Raise :class:`PermissionDenied` if ``user`` cannot edit
    ``contract``'s lineage.

    Returns ``None`` on success — the side-effecting "permission
    granted, proceed" signal.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionDenied(
            {
                "error": "Authentication required",
                "code": "EDIT_LINEAGE_FORBIDDEN",
            }
        )

    # Platform admin short-circuit.
    if getattr(user, "is_platform_admin", False):
        return

    user_tenant_id = str(getattr(user, "tenant_id", "") or "")
    contract_tenant_id = str(getattr(contract, "tenant_id", "") or "")

    # Cross-tenant edit denied unconditionally (F2 v1 non-goal).
    if user_tenant_id != contract_tenant_id:
        raise PermissionDenied(
            {
                "error": ("Cross-tenant lineage edits are not permitted."),
                "code": "EDIT_LINEAGE_FORBIDDEN",
            }
        )

    # Contract owner short-circuit.
    contract_owner_id = getattr(contract, "created_by_id", None)
    if contract_owner_id and str(contract_owner_id) == str(user.id):
        return

    # Tenant admin OR EDIT_LINEAGE permission.
    if _has_tenant_admin_role(user, contract_tenant_id):
        return
    if _has_edit_lineage_permission(user, contract_tenant_id):
        return

    raise PermissionDenied(
        {
            "error": (
                "Editing this contract's lineage requires "
                "TENANT_ADMIN role or the EDIT_LINEAGE permission."
            ),
            "code": "EDIT_LINEAGE_FORBIDDEN",
        }
    )


def _has_tenant_admin_role(user: Any, tenant_id: str) -> bool:
    """Lookup the user's role-bindings for ``tenant_id``."""
    try:
        # Phase 227 L9.3 used the ``has_role`` helper on User; reuse it
        # so the role-detection logic stays in one place.
        return bool(user.has_role("TENANT_ADMIN"))
    except Exception:
        # User model variant without ``has_role`` — fall back to the
        # explicit UserRole join.
        try:
            from hub.apps.users.models import UserRole

            return UserRole.objects.filter(
                user=user,
                tenant_id=tenant_id,
                role__name="TENANT_ADMIN",
            ).exists()
        except Exception:  # pragma: no cover — defensive
            return False


def _has_edit_lineage_permission(user: Any, tenant_id: str) -> bool:
    """Lookup the explicit ``EDIT_LINEAGE`` permission grant."""
    try:
        from hub.apps.users.models import UserRole

        # Roles → role.permissions__codename — the standard Django
        # auth-style permission lookup, scoped to the tenant.
        return UserRole.objects.filter(
            user=user,
            tenant_id=tenant_id,
            role__permissions__codename="EDIT_LINEAGE",
        ).exists()
    except Exception:  # pragma: no cover — defensive
        return False


__all__ = ["require_edit_lineage"]
