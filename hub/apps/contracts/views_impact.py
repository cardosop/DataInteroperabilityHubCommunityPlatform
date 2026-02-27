"""
Contract Views Impact Analysis Operations

Impact analysis actions for contract viewsets.

SAVING CHECKPOINT: This module contains impact analysis-related actions.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.core.responses import api_error_response
from hub.apps.core.services.base import NotFoundError

from .impact_visualization import ImpactVisualizer
from .lineage_service import LineageService
from .models import Contract
from .views_helpers import _get_tenant_id_from_request


class ContractImpactMixin:
    """
    Mixin for Contract impact analysis operations.

    Provides impact analysis endpoints for analyzing contract changes.
    """

    @extend_schema(
        summary="Get impact analysis",
        description="""
        Analyze impact of changes to a contract, model, or field.

        Performs reverse lineage traversal to find all resources that depend on
        the specified contract/model/field.

        **Query Parameters:**
        - `depth`: Maximum traversal depth (default: 10)
        - `model_name`: Optional model name for model-level impact
        - `field_name`: Optional field name for field-level impact
        - `include_fields`: Include field-level dependencies (default: true)
        - `format`: Response format (json, csv, dot, mermaid, paths) (default: json)
        """,
        parameters=[
            OpenApiParameter(
                name="depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum traversal depth (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Model name for model-level impact",
                required=False,
            ),
            OpenApiParameter(
                name="field_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Field name for field-level impact",
                required=False,
            ),
            OpenApiParameter(
                name="include_fields",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description="Include field-level dependencies (default: true)",
                required=False,
            ),
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Response format: json, csv, dot, mermaid, paths (default: json)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Impact analysis result"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Impact Analysis"],
    )
    @action(detail=True, methods=["get"], url_path="impact-analysis")
    def get_impact_analysis(self, request, id=None):
        """Get impact analysis for a contract, model, or field."""
        # Get contract ID from URL kwargs
        contract_id = self.kwargs.get("pk") or self.kwargs.get("id")
        if not contract_id:
            from rest_framework.exceptions import NotFound

            raise NotFound("Contract ID not found in URL")

        # Get contract directly and verify tenant access
        try:
            contract = Contract.objects.get(id=contract_id)
        except Contract.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound("Contract not found")

        # Verify tenant access (same logic as get_queryset)
        user = request.user
        if not (hasattr(user, "is_platform_admin") and user.is_platform_admin):
            # Get tenant from request or user
            tenant_id = None
            if hasattr(request, "tenant_id") and request.tenant_id:
                tenant_id = request.tenant_id
                if isinstance(tenant_id, str):
                    import uuid

                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None
            elif hasattr(request, "tenant") and request.tenant:
                tenant_id = request.tenant.id
            elif hasattr(user, "tenant_id") and user.tenant_id:
                tenant_id = user.tenant_id
            elif hasattr(user, "tenant") and user.tenant:
                tenant_id = user.tenant.id

            # Verify contract belongs to user's tenant
            if tenant_id and contract.tenant_id:
                # Convert both to UUID for comparison
                import uuid

                contract_tenant_id = contract.tenant_id
                if isinstance(contract_tenant_id, str):
                    try:
                        contract_tenant_id = uuid.UUID(contract_tenant_id)
                    except (ValueError, TypeError):
                        contract_tenant_id = None
                if isinstance(tenant_id, str):
                    try:
                        tenant_id = uuid.UUID(tenant_id)
                    except (ValueError, TypeError):
                        tenant_id = None

                if contract_tenant_id != tenant_id:
                    from rest_framework.exceptions import NotFound

                    raise NotFound("Contract not found")

        # Get parameters (use "output" to avoid DRF content negotiation using "format" query param)
        depth = int(request.query_params.get("depth", 10))
        model_name = request.query_params.get("model_name")
        field_name = request.query_params.get("field_name")
        include_fields = request.query_params.get("include_fields", "true").lower() == "true"
        format_type = (
            request.query_params.get("output") or request.query_params.get("format") or "json"
        ).lower()

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        # Perform impact analysis using LineageService (which publishes events automatically)
        try:
            impact_result = lineage_service.analyze_impact(
                contract_id=str(contract.id),
                model_name=model_name,
                field_name=field_name,
                max_contract_depth=depth,
                max_model_depth=depth,
                max_field_depth=depth if include_fields else 0,
                include_fields=include_fields,
            )
        except NotFoundError:
            return api_error_response(
                message="Contract not found",
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
            )

        # Check for errors
        if "error" in impact_result:
            return Response(
                impact_result,
                status=(
                    status.HTTP_404_NOT_FOUND
                    if "not found" in impact_result.get("error", "").lower()
                    else status.HTTP_400_BAD_REQUEST
                ),
            )

        # Format response based on format parameter
        if format_type == "csv":
            csv_string = ImpactVisualizer.generate_impact_csv(impact_result)
            return Response(
                csv_string,
                content_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="impact_analysis_{contract.id}.csv"'
                },
            )
        elif format_type == "dot":
            dot_string = ImpactVisualizer.generate_impact_dot(impact_result)
            return Response(dot_string, content_type="text/plain")
        elif format_type == "mermaid":
            mermaid_string = ImpactVisualizer.generate_impact_mermaid(impact_result)
            return Response(mermaid_string, content_type="text/plain")
        elif format_type == "paths":
            paths = ImpactVisualizer.generate_impact_paths(impact_result)
            return Response(
                {
                    "source": impact_result.get("source", {}),
                    "paths": paths,
                    "total_paths": len(paths),
                }
            )
        else:  # Default to JSON
            # Generate JSON visualization
            json_graph = ImpactVisualizer.generate_impact_json(impact_result)
            # Include impact_graph for backward compatibility and test expectations
            json_graph["impact_graph"] = impact_result.get("impact_graph", {})
            return Response(json_graph)
