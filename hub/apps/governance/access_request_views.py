"""
Access Request Views

REST API views for access request management.
Views call GovernanceService only; business rules run in service.
"""

import structlog
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from hub.apps.audit.utils import create_audit_event
from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError

from .models import AccessRequest, AccessRequestComment, AccessRequestStatus
from .serializers import AccessRequestCommentSerializer, AccessRequestSerializer
from .services import GovernanceService

logger = structlog.get_logger(__name__)


class AccessRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for access request management.

    Tenant-scoped: users can only see/manage access requests in their tenant.
    """

    queryset = AccessRequest.objects.all()
    serializer_class = AccessRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """Filter queryset based on user permissions"""
        user = self.request.user

        # Platform admins can see all access requests
        if hasattr(user, "is_platform_admin") and user.is_platform_admin:
            queryset = AccessRequest.objects.all()
        # Regular users can only see access requests in their tenant
        elif hasattr(user, "tenant") and user.tenant:
            queryset = AccessRequest.objects.filter(tenant=user.tenant)
        else:
            queryset = AccessRequest.objects.none()

        # Apply filters
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        asset_id = self.request.query_params.get("asset_id")
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        dataset_id = self.request.query_params.get("dataset_id")
        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)

        return queryset.order_by("-created_at")

    @transaction.atomic
    def create(self, request):
        """
        Create an access request.

        POST /api/v1/governance/access-requests/
        Body: {
            "asset_id": "uuid" (optional),
            "dataset_id": "uuid" (optional),
            "file_id": "uuid" (optional),
            "reason": "string",
            "requested_access_type": "READ" (optional, default: "READ"),
            "expires_at": "ISO datetime" (optional)
        }
        """
        # Get tenant from user
        tenant = (
            request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
        )
        if not tenant:
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="User must belong to a tenant to create access requests",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # Get resource references
        asset_id = request.data.get("asset_id")
        dataset_id = request.data.get("dataset_id")
        file_id = request.data.get("file_id")
        reason = request.data.get("reason")
        requested_access_type = request.data.get("requested_access_type", "READ")
        expires_at = request.data.get("expires_at")

        if not reason:
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="reason is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        if not any([asset_id, dataset_id, file_id]):
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="At least one of asset_id, dataset_id, or file_id is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # Create access request using service
        service = GovernanceService(tenant_id=str(tenant.id))

        try:
            access_request = service.create_access_request(
                tenant_id=str(tenant.id),
                requested_by_id=str(request.user.id),
                asset_id=asset_id,
                dataset_id=dataset_id,
                file_id=file_id,
                reason=reason,
                requested_access_type=requested_access_type,
                expires_at=expires_at,
            )

            # Log audit event
            create_audit_event(
                resource_type="ACCESS_REQUEST",
                action="ACCESS_REQUEST_CREATED",
                actor_user=request.user,
                tenant=tenant,
                resource_id=str(access_request.id),
                details={
                    "asset_id": asset_id,
                    "dataset_id": dataset_id,
                    "file_id": file_id,
                    "requested_access_type": requested_access_type,
                },
                request=request,
            )

            serializer = AccessRequestSerializer(access_request)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)
        except Exception as e:
            logger.error("Failed to create access request", error=str(e), exc_info=True)
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message=f"Failed to create access request: {e!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_ERROR",
            )

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, id=None):
        """
        Approve an access request.

        POST /api/v1/governance/access-requests/{id}/approve/
        """
        access_request = self.get_object()

        if access_request.status not in (
            AccessRequestStatus.PENDING,
            AccessRequestStatus.PENDING_NEXT_APPROVER,
        ):
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message=f"Access request is not pending (status: {access_request.status})",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="BUSINESS_RULES_VALIDATION",
                details={"status": access_request.status},
            )

        # Phase 272.2 — PLATFORM_ADMIN force_approve bypass.
        force_approve = request.query_params.get("force_approve", "").lower() == "true" and getattr(
            request.user, "is_platform_admin", False
        )

        # Approve using service
        service = GovernanceService(tenant_id=str(access_request.tenant.id))

        try:
            approved_request = service.approve_access_request(
                access_request_id=str(access_request.id),
                tenant_id=str(access_request.tenant.id),
                approver_id=str(request.user.id),
                comments=request.data.get("comments"),
                force_approve=force_approve,
            )

            # Log audit event
            create_audit_event(
                resource_type="ACCESS_REQUEST",
                action="ACCESS_REQUEST_APPROVED",
                actor_user=request.user,
                tenant=access_request.tenant,
                resource_id=str(access_request.id),
                details={"approved_by": str(request.user.id)},
                request=request,
            )

            serializer = AccessRequestSerializer(approved_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)
        except Exception as e:
            logger.error("Failed to approve access request", error=str(e), exc_info=True)
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message=f"Failed to approve access request: {e!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_ERROR",
            )

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, id=None):
        """
        Reject an access request.

        POST /api/v1/governance/access-requests/{id}/reject/
        Body: {
            "reason": "string" (required)
        }
        """
        access_request = self.get_object()

        # Also update the approve guard:

        reason = request.data.get("reason")
        if not reason:
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="reason is required",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        # Reject using service
        service = GovernanceService(tenant_id=str(access_request.tenant.id))

        try:
            rejected_request = service.reject_access_request(
                access_request_id=str(access_request.id),
                tenant_id=str(access_request.tenant.id),
                approver_id=str(request.user.id),
                reason=reason,
                comments=request.data.get("comments"),
            )

            # Log audit event
            create_audit_event(
                resource_type="ACCESS_REQUEST",
                action="ACCESS_REQUEST_REJECTED",
                actor_user=request.user,
                tenant=access_request.tenant,
                resource_id=str(access_request.id),
                details={"rejected_by": str(request.user.id), "rejection_reason": reason},
                request=request,
            )

            serializer = AccessRequestSerializer(rejected_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)
        except Exception as e:
            logger.error("Failed to reject access request", error=str(e), exc_info=True)
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message=f"Failed to reject access request: {e!s}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_ERROR",
            )

    @transaction.atomic
    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, id=None):
        """
        Revoke an approved access request.

        POST /api/v1/governance/access-requests/{id}/revoke/
        Body: {"reason": "string" (required)}
        """
        reason = (request.data.get("reason") or "").strip()
        if not reason:
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="reason is required for revocation",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="REVOCATION_REASON_REQUIRED",
            )

        service = GovernanceService(tenant_id=str(self.get_object().tenant.id))

        try:
            revoked_request = service.revoke_access_request(
                access_request_id=str(id),
                tenant_id=str(self.get_object().tenant.id),
                revoker_id=str(request.user.id),
                reason=reason,
            )

            create_audit_event(
                resource_type="ACCESS_REQUEST",
                action="ACCESS_REQUEST_REVOKED",
                actor_user=request.user,
                tenant=revoked_request.tenant,
                resource_id=str(revoked_request.id),
                details={
                    "revoked_by": str(request.user.id),
                    "revocation_reason": reason,
                },
                request=request,
            )

            serializer = AccessRequestSerializer(revoked_request)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (ServiceValidationError, NotFoundError) as e:
            return handle_service_exception(e)

    # ── Phase 272.1 — AccessRequestComment endpoints ─────────────────

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, id=None):
        """
        GET  /api/v1/governance/access-requests/{id}/comments/
        POST /api/v1/governance/access-requests/{id}/comments/

        GET: list comments chronologically.
        POST: create a standalone comment (body required, no status change).
        """
        access_request = self.get_object()

        if request.method == "GET":
            queryset = AccessRequestComment.objects.filter(
                access_request=access_request,
            ).order_by("created_at")
            serializer = AccessRequestCommentSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # POST — standalone comment.
        body = (request.data.get("body") or "").strip()
        if not body:
            from hub.apps.core.responses import api_error_response

            return api_error_response(
                message="body is required and must be non-empty",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        comment = AccessRequestComment.objects.create(
            tenant=access_request.tenant,
            access_request=access_request,
            author=request.user,
            body=body,
        )
        serializer = AccessRequestCommentSerializer(comment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="pending-count")
    def pending_count(self, request):
        """Return the number of PENDING access requests visible to an admin.

        GET /api/v1/governance/access-requests/pending-count/

        - Platform admins: count across all tenants.
        - TENANT_ADMIN role: count within the caller's tenant.
        - All other users: 403.
        """
        user = request.user
        is_platform_admin = bool(getattr(user, "is_platform_admin", False))
        is_tenant_admin = hasattr(user, "has_role") and user.has_role("TENANT_ADMIN")

        if not (is_platform_admin or is_tenant_admin):
            raise PermissionDenied(
                "Only tenant or platform administrators may view pending counts."
            )

        queryset = AccessRequest.objects.filter(
            status__in=(
                AccessRequestStatus.PENDING,
                AccessRequestStatus.PENDING_NEXT_APPROVER,
            )
        )
        if not is_platform_admin:
            tenant = getattr(user, "tenant", None)
            if tenant is None:
                return Response({"count": 0}, status=status.HTTP_200_OK)
            queryset = queryset.filter(tenant=tenant)

        return Response({"count": queryset.count()}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="bulk-approve")
    def bulk_approve(self, request):
        """Bulk-approve pending access requests (Phase 223.3.3).

        POST /api/v1/governance/access-requests/bulk-approve/
        Body: { "ids": ["uuid", ...], "comments": "optional" }

        Each id is processed in its **own** ``transaction.atomic`` so a
        single failure does not roll back the successful approvals. The
        response surfaces both outcomes:
            { "succeeded": ["uuid", ...], "failed": [{"id": "uuid", "error": "..."}] }
        """
        return self._bulk_transition(
            request,
            action_name="approve",
            success_status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="bulk-reject")
    def bulk_reject(self, request):
        """Bulk-reject pending access requests (Phase 223.3.3).

        POST /api/v1/governance/access-requests/bulk-reject/
        Body: { "ids": ["uuid", ...], "reason": "required string" }

        Semantics match ``bulk_approve``: per-id atomicity, partial
        success reported in ``failed``.
        """
        return self._bulk_transition(
            request,
            action_name="reject",
            success_status=status.HTTP_200_OK,
        )

    def _bulk_transition(self, request, *, action_name, success_status):
        from hub.apps.core.responses import api_error_response

        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids:
            return api_error_response(
                message="'ids' must be a non-empty list of access request UUIDs.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )

        reason = request.data.get("reason")
        if action_name == "reject" and not reason:
            return api_error_response(
                message="'reason' is required for bulk-reject.",
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
            )
        comments = request.data.get("comments")

        succeeded: list[str] = []
        failed: list[dict[str, str]] = []

        queryset = self.get_queryset()

        for raw_id in ids:
            request_id = str(raw_id)
            try:
                access_request = queryset.get(id=request_id)
            except AccessRequest.DoesNotExist:
                failed.append(
                    {
                        "id": request_id,
                        "error": "not found or not permitted",
                    }
                )
                continue

            if access_request.status not in (
                AccessRequestStatus.PENDING,
                AccessRequestStatus.PENDING_NEXT_APPROVER,
            ):
                failed.append(
                    {
                        "id": request_id,
                        "error": f"access request is not pending (status: {access_request.status})",
                    }
                )
                continue

            service = GovernanceService(
                tenant_id=str(access_request.tenant.id),
            )
            try:
                with transaction.atomic():
                    if action_name == "approve":
                        service.approve_access_request(
                            access_request_id=request_id,
                            tenant_id=str(access_request.tenant.id),
                            approver_id=str(request.user.id),
                            comments=comments,
                        )
                        audit_action = "ACCESS_REQUEST_APPROVED"
                        audit_details = {"approved_by": str(request.user.id), "bulk": True}
                    else:
                        service.reject_access_request(
                            access_request_id=request_id,
                            tenant_id=str(access_request.tenant.id),
                            approver_id=str(request.user.id),
                            reason=reason,
                            comments=comments,
                        )
                        audit_action = "ACCESS_REQUEST_REJECTED"
                        audit_details = {
                            "rejected_by": str(request.user.id),
                            "rejection_reason": reason,
                            "bulk": True,
                        }
                create_audit_event(
                    resource_type="ACCESS_REQUEST",
                    action=audit_action,
                    actor_user=request.user,
                    tenant=access_request.tenant,
                    resource_id=request_id,
                    details=audit_details,
                    request=request,
                )
                succeeded.append(request_id)
            except (ServiceValidationError, NotFoundError) as exc:
                failed.append({"id": request_id, "error": str(exc)})
            except Exception as exc:
                logger.error(
                    "bulk_%s_failed",
                    action_name,
                    error=str(exc),
                    request_id=request_id,
                    exc_info=True,
                )
                failed.append({"id": request_id, "error": "internal error"})

        return Response(
            {"succeeded": succeeded, "failed": failed},
            status=success_status,
        )
