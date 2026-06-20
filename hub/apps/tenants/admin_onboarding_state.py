"""
Phase 277.B.032 — Admin onboarding-state inspection endpoint.

``GET /api/v1/admin/tenants/{tenant_id}/onboarding-state/``

Returns the checklist from ``compute_onboarding_state()`` so a
PLATFORM_ADMIN can inspect a tenant's onboarding progress before
approving KYC or activating features.
"""

from __future__ import annotations

from django.http import HttpRequest
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.audit.event_types import TENANT_ONBOARDING_STATE_VIEWED
from hub.apps.audit.utils import create_audit_event
from hub.apps.tenants.models import Tenant
from hub.apps.tenants.onboarding import compute_onboarding_state
from hub.apps.tenants.permissions import IsPlatformAdmin


class AdminTenantOnboardingStateView(APIView):
    """Return the onboarding checklist for a tenant (PLATFORM_ADMIN only)."""

    permission_classes = [permissions.IsAuthenticated, IsPlatformAdmin]

    def get(self, request: HttpRequest, tenant_id: str) -> Response:
        tenant = self._get_tenant(tenant_id)
        state = compute_onboarding_state(tenant)

        create_audit_event(
            resource_type="TENANT",
            action=TENANT_ONBOARDING_STATE_VIEWED,
            actor_user=request.user,
            tenant=tenant,
            resource_id=str(tenant.id),
            result="SUCCESS",
            details={
                "tenant_id": str(tenant.id),
                "onboarding_state": state,
            },
        )

        return Response(
            {
                "tenant_id": str(tenant.id),
                "tenant_name": tenant.name,
                "onboarding_state": state,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _get_tenant(tenant_id: str) -> Tenant:
        try:
            return Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            from django.http import Http404

            raise Http404("Tenant not found")
