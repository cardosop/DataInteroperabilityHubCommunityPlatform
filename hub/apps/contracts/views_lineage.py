"""
Contract Views Lineage Operations

Lineage-related actions for contract viewsets.

SAVING CHECKPOINT: This module contains all lineage-related actions.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response

from hub.apps.core.services.base import NotFoundError

from .lineage_service import LineageService
from .views_helpers import _get_tenant_id_from_request


class ContractLineageMixin:
    """
    Mixin for Contract lineage operations.

    Provides lineage-related actions including field, model, contract, hierarchical,
    and visualization endpoints.
    """

    @extend_schema(
        summary="Get field-level lineage",
        description="""
        Get lineage for a specific field in a contract.

        Returns lineage information including field references and entries.
        """,
        parameters=[
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Model name (optional)",
                required=False,
            ),
        ],
        responses={
            200: inline_serializer(
                name="FieldLineageResponse",
                fields={
                    "field_name": serializers.CharField(),
                    "lineage": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract or field not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="fields/(?P<field_name>[^/.]+)/lineage")
    def get_field_lineage(self, request, id=None, field_name=None):
        """
        Get field-level lineage with caching support.
        Uses LineageService which publishes events automatically.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        # Try to get model_name from query params or infer from contract
        model_name = request.query_params.get("model_name")

        try:
            result = lineage_service.get_field_lineage(
                contract_id=contract_id,
                field_name=field_name,
                model_name=model_name,
                use_cache=True,
            )
            return Response(result)
        except NotFoundError:
            return Response(
                {"error": f"Field {field_name} not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Get model-level lineage",
        description="""
        Get lineage for a specific model in a contract.

        Returns lineage information including model references and entries.
        """,
        parameters=[
            OpenApiParameter(
                name="model_name",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description="Model name",
                required=True,
            ),
        ],
        responses={
            200: inline_serializer(
                name="ModelLineageResponse",
                fields={
                    "model_name": serializers.CharField(),
                    "lineage": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract or model not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="models/(?P<model_name>[^/.]+)/lineage")
    def get_model_lineage(self, request, id=None, model_name=None):
        """
        Get model-level lineage with caching support.
        Uses LineageService which publishes events automatically.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        try:
            result = lineage_service.get_model_lineage(
                contract_id=contract_id, model_name=model_name, use_cache=True
            )
            return Response(result)
        except NotFoundError:
            return Response(
                {"error": f"Model {model_name} not found"}, status=status.HTTP_404_NOT_FOUND
            )

    @extend_schema(
        summary="Get contract-level lineage",
        description="""
        Get contract-level lineage including contract references.

        Returns contract references and lineage entries.
        """,
        responses={
            200: inline_serializer(
                name="ContractLineageResponse",
                fields={
                    "contracts": serializers.ListField(),
                    "entries": serializers.ListField(),
                },
            ),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="lineage/contracts")
    def get_contract_lineage(self, request, id=None):
        """
        Get contract-level lineage with caching support.
        Uses LineageService which publishes events automatically.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        result = lineage_service.get_contract_lineage(contract_id=contract_id, use_cache=True)
        return Response(result)

    @extend_schema(
        summary="Get hierarchical lineage",
        description="""
        Get complete hierarchical lineage (contract, model, and field levels).

        Returns full lineage traversal with all levels.
        """,
        parameters=[
            OpenApiParameter(
                name="max_contract_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum contract depth for traversal (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="max_model_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum model depth for traversal (default: 10)",
                required=False,
            ),
            OpenApiParameter(
                name="max_field_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum field depth for traversal (default: 10)",
                required=False,
            ),
        ],
        responses={
            200: inline_serializer(
                name="HierarchicalLineageResponse",
                fields={
                    "upstream": serializers.DictField(),
                    "downstream": serializers.DictField(),
                },
            ),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(detail=True, methods=["get"], url_path="lineage/full")
    def get_hierarchical_lineage(self, request, id=None):
        """
        Get hierarchical lineage (bidirectional traversal).
        Uses LineageService which publishes events automatically.
        """
        contract = self.get_object()
        contract_id = str(contract.id)

        max_contract_depth = int(request.query_params.get("max_contract_depth", 10))
        max_model_depth = int(request.query_params.get("max_model_depth", 10))
        max_field_depth = int(request.query_params.get("max_field_depth", 10))

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        result = lineage_service.get_full_lineage(
            contract_id=contract_id,
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
            use_cache=False,  # Full lineage is expensive and depth params vary, so skip cache
        )

        return Response(result)

    @extend_schema(
        summary="Get lineage visualization",
        description="""
        Get lineage graph in various visualization formats.

        Supports JSON (D3.js), DOT (Graphviz), and Mermaid formats.
        """,
        parameters=[
            OpenApiParameter(
                name="format",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Visualization format: json, dot, or mermaid (default: json)",
                required=False,
            ),
            OpenApiParameter(
                name="max_depth",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Maximum traversal depth (default: 10)",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Lineage graph in requested format"),
            404: OpenApiResponse(description="Contract not found"),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="lineage/visualization",
        url_name="lineage-visualization",
    )
    def get_lineage_visualization(self, request, id=None):
        """
        Get lineage visualization in various formats.
        Uses LineageService which publishes events automatically.
        """
        # Use pre-retrieved contract if available (from custom view), otherwise use get_object()
        # This allows the custom URL view to bypass DRF's get_object() which may have issues
        # with manually instantiated viewsets
        if hasattr(self, "_contract"):
            contract = self._contract
            # Clean up the temporary attribute
            delattr(self, "_contract")
        else:
            # Use get_object() for proper tenant scoping and object retrieval
            # This is the same approach used by get_hierarchical_lineage which works correctly
            # get_object() handles tenant scoping automatically via get_queryset()
            contract = self.get_object()

        contract_id = str(contract.id)

        # Get format from query params - prioritize query param over format suffix
        # DRF's DefaultRouter creates format suffix patterns that can interfere with query params
        # CRITICAL: Check query parameter FIRST before any format suffix handling
        # This ensures ?format=dot works even if DRF tries to interpret it as a suffix
        # Use request.query_params (DRF's version) - this works with both DRF Request and Django HttpRequest
        # If request is a DRF Request, use query_params; if it's a Django HttpRequest, use GET
        if hasattr(request, "query_params"):
            format_param = request.query_params.get("format", "json").lower().strip()
        elif hasattr(request, "GET"):
            format_param = request.GET.get("format", "json").lower().strip()
        else:
            format_param = "json"

        # Also check DRF's format attribute (set by format suffix pattern) as fallback
        # But only if query param wasn't found
        if not format_param and hasattr(request, "format") and request.format:
            format_param = request.format.lower()

        format_type = format_param if format_param in ["json", "dot", "mermaid"] else "json"
        max_depth = int(request.query_params.get("max_depth", 10))

        # Phase 228.F2.3 (REQ-LIN-F2-001) — opt-in field-level
        # expansion.  Default False keeps the existing visualization
        # response shape identical (no surprise payload growth for
        # callers who haven't asked for the F2 surface).  When True,
        # the response carries the per-field nodes + links derived
        # from ``LineageEdge.source_field`` / ``target_field`` so the
        # F2 frontend editor can render them.
        include_fields_raw = request.query_params.get(
            "include_fields", "false"
        )
        include_fields = str(include_fields_raw).lower() in (
            "true", "1", "yes",
        )

        # Initialize LineageService with tenant_id and user_id
        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        lineage_service = LineageService(tenant_id=tenant_id, user_id=user_id)

        result = lineage_service.get_lineage_visualization(
            contract_id=contract_id, format=format_type, max_depth=max_depth
        )

        if include_fields and format_type == "json":
            # Augment the JSON visualization with field-level nodes
            # + links derived from current open LineageEdge rows.  We
            # only do this for the JSON format — DOT and Mermaid are
            # contract-level diagrams whose grammar doesn't carry
            # field-level structure cleanly.
            from hub.apps.contracts.models import LineageEdge

            field_nodes: list = []
            field_links: list = []
            seen_field_ids: set = set()
            for row in (
                LineageEdge.objects
                .filter(tenant_id=tenant_id, valid_to__isnull=True)
                .filter(
                    # Edges anchored to this contract on either side.
                    __import__("django.db.models", fromlist=["Q"]).Q(
                        source_contract_id=contract_id,
                    )
                    | __import__("django.db.models", fromlist=["Q"]).Q(
                        target_contract_id=contract_id,
                    )
                )
                .iterator(chunk_size=200)
            ):
                for side in ("source", "target"):
                    cid = (
                        row.source_contract_id if side == "source"
                        else row.target_contract_id
                    )
                    model = row.source_model if side == "source" else row.target_model
                    field = row.source_field if side == "source" else row.target_field
                    if not (cid and field):
                        continue
                    fid = f"field:{cid}:{model}.{field}"
                    if fid in seen_field_ids:
                        continue
                    seen_field_ids.add(fid)
                    field_nodes.append({
                        "id": fid,
                        "type": "field",
                        "label": f"{model}.{field}" if model else field,
                        "contract_id": str(cid),
                    })
                if (row.source_contract_id and row.source_field
                        and row.target_contract_id and row.target_field):
                    field_links.append({
                        "source": (
                            f"field:{row.source_contract_id}:"
                            f"{row.source_model}.{row.source_field}"
                        ),
                        "target": (
                            f"field:{row.target_contract_id}:"
                            f"{row.target_model}.{row.target_field}"
                        ),
                        "edge_type": row.edge_type,
                    })
            result.setdefault("field_nodes", []).extend(field_nodes)
            result.setdefault("field_links", []).extend(field_links)

        if format_type == "dot":
            return Response(result.get("dot", ""), content_type="text/plain")
        elif format_type == "mermaid":
            return Response(result.get("mermaid", ""), content_type="text/plain")
        else:  # Default to JSON
            return Response(result)
