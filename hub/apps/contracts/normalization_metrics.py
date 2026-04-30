"""
Normalization Metrics

Records metrics for normalization coverage, contract size, missing objects, and broken lineage links.
"""
import json
from typing import Dict, Any, Optional, List
from django.conf import settings

try:
    from hub.apps.observability.otel_metrics import (
        normalization_coverage_by_object,
        contract_json_size_bytes,
        contract_missing_objects_total,
        contract_broken_lineage_links_total,
        odcs_v310_relationships_count,
        odcs_v310_fallback_total,
        # Phase 227 Wave 1 (227.L7.1) — structureless / floor metrics.
        contract_validation_failed_total,
        contract_structureless_total,
        contract_normalization_models_count,
        contract_normalization_fields_total_count,
        contracts_renormalize_batch_duration_seconds,
        contract_structureless_backlog,
    )
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False


def record_normalization_coverage(
    hub_contract: Dict[str, Any],
    tenant_id: Optional[str] = None
) -> None:
    """
    Record normalization coverage metrics by object type.
    
    Args:
        hub_contract: Normalized HubContract JSON
        tenant_id: Tenant ID (optional)
    """
    if not METRICS_AVAILABLE or not hub_contract:
        return
    
    # Object types to track
    object_types = [
        'contact', 'servers', 'terms', 'definitions', 'servicelevels',
        'models', 'lineage', 'roles', 'team', 'pricing', 'support'
    ]
    
    # Calculate coverage for each object type
    for obj_type in object_types:
        if obj_type in hub_contract:
            # Object is present
            coverage = 1.0
        else:
            # Object is missing
            coverage = 0.0
        
        # Record metric
        labels = {'object_type': obj_type}
        if tenant_id:
            labels['tenant_id'] = str(tenant_id)
        
        normalization_coverage_by_object.labels(**labels).observe(coverage)


def record_contract_json_size(
    hub_contract: Dict[str, Any],
    tenant_id: Optional[str] = None
) -> None:
    """
    Record contract JSON size metric.
    
    Args:
        hub_contract: Normalized HubContract JSON
        tenant_id: Tenant ID (optional)
    """
    if not METRICS_AVAILABLE or not hub_contract:
        return
    
    # Calculate JSON size in bytes
    json_str = json.dumps(hub_contract)
    size_bytes = len(json_str.encode('utf-8'))
    
    # Record metric
    labels = {}
    if tenant_id:
        labels['tenant_id'] = str(tenant_id)
    
    contract_json_size_bytes.labels(**labels).observe(size_bytes)


def record_missing_objects(
    hub_contract: Dict[str, Any],
    tenant_id: Optional[str] = None
) -> None:
    """
    Record missing objects metric.
    
    Args:
        hub_contract: Normalized HubContract JSON
        tenant_id: Tenant ID (optional)
    """
    if not METRICS_AVAILABLE or not hub_contract:
        return
    
    # Expected objects
    expected_objects = [
        'contact', 'servers', 'terms', 'definitions', 'servicelevels',
        'models', 'lineage', 'roles', 'team', 'pricing', 'support'
    ]
    
    # Check for missing objects
    for obj_type in expected_objects:
        if obj_type not in hub_contract:
            labels = {'object_type': obj_type}
            if tenant_id:
                labels['tenant_id'] = str(tenant_id)
            
            contract_missing_objects_total.labels(**labels).inc()


def record_broken_lineage_links(
    hub_contract: Dict[str, Any],
    broken_links: Optional[List[Dict[str, Any]]],
    tenant_id: Optional[str] = None
) -> None:
    """
    Record broken lineage links metric.
    
    Args:
        hub_contract: Normalized HubContract JSON
        broken_links: List of broken link dictionaries with 'type' field (optional)
        tenant_id: Tenant ID (optional)
    """
    if not METRICS_AVAILABLE or not broken_links:
        return
    
    # Count broken links by type
    link_types = {}
    for link in broken_links:
        link_type = link.get('type', 'unknown')
        link_types[link_type] = link_types.get(link_type, 0) + 1
    
    # Record metrics
    for link_type, count in link_types.items():
        labels = {'link_type': link_type}
        if tenant_id:
            labels['tenant_id'] = str(tenant_id)
        
        for _ in range(count):
            contract_broken_lineage_links_total.labels(**labels).inc()


