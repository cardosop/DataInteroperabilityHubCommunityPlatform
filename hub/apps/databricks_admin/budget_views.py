"""P7 (openspec add-databricks-cost-guardrails task 7.6) — the U9 budget
page API.

``GET /api/v1/databricks/budgets/`` renders the request tenant's budget
rows (window-consumed + per-warehouse breakdown) via
``budget_ux.budget_status``. Authenticated users, flag-gated like every
other control-plane surface (the kill switch wins even when the flag is
on), scoped-throttled per the house rate discipline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from hub.apps.api.standards.pagination import StandardPageNumberPagination
from hub.apps.databricks_admin.views import _gate_control_plane

if TYPE_CHECKING:
    from rest_framework.response import Response


class BudgetViewSet(viewsets.ViewSet):
    """The tenant's cost-budget rows with the rolling progress."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "databricks_budgets"

    def get_permissions(self):
        return [IsAuthenticated()]

    def initial(self, request, *args, **kwargs):
        _gate_control_plane(self)
        return super().initial(request, *args, **kwargs)

    def list(self, request) -> Response:
        from hub.apps.databricks_admin.budget_ux import budget_status

        tenant = getattr(request, "tenant", None) or getattr(request.user, "tenant", None)
        rows = budget_status(tenant)
        paginator = StandardPageNumberPagination()
        page = paginator.paginate_queryset(rows, request)
        return paginator.get_paginated_response(page if page is not None else rows)
