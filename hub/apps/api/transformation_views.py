"""
Placeholder views for transformation pipelines API.

Deferred feature - returns empty placeholders until full implementation.
"""
import uuid

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class TransformationPipelineViewSet(viewsets.ViewSet):
    """Placeholder for transformation pipelines - GET /api/v1/transformation/pipelines/"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

    def create(self, request):
        pipeline_id = str(uuid.uuid4())
        name = request.data.get("name", "placeholder")
        return Response(
            {"id": pipeline_id, "name": name, "status": "placeholder"},
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, pk=None):
        """Placeholder: pipelines are not persisted; return 404 for any id."""
        from rest_framework.exceptions import NotFound

        raise NotFound(detail="Pipeline not found")

    @action(detail=True, methods=["post"], url_path="validate")
    def validate(self, request, pk=None):
        return Response({"valid": True, "pipeline_id": pk}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        return Response({"status": "ok", "pipeline_id": pk}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="execute")
    def execute(self, request, pk=None):
        return Response(
            {"execution_id": str(uuid.uuid4()), "pipeline_id": pk, "status": "submitted"},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"], url_path="preview")
    def preview(self, request, pk=None):
        return Response({"preview": [], "pipeline_id": pk}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        return Response({"pipeline_id": pk, "download_url": None}, status=status.HTTP_200_OK)

    def partial_update(self, request, pk=None):
        return Response({"id": pk, "nodes": request.data.get("nodes", [])}, status=status.HTTP_200_OK)


class TransformationExecutionViewSet(viewsets.ViewSet):
    """Placeholder for transformation executions - GET /api/v1/transformation/executions/"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response({"results": [], "count": 0}, status=status.HTTP_200_OK)

    def retrieve(self, request, pk=None):
        return Response({
            "id": pk,
            "status": "completed",
            "pipeline_id": None,
        }, status=status.HTTP_200_OK)


class TransformationAuditViewSet(viewsets.ViewSet):
    """Placeholder for transformation audit - GET /api/v1/transformation/audit/"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        return Response({"audit_log": [], "count": 0}, status=status.HTTP_200_OK)
