"""
Phase 228.F3.6 — Lineage Subscription CRUD endpoints (REQ-LIN-F3-003).

Routes (registered under ``/api/v1/lineage/subscriptions/``):

* ``POST   /``         — create
* ``GET    /``         — list (cursor-paginated, mine only)
* ``GET    /{id}/``    — retrieve
* ``PATCH  /{id}/``    — update threshold + channels
* ``DELETE /{id}/``    — unsubscribe

Auth + scoping:

* ``IsAuthenticated`` — only logged-in users.
* The list queryset is auto-filtered to the current user.  A user
  cannot list / retrieve someone else's subscriptions even if they
  guess the UUID.
* On create, the viewset validates that the user has READ permission
  on the referenced contract / asset — you cannot subscribe to
  something you can't see (REQ-LIN-F3-003 spec scenario).
* The 100-subscription cap is enforced at create time
  (REQ-LIN-F3-002 spec scenario).
* Duplicate detection: if the user already has a subscription with
  the same source, the create returns 409 (CONFLICT) with the
  existing row's id.

Capability flag: ``lineage.change_notifications``.  When OFF, all
endpoints return 404 so the surface is hidden completely
(consistent with the F1/F2 pattern).
"""
from __future__ import annotations

from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from hub.apps.api.capabilities import is_capability_enabled
from hub.apps.api.standards.pagination import StandardCursorPagination
from hub.apps.contracts.lineage_subscription_serializers import (
    LineageSubscriptionPatchSerializer,
    LineageSubscriptionSerializer,
)
from hub.apps.contracts.models import Contract, LineageSubscription


PER_USER_SUBSCRIPTION_CAP = 100


class LineageSubscriptionPagination(StandardCursorPagination):
    """REQ-LIN-F3-003 spec uses ``?limit=`` for the page-size query
    param: ``GET /api/v1/lineage/subscriptions/?cursor=<>&limit=50``.

    The shared ``StandardCursorPagination`` exposes ``page_size``;
    this subclass widens the accepted name to BOTH ``limit`` and
    ``page_size``.  ``limit`` wins when both are sent (spec is the
    primary contract); ``page_size`` is preserved for the rest of
    the codebase that uses it.
    """

    page_size_query_param = "limit"

    def get_page_size(self, request):  # type: ignore[override]
        # Accept either "limit" (spec) or "page_size" (project default).
        # DRF's CursorPagination.get_page_size reads from
        # ``self.page_size_query_param`` only; we add a fallback.
        try:
            from rest_framework.settings import api_settings
            from rest_framework.pagination import _positive_int

            for param in ("limit", "page_size"):
                if param in request.query_params:
                    raw = request.query_params[param]
                    return _positive_int(
                        raw,
                        strict=True,
                        cutoff=self.max_page_size,
                    )
        except (KeyError, ValueError):
            pass
        return self.page_size


class LineageSubscriptionViewSet(viewsets.ModelViewSet):
    """REQ-LIN-F3-003 ViewSet."""

    serializer_class = LineageSubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = LineageSubscriptionPagination
    lookup_field = "id"
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    # ----- Capability gate -----

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not is_capability_enabled("lineage.change_notifications"):
            from rest_framework.exceptions import NotFound
            raise NotFound("lineage.change_notifications capability is disabled.")

    # ----- Queryset -----

    def get_queryset(self):
        # Always-filter-by-user — a user cannot see another user's
        # subscriptions even with a guessed id.
        user = self.request.user
        return (
            LineageSubscription.objects
            .filter(user=user)
            .select_related("source_contract", "source_asset")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "partial_update":
            return LineageSubscriptionPatchSerializer
        return LineageSubscriptionSerializer

    # ----- Create -----

    def create(self, request, *args, **kwargs):
        # Read-permission gate on the source resource — defends against
        # the "subscribe to a contract in another tenant to leak its
        # name" attack.
        self._assert_user_can_see_source(request)

        # Per-user cap enforcement.
        existing_count = LineageSubscription.objects.filter(
            user=request.user,
        ).count()
        if existing_count >= PER_USER_SUBSCRIPTION_CAP:
            return Response(
                {
                    "code": "SUBSCRIPTION_CAP_EXCEEDED",
                    "detail": (
                        f"Per-user subscription cap of "
                        f"{PER_USER_SUBSCRIPTION_CAP} reached."
                    ),
                    "cap": PER_USER_SUBSCRIPTION_CAP,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Duplicate detection — return 409 with the existing row's id
        # so the client can no-op cleanly without a second round-trip.
        source_contract = request.data.get("source_contract")
        source_asset = request.data.get("source_asset")
        existing = LineageSubscription.objects.filter(
            user=request.user,
            source_contract_id=source_contract,
            source_asset_id=source_asset,
        ).first()
        if existing is not None:
            return Response(
                {
                    "code": "SUBSCRIPTION_ALREADY_EXISTS",
                    "id": str(existing.id),
                    "detail": "You are already subscribed to this source.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(user=request.user)
        return Response(
            self.get_serializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    # ----- Update -----

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(LineageSubscriptionSerializer(instance).data)

    # ----- Helpers -----

    def _assert_user_can_see_source(self, request) -> None:
        """REQ-LIN-F3-003 spec scenario "Cannot subscribe to invisible
        resource".

        A user must have READ permission on the contract / asset they
        subscribe to.  In the multi-tenant model, READ permission
        translates to "the resource is visible in the user's tenant
        scope OR the user has a marketplace entitlement granting
        read access to the cross-tenant resource".
        """
        source_contract_id = request.data.get("source_contract")
        source_asset_id = request.data.get("source_asset")
        user = request.user
        user_tenant_id = getattr(user, "tenant_id", None)

        if source_contract_id:
            try:
                contract = Contract.objects.get(id=source_contract_id)
            except Contract.DoesNotExist:
                raise PermissionDenied(
                    "Source contract not visible to this user.",
                )
            # Same-tenant: visible.  Cross-tenant: REQ-LIN-F3-003
            # mandates 403.  (Marketplace-entitlement-based cross-tenant
            # read is intentionally NOT a subscription source for v1 —
            # the dispatcher's debounce + per-tenant rate limiter
            # cannot reason cleanly about cross-tenant counts; gate it
            # to same-tenant for v1.)
            if str(contract.tenant_id) != str(user_tenant_id):
                raise PermissionDenied(
                    "Cross-tenant subscription sources are not "
                    "permitted in F3 v1.",
                )

        if source_asset_id:
            from hub.apps.assets.models import Asset
            try:
                asset = Asset.objects.get(id=source_asset_id)
            except Asset.DoesNotExist:
                raise PermissionDenied(
                    "Source asset not visible to this user.",
                )
            if str(asset.tenant_id) != str(user_tenant_id):
                raise PermissionDenied(
                    "Cross-tenant subscription sources are not "
                    "permitted in F3 v1.",
                )
