"""Phase 235.1 + 235.2 + 235.3 — PLATFORM_ADMIN URL surface (mounted at ``/api/v1/admin/``)."""

from __future__ import annotations

from django.urls import path

from hub.apps.billing import connect_views

from .admin_dashboard_summary import AdminDashboardSummaryView
from .admin_feature_flag_views import (
    AdminTenantFeatureFlagView,
    FeatureFlagFlipApprovalApproveView,
)
from .admin_health import AdminHealthView
from .admin_impersonate import (
    AdminImpersonateExitView,
    AdminImpersonateStartView,
)
from .admin_onboarding_state import AdminTenantOnboardingStateView
from .admin_tenant_create import AdminTenantCreateView
from .admin_tenant_delete import AdminTenantDeleteView

urlpatterns = [
    # Phase TR.C — PLATFORM_ADMIN health endpoint (detailed component
    # status for ops debugging; requires PLATFORM_ADMIN).
    path(
        "health/",
        AdminHealthView.as_view(),
        name="admin-health",
    ),
    # Phase 235.2 — tenant create (PLATFORM_ADMIN). MUST be registered
    # before the ``tenants/<uuid:tenant_id>/...`` patterns below — for
    # POST ``/api/v1/admin/tenants/`` Django's URL resolver picks the
    # FIRST match; ``tenants/`` with no trailing dynamic segment is
    # distinct from ``tenants/<uuid>/feature-flags/`` so the ordering
    # is unambiguous, but listing the create endpoint first makes the
    # admin-surface inventory read top-down by responsibility.
    path(
        "tenants/",
        AdminTenantCreateView.as_view(),
        name="admin-tenant-create",
    ),
    # Phase 235.3 — tenant soft-delete (PLATFORM_ADMIN). The DELETE
    # verb here is the load-bearing method; GET/PUT/PATCH on the same
    # path are intentionally NOT routed because Phase 235.3 doesn't
    # need them and exposing them via this view would be ambiguous
    # with the feature-flag sub-resource below.
    path(
        "tenants/<uuid:tenant_id>/",
        AdminTenantDeleteView.as_view(),
        name="admin-tenant-delete",
    ),
    path(
        "tenants/<uuid:tenant_id>/feature-flags/",
        AdminTenantFeatureFlagView.as_view(),
        name="admin-tenant-feature-flags",
    ),
    # Phase 277.B.032 — onboarding-state inspection (PLATFORM_ADMIN).
    path(
        "tenants/<uuid:tenant_id>/onboarding-state/",
        AdminTenantOnboardingStateView.as_view(),
        name="admin-tenant-onboarding-state",
    ),
    path(
        "feature-flag-approvals/<uuid:approval_id>/approve/",
        FeatureFlagFlipApprovalApproveView.as_view(),
        name="admin-feature-flag-approval-approve",
    ),
    # Phase 235.4 — impersonation start + exit (PLATFORM_ADMIN). The
    # ``exit/`` sub-path is registered BEFORE the bare ``impersonate/``
    # path so a future per-session detail path (e.g.
    # ``impersonate/<uuid:session_id>/``) does NOT accidentally
    # match ``impersonate/exit/`` first.
    path(
        "impersonate/exit/",
        AdminImpersonateExitView.as_view(),
        name="admin-impersonate-exit",
    ),
    path(
        "impersonate/",
        AdminImpersonateStartView.as_view(),
        name="admin-impersonate-start",
    ),
    # Phase 235.5 — PLATFORM_ADMIN consolidated dashboard summary.
    # Single aggregate that drives six widget cards on the SPA's
    # Admin Overview tab. 5-minute server-side cache; ``?refresh=true``
    # bypasses the cache for ops mid-incident.
    path(
        "dashboard/summary/",
        AdminDashboardSummaryView.as_view(),
        name="admin-dashboard-summary",
    ),
    # Phase 271.5.1 — PLATFORM_ADMIN KYB review queue: lists
    # ConnectAccounts stuck in Stripe's KYB pipeline (>24h since
    # creation, details_submitted but charges_enabled still False).
    path(
        "connect/review-queue/",
        connect_views.connect_review_queue,
        name="admin-connect-review-queue",
    ),
]
