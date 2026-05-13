"""
Phase 277.B.092 — ABAC enforcement guard for admin endpoints.

Wraps PLATFORM_ADMIN-only endpoints with ABAC evaluation so that a
DENY ``AccessPolicy`` can block an admin action even when the caller
has the PLATFORM_ADMIN role.  This provides defence-in-depth: the
role grants CAPABILITY, but ABAC governs whether the SPECIFIC action
is permitted.

Usage:

    from hub.apps.governance.admin_abac import admin_abac_guard

    @admin_abac_guard(resource_type="TENANT_CONFIG")
    def update_rate_limits(request, tenant_id):
        ...
"""
from __future__ import annotations

import functools
import logging
from typing import Callable

from django.http import JsonResponse
from rest_framework import status

logger = logging.getLogger(__name__)


def _evaluate_admin_action(request, resource_type: str, action: str) -> None:
    """Evaluate ABAC for an admin action; raise PermissionDenied if blocked.

    This is the runtime function used by ViewSet.check_permissions().
    It raises DRF's PermissionDenied so the standard DRF exception
    handler renders a structured error response.
    """
    from rest_framework.exceptions import PermissionDenied

    from hub.apps.audit.event_types import ABAC_POLICY_DENIED
    from hub.apps.audit.utils import create_audit_event
    from hub.apps.governance.abac import ABACEngine

    user = request.user
    if not user or not user.is_authenticated:
        return

    tenant_id = (
        getattr(request, "tenant_id", None)
        or getattr(user, "tenant_id", None)
    )
    resource_id = getattr(request, "resolver_match", None)
    resource_id_str = str(resource_id.kwargs) if resource_id else "unknown"

    try:
        abac_result = ABACEngine.evaluate_access(
            user_id=str(user.id),
            tenant_id=str(tenant_id) if tenant_id else "",
            resource_type=resource_type,
            resource_id=resource_id_str,
            access_type=action,
        )
    except Exception:
        # Fail-open on ABAC evaluation error — admin still proceeds
        return

    if not abac_result.allowed:
        try:
            create_audit_event(
                resource_type=resource_type,
                action=ABAC_POLICY_DENIED,
                actor_user=user,
                tenant=None,
                resource_id=resource_id_str,
                result="DENIED",
                details={
                    "admin_action": action,
                    "admin_user_id": str(user.id),
                    "policy_id": (
                        str(abac_result.policy.id)
                        if abac_result.policy
                        else None
                    ),
                },
                request=request,
            )
        except Exception:
            logger.exception("abac_policy_denied_audit_failed")

        raise PermissionDenied(
            detail={
                "code": "ABAC_POLICY_DENIED",
                "message": "This admin action is blocked by an ABAC policy.",
                "http_status": 403,
                "details": {
                    "resource_type": resource_type,
                    "action": action,
                },
            }
        )


def admin_abac_guard(
    resource_type: str,
    action: str = "ADMIN_WRITE",
):
    """Decorator: evaluate ABAC before executing an admin endpoint.

    If ABAC returns DENY, the decorated function is NOT called and a
    403 response with code ``ABAC_POLICY_DENIED`` is returned instead.
    An audit event is emitted recording the blocked attempt.

    Args:
        resource_type: ABAC resource type (e.g. ``TENANT_CONFIG``,
            ``FEATURE_FLAG``, ``GOVERNANCE_OVERRIDE``).
        action: ABAC access type (default ``ADMIN_WRITE``).
    """

    def decorator(view_func: Callable):

        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from hub.apps.audit.event_types import ABAC_POLICY_DENIED
            from hub.apps.audit.utils import create_audit_event
            from hub.apps.governance.abac import ABACEngine
            from hub.apps.tenants.request_tenant import get_request_tenant_id

            user = request.user
            if not user or not user.is_authenticated:
                return JsonResponse(
                    {"error": "Authentication required."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            tenant_id = get_request_tenant_id(request) or str(
                getattr(user, "tenant_id", "")
            )
            resource_id = kwargs.get(
                "tenant_id", kwargs.get("pk", tenant_id or "unknown")
            )

            # Evaluate ABAC
            try:
                abac_result = ABACEngine.evaluate_access(
                    user_id=str(user.id),
                    tenant_id=str(tenant_id) if tenant_id else "",
                    resource_type=resource_type,
                    resource_id=str(resource_id),
                    access_type=action,
                )
            except Exception:
                logger.exception("admin_abac_evaluation_failed")
                # Fail-open on evaluation error — admin still proceeds
                return view_func(request, *args, **kwargs)

            if not abac_result.allowed:
                try:
                    create_audit_event(
                        resource_type=resource_type,
                        action=ABAC_POLICY_DENIED,
                        actor_user=user,
                        tenant=None,
                        resource_id=str(resource_id),
                        result="DENIED",
                        details={
                            "admin_action": action,
                            "admin_user_id": str(user.id),
                            "policy_id": (
                                str(abac_result.policy.id)
                                if abac_result.policy
                                else None
                            ),
                        },
                        request=request,
                    )
                except Exception:
                    logger.exception("abac_policy_denied_audit_failed")

                return JsonResponse(
                    {
                        "error": {
                            "code": "ABAC_POLICY_DENIED",
                            "message": (
                                "This admin action is blocked by an ABAC policy."
                            ),
                            "http_status": 403,
                            "details": {
                                "resource_type": resource_type,
                                "action": action,
                            },
                        },
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # ABAC allowed — proceed
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
