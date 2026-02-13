"""
Versioning API views.

List versions, get version by id, compare two versions.
Uses existing Contract and Dataset models; tenant-scoped; no mocks.
"""

import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.tenants.request_tenant import get_request_tenant_id

from .serializers import (
    VersionCompareSerializer,
    VersionDetailSerializer,
    VersionListEntrySerializer,
)


def _tenant_id_from_request(request: Request):
    """Return tenant_id (UUID or None) for tenant-scoped queries."""
    tid = get_request_tenant_id(request)
    if not tid:
        return None
    try:
        return uuid.UUID(tid)
    except (ValueError, TypeError):
        return None


class VersioningViewSet(viewsets.ViewSet):
    """
    Versioning API: list versions, get version, compare.

    - List: GET .../versions/?resource_type=contract|dataset&resource_id=<asset_uuid>
    - Get:  GET .../versions/<id>/
    - Compare: GET .../compare/?resource_type=...&id_a=<uuid>&id_b=<uuid>
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="List versions",
        description="List versions by asset id. Tenant-scoped.",
        parameters=[
            OpenApiParameter(
                "resource_type",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                enum=["contract", "dataset"],
            ),
            OpenApiParameter(
                "resource_id", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=True
            ),
        ],
        responses={200: VersionListEntrySerializer(many=True)},
    )
    def list(self, request: Request) -> Response:
        resource_type = request.query_params.get("resource_type")
        resource_id = request.query_params.get("resource_id")
        if not resource_type or resource_type not in ("contract", "dataset"):
            return Response(
                {"error": "resource_type required: 'contract' or 'dataset'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not resource_id:
            return Response(
                {"error": "resource_id is required (asset UUID)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant_id = _tenant_id_from_request(request)
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant to list versions"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            asset_uuid = uuid.UUID(resource_id)
        except (ValueError, TypeError):
            return Response(
                {"error": "resource_id must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if resource_type == "contract":
            qs = Contract.objects.filter(
                tenant_id=tenant_id,
                asset_id=asset_uuid,
            ).order_by("-version")
            results = [
                {
                    "id": str(c.id),
                    "resource_type": "contract",
                    "version": c.version,
                    "semantic_version": (getattr(c, "original_spec_version", None) or None),
                    "created_at": c.created_at,
                    "is_current": None,
                }
                for c in qs
            ]
        else:
            qs = Dataset.objects.filter(
                tenant_id=tenant_id,
                asset_id=asset_uuid,
            ).order_by("-version")
            results = [
                {
                    "id": str(d.id),
                    "resource_type": "dataset",
                    "version": d.version,
                    "semantic_version": d.semantic_version,
                    "created_at": d.created_at,
                    "is_current": d.is_current,
                }
                for d in qs
            ]

        return Response({"results": results})

    @extend_schema(
        summary="Get version by id",
        description="Retrieve one version by id. Tenant-scoped.",
        responses={200: VersionDetailSerializer, 404: None},
    )
    def retrieve(self, request: Request, pk=None) -> Response:
        tenant_id = _tenant_id_from_request(request)
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            version_id = uuid.UUID(pk)
        except (ValueError, TypeError):
            return Response(status=status.HTTP_404_NOT_FOUND)

        contract = Contract.objects.filter(tenant_id=tenant_id, id=version_id).first()
        if contract:
            data = {
                "id": str(contract.id),
                "resource_type": "contract",
                "version": contract.version,
                "semantic_version": getattr(contract, "original_spec_version", None) or None,
                "created_at": contract.created_at,
                "updated_at": contract.updated_at,
                "is_current": None,
                "status": contract.status,
                "original_spec_version": contract.original_spec_version,
            }
            return Response(data)

        dataset = Dataset.objects.filter(tenant_id=tenant_id, id=version_id).first()
        if dataset:
            data = {
                "id": str(dataset.id),
                "resource_type": "dataset",
                "version": dataset.version,
                "semantic_version": dataset.semantic_version,
                "created_at": dataset.created_at,
                "updated_at": dataset.updated_at,
                "is_current": dataset.is_current,
                "status": None,
                "original_spec_version": None,
            }
            return Response(data)

        return Response(status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        summary="Compare two versions",
        description="Compare two versions (same resource type). Tenant-scoped.",
        parameters=[
            OpenApiParameter(
                "resource_type",
                OpenApiTypes.STR,
                OpenApiParameter.QUERY,
                required=True,
                enum=["contract", "dataset"],
            ),
            OpenApiParameter("id_a", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=True),
            OpenApiParameter("id_b", OpenApiTypes.UUID, OpenApiParameter.QUERY, required=True),
        ],
        responses={200: VersionCompareSerializer, 400: None, 404: None},
    )
    @action(detail=False, methods=["get"], url_path="compare")
    def compare(self, request: Request) -> Response:
        resource_type = request.query_params.get("resource_type")
        id_a = request.query_params.get("id_a")
        id_b = request.query_params.get("id_b")
        if not resource_type or resource_type not in ("contract", "dataset"):
            return Response(
                {"error": "resource_type required: 'contract' or 'dataset'"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not id_a or not id_b:
            return Response(
                {"error": "id_a and id_b are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant_id = _tenant_id_from_request(request)
        if not tenant_id:
            return Response(
                {"error": "User must belong to a tenant"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid_a = uuid.UUID(id_a)
            uuid_b = uuid.UUID(id_b)
        except (ValueError, TypeError):
            return Response(status=status.HTTP_404_NOT_FOUND)

        if resource_type == "contract":
            c_a = Contract.objects.filter(tenant_id=tenant_id, id=uuid_a).first()
            c_b = Contract.objects.filter(tenant_id=tenant_id, id=uuid_b).first()
            if not c_a or not c_b:
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(
                {
                    "id_a": str(c_a.id),
                    "id_b": str(c_b.id),
                    "resource_type": "contract",
                    "version_a": c_a.version,
                    "version_b": c_b.version,
                    "created_at_a": c_a.created_at,
                    "created_at_b": c_b.created_at,
                }
            )
        else:
            d_a = Dataset.objects.filter(tenant_id=tenant_id, id=uuid_a).first()
            d_b = Dataset.objects.filter(tenant_id=tenant_id, id=uuid_b).first()
            if not d_a or not d_b:
                return Response(status=status.HTTP_404_NOT_FOUND)
            return Response(
                {
                    "id_a": str(d_a.id),
                    "id_b": str(d_b.id),
                    "resource_type": "dataset",
                    "version_a": d_a.version,
                    "version_b": d_b.version,
                    "created_at_a": d_a.created_at,
                    "created_at_b": d_b.created_at,
                }
            )
