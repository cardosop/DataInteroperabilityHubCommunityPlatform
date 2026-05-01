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


# ===========================================================================
# Phase 228 F5 (REQ-LIN-F5-001 / DoD-G6 + DoD-G7) — observability helpers
# for the time-travel surface.
# ===========================================================================

def _record_time_travel_metric(*, query_type: str) -> None:
    """Emit ``lineage_time_travel_queries_total{type}`` per
    REQ-LIN-F5-001. Best-effort: a metrics-emit failure must not fail
    the read."""
    try:
        from hub.apps.observability.metrics import (
            lineage_time_travel_queries_total,
        )
    except Exception:  # noqa: BLE001 — metrics module optional at import.
        return
    try:
        lineage_time_travel_queries_total.labels(type=query_type).inc()
    except Exception:  # noqa: BLE001 — best-effort.
        pass


def _emit_snapshot_audit(
    *,
    tenant_id,
    user_id,
    contract_id,
    as_of,
    source: str,
) -> None:
    """Emit ``LINEAGE_SNAPSHOT_QUERIED`` audit per REQ-LIN-F5-001.
    Best-effort fail-soft: an audit-emit failure must not fail the
    read.

    The audit row carries the contract id + the resolved cutoff +
    the source label (`as_of` | `version`) so a compliance review
    can answer "who looked at lineage at what historical point in
    time, and how did they specify it"."""
    try:
        from hub.apps.audit.models import LINEAGE_SNAPSHOT_QUERIED
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant
        from django.contrib.auth import get_user_model
    except Exception:  # noqa: BLE001 — audit optional at import.
        return
    try:
        tenant = None
        if tenant_id:
            tenant = Tenant.objects.filter(pk=tenant_id).first()
        actor_user = None
        if user_id:
            actor_user = get_user_model().objects.filter(pk=user_id).first()
        create_audit_event(
            resource_type="LINEAGE",
            action=LINEAGE_SNAPSHOT_QUERIED,
            actor_user=actor_user,
            tenant=tenant,
            resource_id=str(contract_id) if contract_id else None,
            details={
                "as_of": as_of.isoformat() if as_of is not None else None,
                "source": source,
            },
        )
    except Exception:  # noqa: BLE001 — best-effort.
        pass


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

    # =================================================================
    # Phase 228 F5 (REQ-LIN-F5-002 / 228.F5.3) — point-in-time diff.
    # =================================================================

    @extend_schema(
        summary="Diff lineage between two points in time",
        description=(
            "Compute the set-arithmetic delta between the contract's "
            "lineage edge state at two anchors. Anchors accept "
            "ISO-8601 (`from=2026-04-30T00:00:00Z`) or version-int "
            "(`from_version=3`); ``to`` defaults to NOW() when "
            "omitted. Returns ``{added, removed, changed, unchanged, "
            "summary}`` with deterministic ordering. Pure function "
            "behind the response — driven by "
            "[lineage_diff.py](../lineage_diff.py)."
        ),
        parameters=[
            OpenApiParameter(
                name="from", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="ISO-8601 timestamp for the older anchor.",
                required=False,
            ),
            OpenApiParameter(
                name="to", type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="ISO-8601 timestamp for the newer anchor; defaults to NOW().",
                required=False,
            ),
            OpenApiParameter(
                name="from_version", type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Contract version int → resolves to its created_at.",
                required=False,
            ),
            OpenApiParameter(
                name="to_version", type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description="Contract version int → resolves to its created_at.",
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Lineage diff body."),
            400: OpenApiResponse(description="Invalid from/to value."),
            404: OpenApiResponse(description="Contract or version not found."),
        },
        tags=["Contracts", "Lineage"],
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="lineage/diff",
        url_name="lineage-diff",
    )
    def get_lineage_diff(self, request, id=None):
        """``GET /api/v1/contracts/{id}/lineage/diff/?from=&to=``."""
        from datetime import datetime as _dt
        from django.utils import timezone as _tz
        from django.utils.dateparse import parse_datetime

        from hub.apps.contracts.lineage_diff import compute_diff
        from hub.apps.contracts.models import Contract

        contract = self.get_object()
        contract_id = str(contract.id)

        tenant_id = _get_tenant_id_from_request(request)
        user_id = str(request.user.id) if request.user and request.user.is_authenticated else None

        def _resolve_anchor(*, ts_param, version_param, default_now):
            """Resolve an anchor from query params: timestamp wins
            over version. Returns (datetime, source_label) or
            ``Response`` on error."""
            if ts_param:
                parsed = parse_datetime(ts_param)
                if parsed is None:
                    return Response(
                        {"error": {
                            "code": "INVALID_ANCHOR",
                            "message": f"could not parse {ts_param!r} as ISO-8601",
                        }},
                        status=400,
                    )
                return parsed, "timestamp"
            if version_param:
                try:
                    version_int = int(version_param)
                except (TypeError, ValueError):
                    return Response(
                        {"error": {
                            "code": "INVALID_VERSION",
                            "message": "version must be an integer",
                        }},
                        status=400,
                    )
                anchor = (
                    Contract.objects.filter(
                        tenant_id=tenant_id, version=version_int,
                    )
                    .order_by("created_at")
                    .first()
                )
                if anchor is None:
                    return Response(
                        {"error": {
                            "code": "VERSION_NOT_FOUND",
                            "message": f"No contract version {version_int} for tenant",
                        }},
                        status=404,
                    )
                return anchor.created_at, "version"
            if default_now:
                return _tz.now(), "now"
            return None, None

        from_resolved = _resolve_anchor(
            ts_param=request.query_params.get("from"),
            version_param=request.query_params.get("from_version"),
            default_now=False,
        )
        if isinstance(from_resolved, Response):
            return from_resolved
        from_ts, from_source = from_resolved

        to_resolved = _resolve_anchor(
            ts_param=request.query_params.get("to"),
            version_param=request.query_params.get("to_version"),
            default_now=True,
        )
        if isinstance(to_resolved, Response):
            return to_resolved
        to_ts, to_source = to_resolved

        if from_ts is None:
            return Response(
                {"error": {
                    "code": "MISSING_FROM_ANCHOR",
                    "message": "either ?from=<ISO8601> or ?from_version=<int> is required",
                }},
                status=400,
            )

        # Build the two snapshots via the existing time-travel
        # _edges_at — both directions so we cover incoming + outgoing
        # edges anchored to this contract.
        svc = LineageService(tenant_id=tenant_id, user_id=user_id)

        def _snapshot(at: _dt) -> list:
            return svc._edges_at(contract_id, as_of=at, direction="incoming") + \
                   svc._edges_at(contract_id, as_of=at, direction="outgoing")

        left = _snapshot(from_ts)
        right = _snapshot(to_ts)
        diff = compute_diff(left=left, right=right)

        # Echo the resolved anchors so the caller can render the
        # window in the UI without re-parsing.
        diff["from"] = {"timestamp": from_ts.isoformat(), "source": from_source}
        diff["to"] = {"timestamp": to_ts.isoformat(), "source": to_source}
        return Response(diff)

    @extend_schema(
        summary="Get lineage visualization",
        description=(
            "Get lineage graph in various visualization formats.\n\n"
            "Supports JSON (D3.js), DOT (Graphviz), and Mermaid formats.\n\n"
            "Phase 228 F5 (228.F5.2 / REQ-LIN-F5-001) — point-in-time "
            "knobs `?as_of=<ISO8601>` (direct historical cutoff) and "
            "`?version=<int>` (resolves to the contract's `created_at` "
            "for that version). Both knobs echo back in the response "
            "as `as_of` + `as_of_source ∈ {as_of, version}` so the UI "
            "can render the resolved cutoff without re-parsing query "
            "params. When both are supplied, `as_of` wins."
        ),
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
            # Phase 228 F5 (228.F5.2 / REQ-LIN-F5-001) — point-in-time.
            OpenApiParameter(
                name="as_of",
                type=OpenApiTypes.DATETIME,
                location=OpenApiParameter.QUERY,
                description=(
                    "ISO-8601 timestamp; renders the lineage at that "
                    "historical cutoff. Mutually-permissive with "
                    "`?version=`; when both provided, `as_of` wins."
                ),
                required=False,
            ),
            OpenApiParameter(
                name="version",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description=(
                    "Contract version int; resolves to that "
                    "contract's `created_at` and uses it as the "
                    "`as_of` cutoff. 404 when the version doesn't "
                    "exist for the tenant."
                ),
                required=False,
            ),
            OpenApiParameter(
                name="include_fields",
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description=(
                    "Phase 228.F2 (228.F2.3) — augment JSON "
                    "visualization with field-level nodes derived "
                    "from open LineageEdge rows."
                ),
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(description="Lineage graph in requested format"),
            400: OpenApiResponse(description="Malformed `?as_of=` or non-int `?version=`."),
            404: OpenApiResponse(description="Contract or version not found"),
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

        # Phase 228 F5 (REQ-LIN-F5-001 / 228.F5.2) — point-in-time
        # visualization. Spec-compliant resolution:
        #
        #   ?as_of=<ISO8601>   — direct historical cutoff.
        #   ?version=<int>     — resolves to the Contract.created_at
        #                        for the matching (tenant, version) row.
        #
        # Spec rules (REQ-LIN-F5-001):
        #   1. Both supplied → HTTP 400 (mutually exclusive).
        #   2. Neither supplied → current state (existing behaviour).
        #   3. Capability ``lineage.snapshots`` OFF → params silently
        #      ignored to keep the API backward-compatible.
        #   4. Emit metric `lineage_time_travel_queries_total{type}`.
        #   5. Emit audit event `LINEAGE_SNAPSHOT_QUERIED`.
        from datetime import datetime as _dt
        from django.utils.dateparse import parse_datetime

        as_of_param = request.query_params.get("as_of")
        version_param = request.query_params.get("version")

        # Spec rule 1 — mutual exclusivity.
        if as_of_param and version_param:
            return Response(
                {"error": {
                    "code": "AS_OF_AND_VERSION_MUTUALLY_EXCLUSIVE",
                    "message": "Provide either ?as_of= or ?version=, not both.",
                }},
                status=400,
            )

        # Spec rule 3 — feature flag silently disables the params.
        # Phase 228 F5 (228.F5.DoD.6) — per-tenant rollout: when the
        # global flag is OFF, allow the per-tenant override list to
        # promote the call. Lets ops run 5 internal canary tenants,
        # then 50%, then 100% via Helm value flips alone.
        from hub.apps.api.capabilities import is_capability_enabled_for_tenant
        snapshots_enabled = is_capability_enabled_for_tenant(
            "lineage.snapshots", tenant_id,
        )

        as_of_cutoff: _dt | None = None
        as_of_source: str | None = None

        if (as_of_param or version_param) and not snapshots_enabled:
            # Flag OFF — silently ignore; surface a hint in the
            # response so an operator with the flag-disabled deployment
            # can see why their date picker was no-op.
            as_of_source = "ignored_flag_off"
        elif as_of_param:
            parsed = parse_datetime(as_of_param)
            if parsed is None:
                return Response(
                    {"error": {
                        "code": "INVALID_AS_OF",
                        "message": "as_of must be ISO 8601 (e.g. 2026-04-30T12:00:00Z)",
                    }},
                    status=400,
                )
            as_of_cutoff = parsed
            as_of_source = "as_of"
        elif version_param:
            try:
                version_int = int(version_param)
            except (TypeError, ValueError):
                return Response(
                    {"error": {"code": "INVALID_VERSION",
                               "message": "version must be an integer"}},
                    status=400,
                )
            from hub.apps.contracts.models import Contract
            anchor = Contract.objects.filter(
                tenant_id=tenant_id, version=version_int,
                id=contract_id,
            ).first()
            if anchor is None:
                anchor = Contract.objects.filter(
                    tenant_id=tenant_id, version=version_int,
                ).first()
            if anchor is None:
                return Response(
                    {"error": {
                        "code": "VERSION_NOT_FOUND",
                        "message": f"No contract version {version_int} for tenant",
                    }},
                    status=404,
                )
            as_of_cutoff = anchor.created_at
            as_of_source = "version"

        # Spec rule 4 — metric emission. Best-effort; a metric-emit
        # failure must not fail the read.
        if as_of_source in ("as_of", "version"):
            _record_time_travel_metric(query_type=as_of_source)
            # Spec rule 5 — audit event.
            _emit_snapshot_audit(
                tenant_id=tenant_id,
                user_id=user_id,
                contract_id=contract_id,
                as_of=as_of_cutoff,
                source=as_of_source,
            )

        result = lineage_service.get_lineage_visualization(
            contract_id=contract_id, format=format_type, max_depth=max_depth,
            as_of=as_of_cutoff,
        )

        if as_of_source is not None and isinstance(result, dict):
            result.setdefault("as_of_source", as_of_source)
            if as_of_cutoff is not None:
                result.setdefault("as_of", as_of_cutoff.isoformat())

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
