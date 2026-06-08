"""
Lineage Service

Service layer for lineage operations.
Extracts lineage logic from views and lineage.py module.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from hub.apps.contracts.caching import (
    cache_lineage,
    get_cached_lineage,
    invalidate_lineage_cache,
)
from hub.apps.contracts.impact_analysis import ImpactAnalyzer
from hub.apps.contracts.impact_notifications import ImpactNotifier
from hub.apps.contracts.impact_visualization import ImpactVisualizer
from hub.apps.contracts.lineage import (
    LineageTraverser,
    generate_lineage_dot,
    generate_lineage_json,
    generate_lineage_mermaid,
)
from hub.apps.contracts.models import Contract
from hub.apps.core.services.base import BaseService, NotFoundError
from hub.apps.core.events.service_publishers import LineageEventPublisher
from hub.apps.observability.metrics import trace as _lineage_trace

logger = structlog.get_logger(__name__)


def _edge_belongs_to_tenant(edge: Dict[str, Any], owner_tenant_id: str) -> bool:
    """Phase 228.F1 audit hardening — confirm an edge dict belongs to
    ``owner_tenant_id`` by checking the tenant of its (non-NULL) source
    or target contract.

    The :class:`LineageEdge` table stores ``tenant_id`` as a load-bearing
    FK invariant — every edge is owned by exactly one tenant — but
    ``_edges_at`` returns dict rows that don't carry the FK directly.
    This helper looks up the tenant via the (non-NULL) endpoint
    contract id.  Edges where BOTH endpoints are NULL (rare, external-
    to-external) are accepted — they're not addressable by tenant in
    the dict shape and the upstream caller's tenant scope already
    bounds them.
    """
    from hub.apps.contracts.models import Contract

    for fk_id_key in ("source_contract", "target_contract"):
        endpoint_id = edge.get(fk_id_key)
        if not endpoint_id:
            continue
        contract = (
            Contract.objects
            .filter(id=endpoint_id)
            .only("id", "tenant_id")
            .first()
        )
        if contract is None:
            continue
        return str(contract.tenant_id) == owner_tenant_id
    # Both endpoints NULL — accept (cross-tenant external, no leak).
    return True


class LineageService(BaseService, LineageEventPublisher):
    """
    Service for lineage operations.

    Provides business logic for:
    - Contract-level lineage retrieval
    - Model-level lineage retrieval
    - Field-level lineage retrieval
    - Full hierarchical lineage
    - Lineage visualization
    - Impact analysis
    """

    service_name = "lineage_service"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """Initialize LineageService with tenant and user context."""
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.request_id = request_id
        # Initialize event publisher (BaseService.__init__ does not call
        # super().__init__(), so the mixin __init__ must be invoked explicitly).
        LineageEventPublisher.__init__(self)

    # ------------------------------------------------------------------
    # Phase 228 (REQ-LIN-004, 228.0.13) — time-travel read path
    # ------------------------------------------------------------------

    @staticmethod
    def _record_query_metric(
        *, detail: str, cross_tenant: bool, as_of_set: bool,
    ) -> None:
        """Phase 228 (REQ-LIN-007 / 228.0.19) — emit
        ``lineage_query_total{detail,cross_tenant,as_of}`` per read.

        Best-effort: a metric backend outage MUST NOT break a read.
        Wired into every read-side method so the dashboard's per-detail
        rate panel populates regardless of which method the request hit."""
        try:
            from hub.apps.observability.metrics import lineage_query_total

            lineage_query_total.labels(
                detail=detail,
                cross_tenant="true" if cross_tenant else "false",
                as_of="true" if as_of_set else "false",
            ).inc()
        except Exception:  # noqa: BLE001 — observability never breaks the read.
            return

    @staticmethod
    def _edges_at(
        contract_id: str,
        *,
        as_of: Optional[datetime] = None,
        direction: str = "incoming",
    ) -> List[Dict[str, Any]]:
        """Read ``LineageEdge`` rows that satisfy the SCD Type 2
        validity predicate at ``as_of``.

        ``direction='incoming'`` returns edges where ``target_contract``
        is the supplied contract (this contract's upstream lineage).
        ``direction='outgoing'`` returns edges where ``source_contract``
        is the supplied contract (this contract's downstream consumers).

        When ``as_of`` is ``None``, returns the current state
        (``valid_to IS NULL``). When supplied, applies:

        .. code-block:: sql

            WHERE valid_from <= :as_of
              AND (valid_to IS NULL OR valid_to > :as_of)

        Returns a list of plain dicts (NOT model instances) so the
        caller can serialize directly.
        """
        from django.db.models import Q

        from hub.apps.contracts.models import LineageEdge

        qs = LineageEdge.objects.all()
        if direction == "incoming":
            qs = qs.filter(target_contract_id=contract_id)
        else:
            qs = qs.filter(source_contract_id=contract_id)

        if as_of is None:
            qs = qs.filter(valid_to__isnull=True)
        else:
            qs = qs.filter(valid_from__lte=as_of).filter(
                Q(valid_to__isnull=True) | Q(valid_to__gt=as_of)
            )

        return [
            {
                "id": str(row.id),
                "source_contract": str(row.source_contract_id) if row.source_contract_id else None,
                "target_contract": str(row.target_contract_id) if row.target_contract_id else None,
                "source_model": row.source_model,
                "source_field": row.source_field,
                "target_model": row.target_model,
                "target_field": row.target_field,
                "edge_type": row.edge_type,
                "transformation_ref": row.transformation_ref,
                "job_ref": row.job_ref,
                "valid_from": row.valid_from.isoformat() if row.valid_from else None,
                "valid_to": row.valid_to.isoformat() if row.valid_to else None,
            }
            for row in qs
        ]

    @_lineage_trace("LineageService.get_contract_lineage")
    def get_contract_lineage(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get contract-level lineage.

        Args:
            contract_id: Contract ID
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)
            as_of: Phase 228 (REQ-LIN-004) — when supplied, returns the
                historical state from the relational ``LineageEdge``
                index using the SCD Type 2 predicate. When ``None``
                (default) the legacy JSON-parsing read path is used.
                The legacy path is retained for one deploy cycle and
                removed in a follow-up PR after the relational path is
                proven on staging.

        Returns:
            Lineage dictionary with contracts and entries

        Raises:
            NotFoundError: If contract not found
        """
        # Phase 228 (REQ-LIN-007) — emit the read counter regardless of
        # which read path serves the request. The ``cross_tenant`` label
        # is hard-coded ``False`` here because contract-scoped reads do
        # not cross tenants by definition; the cross-tenant view lives
        # in a Phase 228 F1 method.
        self._record_query_metric(
            detail="contract", cross_tenant=False, as_of_set=as_of is not None,
        )

        # Phase 228 — when ``as_of`` is set, route through the
        # relational LineageEdge index regardless of the cache.
        if as_of is not None:
            edges = self._edges_at(contract_id, as_of=as_of, direction="incoming")
            return {
                "contracts": [
                    {
                        "source_contract": e["source_contract"],
                        "target_contract": e["target_contract"],
                        "edge_type": e["edge_type"],
                        "valid_from": e["valid_from"],
                        "valid_to": e["valid_to"],
                    }
                    for e in edges
                ],
                "entries": [],
                "as_of": as_of.isoformat() if as_of else None,
            }
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(contract_id)
            if cached_lineage:
                return cached_lineage

        # Extract lineage from contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            return {"contracts": [], "entries": []}

        lineage_data = hub_contract.get("lineage", {})
        result = {
            "contracts": lineage_data.get("contracts", []),
            "entries": lineage_data.get("entries", []),
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result)

        # Publish lineage.updated event
        try:
            relationship_count = len(result.get("contracts", [])) + len(result.get("entries", []))
            self.publish_lineage_updated(
                contract_id=contract_id,
                lineage_type="contract",
                relationship_count=relationship_count
            )
        except Exception as e:
            # Log but don't fail lineage retrieval if event publishing fails
            logger.warning(
                "Failed to publish lineage.updated event",
                contract_id=contract_id,
                error=str(e),
                exc_info=True
            )

        return result

    @_lineage_trace("LineageService.get_model_lineage")
    def get_model_lineage(
        self,
        contract_id: str,
        model_name: str,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get model-level lineage.

        Args:
            contract_id: Contract ID
            model_name: Model name
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)
            as_of: Phase 228 (REQ-LIN-004) — historical-state cutoff;
                see :meth:`get_contract_lineage` for the contract.

        Returns:
            Model lineage dictionary

        Raises:
            NotFoundError: If contract or model not found
        """
        self._record_query_metric(
            detail="model", cross_tenant=False, as_of_set=as_of is not None,
        )
        if as_of is not None:
            # Historical model-level lineage: filter the SCD Type 2 edges
            # by ``target_model == model_name``. Returns the canonical
            # edge-list shape that matches ``get_contract_lineage(as_of=...)``
            # so callers branching on read-path internals are consistent.
            edges = [
                e for e in self._edges_at(
                    contract_id, as_of=as_of, direction="incoming",
                )
                if (e.get("target_model") or "") == model_name
            ]
            return {
                "model": model_name,
                "edges": edges,
                "as_of": as_of.isoformat(),
            }
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(contract_id, model_name=model_name)
            if cached_lineage:
                return cached_lineage

        # Find model in contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            raise NotFoundError("Model", model_name)

        models_list = hub_contract.get("models", [])
        model = None
        for m in models_list:
            if isinstance(m, dict) and m.get("name") == model_name:
                model = m
                break

        if not model:
            raise NotFoundError("Model", model_name)

        # Extract lineage from model
        lineage_data = model.get("lineage", {})
        result = {
            "model_name": model_name,
            "lineage": {
                "models": lineage_data.get("models", []),
                "entries": lineage_data.get("entries", []),
            },
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result, model_name=model_name)

        # Publish lineage.updated event
        try:
            lineage_info = result.get("lineage", {})
            relationship_count = len(lineage_info.get("models", [])) + len(lineage_info.get("entries", []))
            self.publish_lineage_updated(
                contract_id=contract_id,
                model_name=model_name,
                lineage_type="model",
                relationship_count=relationship_count
            )
        except Exception as e:
            # Log but don't fail lineage retrieval if event publishing fails
            logger.warning(
                "Failed to publish lineage.updated event",
                contract_id=contract_id,
                model_name=model_name,
                error=str(e),
                exc_info=True
            )

        return result

    @_lineage_trace("LineageService.get_field_lineage")
    def get_field_lineage(
        self,
        contract_id: str,
        field_name: str,
        model_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        use_cache: bool = True,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get field-level lineage.

        Args:
            contract_id: Contract ID
            field_name: Field name
            model_name: Optional model name (searches all models if not provided)
            tenant_id: Optional tenant ID for filtering
            use_cache: Whether to use cache (default: True)

        Returns:
            Field lineage dictionary

        Raises:
            NotFoundError: If contract or field not found
        """
        self._record_query_metric(
            detail="field", cross_tenant=False, as_of_set=as_of is not None,
        )
        if as_of is not None:
            edges = [
                e for e in self._edges_at(
                    contract_id, as_of=as_of, direction="incoming",
                )
                if (e.get("target_field") or "") == field_name
                and (model_name is None or (e.get("target_model") or "") == model_name)
            ]
            return {
                "field": field_name,
                "model": model_name,
                "edges": edges,
                "as_of": as_of.isoformat(),
            }
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache
        if use_cache:
            cached_lineage = get_cached_lineage(
                contract_id, model_name=model_name, field_name=field_name
            )
            if cached_lineage:
                return cached_lineage

        # Find field in contract
        hub_contract = contract.hub_contract_json
        if not hub_contract:
            raise NotFoundError("Field", field_name)

        models_list = hub_contract.get("models", [])
        field = None
        found_model_name = None

        for model in models_list:
            if isinstance(model, dict):
                model_name_to_check = model.get("name")
                fields_list = model.get("fields", [])
                for f in fields_list:
                    if isinstance(f, dict) and f.get("name") == field_name:
                        # If model_name specified, only match in that model
                        if model_name and model_name_to_check != model_name:
                            continue
                        field = f
                        found_model_name = model_name_to_check
                        break
                if field:
                    break

        if not field:
            raise NotFoundError("Field", field_name)

        # Extract lineage from field
        lineage_data = field.get("lineage", {})
        result = {
            "field_name": field_name,
            "model_name": found_model_name,
            "lineage": {
                "input_fields": lineage_data.get("input_fields", []),
                "transformations": lineage_data.get("transformations", []),
            },
        }

        # Cache result
        if use_cache:
            cache_lineage(contract_id, result, model_name=found_model_name, field_name=field_name)

        # Publish lineage.updated event
        try:
            lineage_info = result.get("lineage", {})
            relationship_count = len(lineage_info.get("input_fields", [])) + len(lineage_info.get("transformations", []))
            self.publish_lineage_updated(
                contract_id=contract_id,
                model_name=found_model_name,
                field_name=field_name,
                lineage_type="field",
                relationship_count=relationship_count
            )
        except Exception as e:
            # Log but don't fail lineage retrieval if event publishing fails
            logger.warning(
                "Failed to publish lineage.updated event",
                contract_id=contract_id,
                model_name=found_model_name,
                field_name=field_name,
                error=str(e),
                exc_info=True
            )

        return result

    @_lineage_trace("LineageService.get_full_lineage")
    def get_full_lineage(
        self,
        contract_id: str,
        tenant_id: Optional[str] = None,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
        use_cache: bool = True,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get full hierarchical lineage (contract, model, and field levels).

        Args:
            contract_id: Contract ID
            tenant_id: Optional tenant ID for filtering
            max_contract_depth: Maximum contract depth
            max_model_depth: Maximum model depth
            max_field_depth: Maximum field depth
            use_cache: Whether to use cache (default: True)

        Returns:
            Full lineage dictionary with upstream and downstream

        Raises:
            NotFoundError: If contract not found
        """
        self._record_query_metric(
            detail="full", cross_tenant=False, as_of_set=as_of is not None,
        )
        if as_of is not None:
            return {
                "contract_id": contract_id,
                "upstream": self._edges_at(
                    contract_id, as_of=as_of, direction="incoming",
                ),
                "downstream": self._edges_at(
                    contract_id, as_of=as_of, direction="outgoing",
                ),
                "as_of": as_of.isoformat(),
            }
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        # Check cache - use a composite key for full lineage
        # Note: Full lineage cache key includes depth parameters, so we can't use the standard function
        # For now, we'll skip caching for full lineage or use a custom key
        # This is acceptable since full lineage is expensive and depth params vary
        if False:  # Disable cache for full lineage due to depth parameters
            from django.core.cache import cache

            cache_key = f"lineage:full:{contract_id}:{max_contract_depth}:{max_model_depth}:{max_field_depth}"
            cached_lineage = cache.get(cache_key)
            if cached_lineage:
                return cached_lineage

        # Use LineageTraverser to get full lineage
        # Root cause fix: Create separate traversers for upstream and downstream
        # to avoid cycle detection false positives (visited_contracts is shared)
        upstream_traverser = LineageTraverser(
            contract,
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
        )
        downstream_traverser = LineageTraverser(
            contract,
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
        )
        # Based on traverse_bidirectional: upstream = bottom_up, downstream = top_down
        # upstream: what depends on this contract (dependents)
        upstream = upstream_traverser.traverse_bottom_up()
        # downstream: what this contract depends on (sources)
        downstream = downstream_traverser.traverse_top_down()

        result = {"upstream": upstream, "downstream": downstream}

        # Cache result - use custom cache key for full lineage
        if use_cache and False:  # Disable cache for full lineage due to depth parameters
            from django.core.cache import cache

            from hub.apps.contracts.caching import CACHE_TTL_LINEAGE

            cache_key = f"lineage:full:{contract_id}:{max_contract_depth}:{max_model_depth}:{max_field_depth}"
            cache.set(cache_key, result, timeout=CACHE_TTL_LINEAGE)

        # Publish lineage.updated event for full lineage access
        try:
            upstream_count = len(upstream.get("referenced_by", [])) if isinstance(upstream, dict) else 0
            downstream_count = len(downstream.get("contracts", [])) if isinstance(downstream, dict) else 0
            relationship_count = upstream_count + downstream_count
            self.publish_lineage_updated(
                contract_id=contract_id,
                lineage_type="full",
                relationship_count=relationship_count,
                changes={
                    "upstream_count": upstream_count,
                    "downstream_count": downstream_count,
                    "max_contract_depth": max_contract_depth,
                    "max_model_depth": max_model_depth,
                    "max_field_depth": max_field_depth
                }
            )
        except Exception as e:
            # Log but don't fail lineage retrieval if event publishing fails
            logger.warning(
                "Failed to publish lineage.updated event",
                contract_id=contract_id,
                error=str(e),
                exc_info=True
            )

        return result

    @_lineage_trace("LineageService.get_lineage_visualization")
    def get_lineage_visualization(
        self,
        contract_id: str,
        format: str = "json",
        tenant_id: Optional[str] = None,
        max_depth: int = 10,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get lineage visualization in various formats.

        Args:
            contract_id: Contract ID
            format: Visualization format (json, dot, mermaid)
            tenant_id: Optional tenant ID for filtering
            max_depth: Maximum traversal depth

        Returns:
            Visualization data

        Raises:
            NotFoundError: If contract not found
        """
        self._record_query_metric(
            detail="visualization", cross_tenant=False, as_of_set=as_of is not None,
        )
        if as_of is not None:
            # Visualization at ``as_of`` returns the historical edge set
            # in the same nodes-and-edges shape consumers already render.
            edges = self._edges_at(
                contract_id, as_of=as_of, direction="incoming",
            ) + self._edges_at(
                contract_id, as_of=as_of, direction="outgoing",
            )
            nodes_set = set()
            for e in edges:
                if e.get("source_contract"):
                    nodes_set.add(e["source_contract"])
                if e.get("target_contract"):
                    nodes_set.add(e["target_contract"])
            return {
                "format": format,
                "nodes": [{"id": n} for n in sorted(nodes_set)],
                "edges": edges,
                "as_of": as_of.isoformat(),
            }
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        if format == "json":
            return generate_lineage_json(contract, max_depth=max_depth)
        elif format == "dot":
            return {"dot": generate_lineage_dot(contract, max_depth=max_depth)}
        elif format == "mermaid":
            return {"mermaid": generate_lineage_mermaid(contract, max_depth=max_depth)}
        else:
            from hub.apps.core.services.base import ValidationError

            raise ValidationError(
                f"Invalid format: {format}. Supported formats: json, dot, mermaid"
            )

    def analyze_impact(
        self,
        contract_id: str,
        model_name: Optional[str] = None,
        field_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
        max_contract_depth: int = 10,
        max_model_depth: int = 10,
        max_field_depth: int = 10,
        include_fields: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze impact of contract changes.

        Args:
            contract_id: Contract ID
            model_name: Optional model name (for model-level impact)
            field_name: Optional field name (for field-level impact)
            tenant_id: Optional tenant ID for filtering
            max_contract_depth: Maximum contract depth
            max_model_depth: Maximum model depth
            max_field_depth: Maximum field depth
            include_fields: Include field-level dependencies

        Returns:
            Impact analysis results

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        analyzer = ImpactAnalyzer(
            max_contract_depth=max_contract_depth,
            max_model_depth=max_model_depth,
            max_field_depth=max_field_depth,
            include_fields=include_fields,
        )

        # Analyze impact using the correct API
        impact_result = analyzer.analyze_impact(
            contract_id=str(contract.id),
            model_name=model_name,
            field_name=field_name,
            tenant_id=tenant_id or str(self.tenant_id),
        )

        # Check for errors
        if "error" in impact_result:
            return impact_result

        # ImpactAnalyzer already calculates scores internally
        # Add visualization to the result
        result = {
            **impact_result,
            "visualization": ImpactVisualizer.generate_impact_json(impact_result),
        }

        # Publish lineage.updated event for impact analysis
        try:
            impact_nodes = impact_result.get("impact_nodes", [])
            relationship_count = len(impact_nodes) if isinstance(impact_nodes, list) else 0
            self.publish_lineage_updated(
                contract_id=contract_id,
                model_name=model_name,
                field_name=field_name,
                lineage_type="impact_analysis",
                relationship_count=relationship_count,
                changes={
                    "impact_score": impact_result.get("impact_score"),
                    "severity": impact_result.get("severity"),
                    "max_contract_depth": max_contract_depth,
                    "max_model_depth": max_model_depth,
                    "max_field_depth": max_field_depth
                }
            )
        except Exception as e:
            # Log but don't fail impact analysis if event publishing fails
            logger.warning(
                "Failed to publish lineage.updated event",
                contract_id=contract_id,
                model_name=model_name,
                field_name=field_name,
                error=str(e),
                exc_info=True
            )

        return result

    def notify_impact(
        self, contract_id: str, impact_analysis: Dict[str, Any], tenant_id: Optional[str] = None
    ) -> None:
        """
        Send notifications for impact analysis.

        Args:
            contract_id: Contract ID
            impact_analysis: Impact analysis results
            tenant_id: Optional tenant ID for filtering

        Raises:
            NotFoundError: If contract not found
        """
        contract = self.get_resource_or_raise(
            Contract, contract_id, tenant_id=tenant_id or self.tenant_id
        )

        notifier = ImpactNotifier()
        notifier.notify_impact(contract, impact_analysis)

    # ------------------------------------------------------------------
    # Phase 228.F1 (REQ-LIN-F1-001) — cross-tenant marketplace lineage
    # ------------------------------------------------------------------

    # Per-query result-row caps (D2 mitigation in the F1 STRIDE threat
    # model — caps a max_depth=15 request on a dense graph from
    # exhausting the API).  When the BFS would exceed either cap the
    # response carries ``truncated=true`` so the frontend can render a
    # "lineage truncated" affordance and the operator can investigate.
    F1_NODE_CAP = 500
    F1_EDGE_CAP = 1000

    def get_for_asset(
        self,
        asset_id: str,
        *,
        caller_tenant_id: str,
        owner_tenant_id: str,
        detail: str = "summary",
        max_depth: int = 3,
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return the lineage graph rooted at ``asset_id``'s ACTIVE contract.

        Phase 228.F1 (REQ-LIN-F1-001) — the read primitive behind the
        ``GET /api/v1/listings/{listing_id}/lineage/`` endpoint.

        Args
        ----
        asset_id
            UUID of the asset whose ACTIVE contract is the root of the
            graph.  Resolved against the ``contracts`` queryset filtered
            by ``tenant=owner_tenant_id, status="ACTIVE"``.
        caller_tenant_id
            Tenant id of the requesting user — used by the audit row
            and the cross-tenant flag in the per-query metric.
        owner_tenant_id
            Tenant id of the listing owner — the ``LineageEdge`` rows
            we walk are scoped to this tenant.  Cross-tenant edges are
            stored with ``source_contract=NULL`` or ``target_contract=NULL``
            (per the model's docstring at [models.py:821](hub/apps/contracts/models.py)).
        detail
            ``"summary"`` (default — pre-purchase, IP-stripped) or
            ``"full"`` (post-purchase, with transformation IP).  The
            distinction is encoded in the **serializer choice** at the
            view layer; this service emits the same payload shape and
            the view picks the matching serializer.
        max_depth
            Clamped to 1..15 by the view layer; the service trusts
            its caller for this bound.
        as_of
            Optional SCD Type 2 timestamp for time-travel reads.

        Returns
        -------
        ``{"nodes": [...], "links": [...], "truncated": bool, "detail": str}``

        Notes
        -----
        * **Read-replica routing** — uses ``LineageEdge.objects.using("replica")``
          when a ``replica`` connection is configured (REQ-LIN-F1 / F1.8).
          Falls back transparently to the primary when only one connection
          exists, so the unit tests don't need a multi-DB setup.
        * **Cross-tenant edges** — when the BFS encounters an edge whose
          source/target contract belongs to a different tenant (e.g. the
          marketplace consumer who later derives a downstream product),
          the edge is included but the foreign endpoint is rendered as
          a generic "external" node with no tenant_id leakage.
        """
        self._record_query_metric(
            detail=detail,
            cross_tenant=(caller_tenant_id != owner_tenant_id),
            as_of_set=as_of is not None,
        )

        root_contract = (
            Contract.objects.filter(
                asset_id=asset_id,
                tenant_id=owner_tenant_id,
                status="ACTIVE",
            )
            .order_by("-version")
            .first()
        )
        if root_contract is None:
            raise NotFoundError(
                f"No ACTIVE contract found for asset {asset_id} in "
                f"tenant {owner_tenant_id}"
            )

        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        links: List[Dict[str, Any]] = []
        truncated = False

        # BFS — visit each contract once.  A node represents either a
        # contract (in this tenant) or an external/cross-tenant
        # endpoint.  Links carry the canonical edge metadata; the view's
        # serializer choice determines which fields ship over the wire.
        from collections import deque

        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        queue.append((str(root_contract.id), 0))

        # Seed the root node.
        nodes_by_id[str(root_contract.id)] = self._render_contract_node(
            root_contract,
        )

        while queue:
            contract_id, depth = queue.popleft()
            if contract_id in visited:
                continue
            visited.add(contract_id)

            if depth >= max_depth:
                # Walk no deeper, but the existing node + already-emitted
                # edges stay.  Truncation is not a flag at this level.
                continue

            for direction in ("incoming", "outgoing"):
                edges = self._edges_at(
                    contract_id, as_of=as_of, direction=direction,
                )
                # F1.5 audit hardening (post-W6): scope edges to the
                # owner tenant explicitly.  ``_edges_at`` is shared with
                # other lineage callers that don't enforce tenant
                # scope; we add a defensive filter here so an edge
                # rogue-written from another tenant (write-path bug,
                # post-restore from cross-tenant backup) can't bleed
                # into a cross-tenant read.  Belt-and-suspenders with
                # the tenant FK invariant on LineageEdge.
                edges = [
                    e for e in edges
                    if (
                        # Edges from `_edges_at` are dicts (not model
                        # instances) — re-confirm tenant via a small
                        # tenant-id lookup against the source/target
                        # contract.  Cross-tenant endpoints are
                        # legitimately allowed to have null source/target
                        # contract; those carry the owner's tenant_id
                        # implicitly and are kept.
                        _edge_belongs_to_tenant(e, owner_tenant_id)
                    )
                ]
                for edge in edges:
                    if len(links) >= self.F1_EDGE_CAP:
                        truncated = True
                        break

                    src_id = edge["source_contract"]
                    tgt_id = edge["target_contract"]
                    # Direction → which endpoint is the OTHER:
                    # - incoming: target_contract == contract_id, so
                    #   source_contract is the OTHER endpoint.
                    # - outgoing: source_contract == contract_id, so
                    #   target_contract is the OTHER endpoint.
                    # Pre-fix, this was inverted, which produced a
                    # one-step BFS that never expanded past depth 1
                    # for outgoing edges and miscounted incoming
                    # edges as "self-referential".
                    other_id = src_id if direction == "incoming" else tgt_id

                    # Materialise the foreign endpoint node.  Cross-tenant
                    # / external endpoints carry no tenant_id and a
                    # generic "external" label.
                    if other_id and other_id not in nodes_by_id:
                        if len(nodes_by_id) >= self.F1_NODE_CAP:
                            truncated = True
                            break
                        other_contract = (
                            Contract.objects
                            .filter(id=other_id)
                            .only(
                                "id", "tenant_id", "status",
                                "hub_contract_json",
                            )
                            .first()
                        )
                        if (
                            other_contract is not None
                            and str(other_contract.tenant_id) == owner_tenant_id
                        ):
                            nodes_by_id[other_id] = self._render_contract_node(
                                other_contract,
                            )
                        else:
                            # External / cross-tenant — anonymise.
                            nodes_by_id[other_id] = {
                                "id": other_id,
                                "type": "external",
                                "label": "External contract",
                            }

                    # The serializer expects ``source`` / ``target`` graph-node
                    # IDs; the raw edge dict carries ``source_contract`` /
                    # ``target_contract``.  Add the graph-level keys so the
                    # serializers (summary *and* full) can read them.
                    edge["source"] = src_id or ""
                    edge["target"] = tgt_id or ""
                    links.append(edge)

                    if (
                        other_id
                        and other_id not in visited
                        and len(visited) < self.F1_NODE_CAP
                    ):
                        queue.append((other_id, depth + 1))

                if truncated:
                    break
            if truncated:
                break

        return {
            "nodes": list(nodes_by_id.values()),
            "links": links,
            "truncated": truncated,
            "detail": detail,
        }

    @staticmethod
    def _render_contract_node(contract: "Contract") -> Dict[str, Any]:
        """Build a graph node from a Contract instance.

        The label is derived from ``hub_contract_json.info.name`` which
        is the canonical user-facing contract name — never from
        transformation_ref / job_ref.  This is the I4 mitigation in
        the F1 STRIDE threat model: summary-tier node labels MUST NOT
        carry transformation hints.
        """
        payload = getattr(contract, "hub_contract_json", None) or {}
        info = payload.get("info") if isinstance(payload, dict) else None
        name = (info.get("name") if isinstance(info, dict) else None) or ""
        return {
            "id": str(contract.id),
            "type": "contract",
            "label": str(name) or f"contract:{contract.id}",
        }