def record_v310_relationships_count(
    hub_contract: Dict[str, Any],
    tenant_id: Optional[str] = None,
) -> None:
    """Record count of relationships mapped in a v3.1.0 normalisation."""
    if not METRICS_AVAILABLE or not hub_contract:
        return
    count = 0
    for model in hub_contract.get("models", []):
        if isinstance(model, dict):
            rels = model.get("relationships")
            if isinstance(rels, list):
                count += len(rels)
    schema = hub_contract.get("schema")
    if isinstance(schema, dict):
        rels = schema.get("relationships")
        if isinstance(rels, list):
            count += len(rels)
    labels: Dict[str, str] = {}
    if tenant_id:
        labels["tenant_id"] = str(tenant_id)
    odcs_v310_relationships_count.labels(**labels).inc(count)


def record_v310_fallback(
    fallback_normalizer: str,
    tenant_id: Optional[str] = None,
) -> None:
    """Record when a v3.1.0 contract falls back to a non-v3.1.0 normalizer."""
    if not METRICS_AVAILABLE:
        return
    labels: Dict[str, str] = {
        "fallback_normalizer": fallback_normalizer,
    }
    if tenant_id:
        labels["tenant_id"] = str(tenant_id)
    odcs_v310_fallback_total.labels(**labels).inc()


def record_all_normalization_metrics(
    hub_contract: Dict[str, Any],
    broken_links: Optional[List[Dict[str, Any]]] = None,
    tenant_id: Optional[str] = None,
    spec_type: Optional[str] = None,
) -> None:
    """
    Record all normalization metrics at once.

    Args:
        hub_contract: Normalized HubContract JSON
        broken_links: List of broken lineage links (optional)
        tenant_id: Tenant ID (optional)
        spec_type: Originating spec type (e.g. ``ODCS``, ``ODPS``).
            Used by the Phase 227 Wave 1 distribution histograms; if
            omitted, those histograms are skipped (we don't want
            unlabeled samples polluting the per-spec dashboard).
    """
    record_normalization_coverage(hub_contract, tenant_id)
    record_contract_json_size(hub_contract, tenant_id)
    record_missing_objects(hub_contract, tenant_id)

    if broken_links:
        record_broken_lineage_links(hub_contract, broken_links, tenant_id)

    # Phase 227 Wave 1 (227.L7.1) — model + field count histograms.
    if spec_type:
        record_normalization_models_count(hub_contract, spec_type=spec_type)
        record_normalization_fields_total_count(
            hub_contract, spec_type=spec_type
        )


# ---------------------------------------------------------------------------
# Phase 227 Wave 1 (227.L7.1) — structureless / floor metrics emitters
# ---------------------------------------------------------------------------


def record_validation_failed(
    *,
    code: str,
    subcode: Optional[str],
    spec_type: Optional[str],
) -> None:
    """Increment ``contract_validation_failed_total{code,subcode,spec_type}``.

    Called from :func:`hub.apps.contracts.structural_floor.enforce_structural_floor`
    on every Layer-3 raise so the Grafana dashboard's STRUCTURELESS
    rejection-rate panel can break down by code, subcode, and spec_type.

    Empty-string fallback for missing label values keeps the cardinality
    bounded and avoids OTel rejecting None as a label.
    """
    if not METRICS_AVAILABLE:
        return
    contract_validation_failed_total.labels(
        code=code or "UNKNOWN",
        subcode=subcode or "UNSPECIFIED",
        spec_type=str(spec_type or "UNKNOWN"),
    ).inc()


def record_structureless(
    *,
    spec_type: Optional[str],
    source: str,
) -> None:
    """Increment ``contract_structureless_total{spec_type, source}``.

    ``source`` ∈ {``creation``, ``update``, ``migration``,
    ``deprecation_warning``}. Other values are accepted but operators
    should grep their dashboards for them — they indicate a new write
    path that isn't covered by the existing trifecta.
    """
    if not METRICS_AVAILABLE:
        return
    contract_structureless_total.labels(
        spec_type=str(spec_type or "UNKNOWN"),
        source=source,
    ).inc()


