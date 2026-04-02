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
) -> None:
    """
    Record all normalization metrics at once.

    Args:
        hub_contract: Normalized HubContract JSON
        broken_links: List of broken lineage links (optional)
        tenant_id: Tenant ID (optional)
    """
    record_normalization_coverage(hub_contract, tenant_id)
    record_contract_json_size(hub_contract, tenant_id)
    record_missing_objects(hub_contract, tenant_id)

    if broken_links:
        record_broken_lineage_links(hub_contract, broken_links, tenant_id)

