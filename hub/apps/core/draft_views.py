"""
Phase 278.B.4 — draft CRUD endpoints.

GET  /api/v1/drafts/?resource_type=dpia&draft_key=create
PUT  /api/v1/drafts/ — body: {resource_type, draft_key, data}
DELETE /api/v1/drafts/?resource_type=dpia&draft_key=create
"""
from django.db import IntegrityError
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from hub.apps.core.drafts import FormDraft
from hub.apps.tenants.request_tenant import get_request_tenant_id


@extend_schema(
    operation_id="draft_retrieve",
    summary="Retrieve a form draft",
    parameters=[
        {"name": "resource_type", "required": True, "in_": "query", "schema": {"type": "string"}},
        {"name": "draft_key", "required": False, "in_": "query", "schema": {"type": "string", "default": "default"}},
    ],
    responses={
        200: OpenApiResponse(description="Draft data."),
        404: OpenApiResponse(description="Draft not found."),
    },
    tags=["Drafts"],
)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def draft_retrieve(request):
    """Get an auto-saved form draft."""
    resource_type = request.query_params.get("resource_type")
    if not resource_type:
        return Response({"error": "resource_type is required"}, status=status.HTTP_400_BAD_REQUEST)
    draft_key = request.query_params.get("draft_key", "default")

    try:
        draft = FormDraft.objects.get(
            user=request.user,
            resource_type=resource_type,
            draft_key=draft_key,
        )
    except FormDraft.DoesNotExist:
        return Response(
            {"message": "No draft found", "data": {}},
            status=status.HTTP_200_OK,
        )

    return Response({
        "id": str(draft.id),
        "resource_type": draft.resource_type,
        "draft_key": draft.draft_key,
        "data": draft.data,
        "updated_at": draft.updated_at.isoformat(),
    })


@extend_schema(
    operation_id="draft_save",
    summary="Save a form draft (upsert)",
    request={
        "type": "object",
        "properties": {
            "resource_type": {"type": "string"},
            "draft_key": {"type": "string", "default": "default"},
            "data": {"type": "object"},
        },
        "required": ["resource_type", "data"],
    },
    responses={
        200: OpenApiResponse(description="Draft updated."),
        201: OpenApiResponse(description="Draft created."),
    },
    tags=["Drafts"],
)
@api_view(["PUT"])
@permission_classes([permissions.IsAuthenticated])
def draft_save(request):
    """Save or update a form draft. Upserts by (user, resource_type, draft_key)."""
    resource_type = request.data.get("resource_type")
    data = request.data.get("data")
    if not resource_type:
        return Response({"error": "resource_type is required"}, status=status.HTTP_400_BAD_REQUEST)
    if data is None:
        return Response({"error": "data is required"}, status=status.HTTP_400_BAD_REQUEST)

    draft_key = request.data.get("draft_key", "default")
    tenant_id = get_request_tenant_id(request)

    draft, created = FormDraft.objects.update_or_create(
        user=request.user,
        resource_type=resource_type,
        draft_key=draft_key,
        defaults={
            "data": data,
            "tenant_id": tenant_id,
        },
    )

    return Response(
        {
            "id": str(draft.id),
            "resource_type": draft.resource_type,
            "draft_key": draft.draft_key,
            "data": draft.data,
            "updated_at": draft.updated_at.isoformat(),
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
    )


@extend_schema(
    operation_id="draft_delete",
    summary="Delete a form draft",
    parameters=[
        {"name": "resource_type", "required": True, "in_": "query", "schema": {"type": "string"}},
        {"name": "draft_key", "required": False, "in_": "query", "schema": {"type": "string", "default": "default"}},
    ],
    responses={
        204: OpenApiResponse(description="Draft deleted."),
    },
    tags=["Drafts"],
)
@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def draft_delete(request):
    """Delete an auto-saved form draft."""
    resource_type = request.query_params.get("resource_type")
    if not resource_type:
        return Response({"error": "resource_type is required"}, status=status.HTTP_400_BAD_REQUEST)
    draft_key = request.query_params.get("draft_key", "default")

    FormDraft.objects.filter(
        user=request.user,
        resource_type=resource_type,
        draft_key=draft_key,
    ).delete()

    return Response(status=status.HTTP_204_NO_CONTENT)
