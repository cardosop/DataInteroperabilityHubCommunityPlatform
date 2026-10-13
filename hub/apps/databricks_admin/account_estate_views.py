"""P8 (openspec add-databricks-account-plane task 8.4) — the estate
summary surface: ``GET /api/v1/databricks/estate-summary/``.

PLATFORM_ADMIN-only with the SAME RBAC contract as the provisioning
surface (account_views.py): a non-platform caller gets 403 with the
canonical ``PERMISSION_DENIED`` code (the prose error table). The rows
are DERIVED per request (``account_estate.estate_summary``) — the
read-only admin-alias aggregate, no cached rows. (Lives in its own
module so the two account surfaces evolve independently; the
permission-denied exception mirrors account_views' class-attribute
convention — consolidate when both surfaces stabilize.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from hub.apps.auth.permissions import HasRole

if TYPE_CHECKING:
    from rest_framework.response import Response


class _EstatePermissionDenied(PermissionDenied):
    """The prose error table's contract: 403 with the CANONICAL
    ``PERMISSION_DENIED`` code. The code is a CLASS attribute (the repo's
    envelope handler reads class attributes — DRF 3.16 dropped the
    instance ``code`` attribute, so a constructor ``code=`` kwarg would
    collapse to ``AUTH_FORBIDDEN``)."""

    status_code = 403
    code = "PERMISSION_DENIED"
    default_detail = "You do not have permission to perform this action."


class AccountEstateViewSet(viewsets.ViewSet):
    """The platform-wide Databricks estate summary."""

    permission_classes = [permissions.IsAuthenticated]

    # NOTE: no ``permission_classes`` attribute beyond IsAuthenticated —
    # get_permissions() is the single source of truth (pre-instantiated
    # HasRole entries break DRF's re-invocation; see the HasRole
    # docstring).
    def get_permissions(self):
        return [permissions.IsAuthenticated(), HasRole("PLATFORM_ADMIN")]

    def permission_denied(
        self, request, message=None, code=None
    ):  # DRF override — framework keyword-dispatches
        from rest_framework import exceptions as drf_exceptions

        # DRF's default semantics FIRST: an unauthenticated caller (no
        # successful authenticator) gets 401 NotAuthenticated — never a
        # 403 (the DRF permission_denied contract the house surfaces
        # rely on; the override below only pins the code for the
        # AUTHENTICATED non-platform caller).
        if request.authenticators and not request.successful_authenticator:
            raise drf_exceptions.NotAuthenticated()
        raise _EstatePermissionDenied(detail=message)

    def list(self, request) -> Response:
        from hub.apps.api.standards.pagination import StandardPageNumberPagination
        from hub.apps.databricks_admin.account_estate import estate_summary

        rows = estate_summary()
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(page if page is not None else rows)