def record_normalization_models_count(
    hub_contract: Dict[str, Any],
    *,
    spec_type: str,
) -> None:
    """Observe ``len(hub_contract.models)`` on the per-spec histogram.

    Counts ALL models regardless of whether they have fields — the
    histogram is for distribution analysis, not for filtering. Use
    ``contract_validation_failed_total`` for the rejection counter.
    """
    if not METRICS_AVAILABLE or not hub_contract:
        return
    models = hub_contract.get("models") or []
    if not isinstance(models, list):
        models = []
    contract_normalization_models_count.labels(
        spec_type=str(spec_type or "UNKNOWN"),
    ).observe(len(models))


def record_normalization_fields_total_count(
    hub_contract: Dict[str, Any],
    *,
    spec_type: str,
) -> None:
    """Observe the total field count summed across ``models[*].fields[]``
    AND ``schema.fields[]`` on the per-spec histogram."""
    if not METRICS_AVAILABLE or not hub_contract:
        return
    total = 0
    models = hub_contract.get("models") or []
    if isinstance(models, list):
        for model in models:
            if not isinstance(model, dict):
                continue
            fields = model.get("fields") or []
            if isinstance(fields, list):
                total += len(fields)
    schema = hub_contract.get("schema") or {}
    if isinstance(schema, dict):
        schema_fields = schema.get("fields") or []
        if isinstance(schema_fields, list):
            total += len(schema_fields)
    contract_normalization_fields_total_count.labels(
        spec_type=str(spec_type or "UNKNOWN"),
    ).observe(total)


def record_renormalize_batch_duration(
    *,
    spec_type: Optional[str],
    outcome: str,
    duration_seconds: float,
) -> None:
    """Observe ``contracts_renormalize_batch_duration_seconds{spec_type, outcome}``.

    ``outcome`` ∈ {``healed``, ``residual``, ``mixed``, ``failed``}.
    ``mixed`` is appropriate when a batch healed some + left some as
    residue (the most common Wave-3 case for ODCS).
    """
    if not METRICS_AVAILABLE:
        return
    contracts_renormalize_batch_duration_seconds.labels(
        spec_type=str(spec_type or "UNKNOWN"),
        outcome=outcome,
    ).observe(max(0.0, float(duration_seconds)))


def set_structureless_backlog(
    *,
    count: int,
    tenant_id: Optional[str] = None,
) -> None:
    """Set the ``contract_structureless_backlog`` gauge (UpDownCounter).

    Called by the daily cron via the ``--output=count`` mode of
    ``renormalize_contracts``. The cron diff-and-set pattern is
    handled by the caller; this helper just emits an ``inc(delta)``
    to advance the gauge to the desired absolute value.
    """
    if not METRICS_AVAILABLE:
        return
    labels: Dict[str, str] = {}
    if tenant_id:
        labels["tenant_id"] = str(tenant_id)
    # UpDownCounter doesn't have ``set``; emit the absolute count via
    # a ``add`` API. The gauge starts at 0 in a fresh process; the
    # cron computes the delta from the previous reading and passes it
    # in. We expose an "absolute" surface (callers pass the absolute
    # value) and compute the delta internally via a process-local
    # cache. This matches the pattern used elsewhere in the codebase
    # (see ``_set_backfill_remaining`` in ``tasks.py``).
    global _last_backlog_value
    cache_key = tenant_id or "__all__"
    previous = _last_backlog_value.get(cache_key, 0)
    delta = count - previous
    if delta == 0:
        return
    contract_structureless_backlog.labels(**labels).inc(delta)
    _last_backlog_value[cache_key] = count


# Process-local cache for the backlog gauge so we can emit deltas
# rather than absolute values (the underlying OTel UpDownCounter API
# only supports `inc(delta)`, not `set(value)`).
_last_backlog_value: Dict[str, int] = {}

