"""
Workflows API views: list, get by name, trigger.

Uses real WorkflowRegistry and WorkflowEngine via api_helpers; tenant isolation.
"""

import logging
from urllib.parse import urlencode

from django.core.paginator import InvalidPage, Paginator
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from hub.apps.core.responses import handle_service_exception
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.orchestration.api_helpers import (
    get_workflow_engine,
    get_workflow_registry,
)
from hub.apps.orchestration.serializers import (
    WorkflowDefinitionDetailSerializer,
    WorkflowDefinitionListSerializer,
    WorkflowTriggerRequestSerializer,
)
from hub.apps.orchestration.workflow_engine import WorkflowExecutionError

logger = logging.getLogger(__name__)


def _get_tenant_or_400(request: Request) -> tuple:
    """Return (tenant, None) if user has tenant else (None, error_response)."""
    tenant = (
        request.user.tenant if hasattr(request.user, "tenant") and request.user.tenant else None
    )
    if not tenant:
        return None, Response(
            {"error": "User must belong to a tenant to access the Workflows API"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return tenant, None


class WorkflowListView(APIView):
    """GET /api/v1/workflows/ — list workflow definitions; filters and pagination."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        _tenant, err = _get_tenant_or_400(request)
        if err is not None:
            return err

        registry = get_workflow_registry()
        name = request.query_params.get("name")
        is_active_param = request.query_params.get("is_active")
        is_active = None
        if is_active_param is not None:
            is_active = str(is_active_param).lower() in ("true", "1", "yes")

        workflows = registry.discover_workflows(workflow_name=name, is_active=is_active)

        page = request.query_params.get("page", 1)
        page_size = request.query_params.get("page_size", 50)
        try:
            page = max(1, int(page))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = max(1, min(100, int(page_size)))
        except (ValueError, TypeError):
            page_size = 50

        paginator = Paginator(workflows, page_size)
        try:
            page_obj = paginator.get_page(page)
        except InvalidPage:
            page_obj = paginator.get_page(1)

        serializer = WorkflowDefinitionListSerializer(page_obj.object_list, many=True)

        def _build_query(page_num: int) -> str:
            params = {"page": page_num}
            if page_size != 50:
                params["page_size"] = page_size
            if name:
                params["name"] = name
            if is_active_param is not None:
                params["is_active"] = is_active_param
            return urlencode(params)

        next_link = None
        if page_obj.has_next():
            q = _build_query(page_obj.next_page_number())
            next_link = request.build_absolute_uri(request.path + "?" + q)
        previous_link = None
        if page_obj.has_previous():
            q = _build_query(page_obj.previous_page_number())
            previous_link = request.build_absolute_uri(request.path + "?" + q)

        return Response(
            {
                "count": paginator.count,
                "page": page_obj.number,
                "page_size": page_size,
                "total_pages": paginator.num_pages,
                "next": next_link,
                "previous": previous_link,
                "results": serializer.data,
            }
        )


class WorkflowDetailView(APIView):
    """GET /api/v1/workflows/<name>/ — get workflow definition by name and optional version."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, name: str) -> Response:
        _tenant, err = _get_tenant_or_400(request)
        if err is not None:
            return err

        registry = get_workflow_registry()
        version = request.query_params.get("version")
        workflow = registry.get_workflow(name, version=version)
        if workflow is None:
            return Response(
                {
                    "error": f"Workflow not found: {name}",
                    "code": "NOT_FOUND",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = WorkflowDefinitionDetailSerializer(workflow)
        return Response(serializer.data)


class WorkflowTriggerView(APIView):
    """POST .../trigger/ — create (and optionally start) a workflow instance."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, name: str) -> Response:
        tenant, err = _get_tenant_or_400(request)
        if err is not None:
            return err

        req_serializer = WorkflowTriggerRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        input_data = req_serializer.validated_data.get("input_data") or {}
        start_immediately = req_serializer.validated_data.get("start_immediately", False)

        engine = get_workflow_engine()
        try:
            instance = engine.create_instance(
                workflow_name=name,
                input_data=input_data,
                tenant_id=str(tenant.id),
                created_by_id=str(request.user.id),
            )
        except ServiceValidationError as e:
            return handle_service_exception(e)
        except WorkflowExecutionError as e:
            return Response(
                {
                    "error": str(e),
                    "code": "WORKFLOW_NOT_FOUND",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        started = True
        start_error = None
        if start_immediately:
            try:
                instance = engine.start_instance(str(instance.id))
            except Exception as e:
                logger.warning(
                    "Workflow trigger: start_immediately failed for instance %s: %s",
                    instance.id,
                    e,
                    exc_info=True,
                )
                started = False
                start_error = str(e)

        payload = {
            "id": instance.id,
            "status": instance.status,
            "workflow_name": instance.workflow_name,
            "workflow_version": instance.workflow_version,
            "created_at": instance.created_at,
        }
        if start_immediately:
            payload["started"] = started
            if start_error is not None:
                payload["start_error"] = start_error
        return Response(payload, status=status.HTTP_201_CREATED)
