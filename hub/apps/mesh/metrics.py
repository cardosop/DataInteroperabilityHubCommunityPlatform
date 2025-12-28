"""
Data Mesh Metrics

Prometheus metrics for Data Mesh operations monitoring and observability.
Tracks domain lifecycle, policy applications, compliance checks, topology updates, and health status.
"""
from typing import Optional

from hub.apps.observability.otel_metrics import (
    _CounterWrapper,
    _HistogramWrapper,
    _UpDownCounterWrapper,
)


# ============================================================================
# Domain Lifecycle Metrics
# ============================================================================

mesh_domain_created_total = _CounterWrapper(
    'mesh_domain_created_total',
    'Total number of data mesh domains created',
    unit='1',
    expected_labels=('tenant_id', 'status')
)

mesh_domain_updated_total = _CounterWrapper(
    'mesh_domain_updated_total',
    'Total number of data mesh domains updated',
    unit='1',
    expected_labels=('tenant_id',)
)

mesh_domain_deleted_total = _CounterWrapper(
    'mesh_domain_deleted_total',
    'Total number of data mesh domains deleted',
    unit='1',
    expected_labels=('tenant_id', 'reason')
)

mesh_domain_creation_duration_seconds = _HistogramWrapper(
    'mesh_domain_creation_duration_seconds',
    'Data mesh domain creation duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    expected_labels=('tenant_id', 'status')
)

mesh_domain_update_duration_seconds = _HistogramWrapper(
    'mesh_domain_update_duration_seconds',
    'Data mesh domain update duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    expected_labels=('tenant_id',)
)


# ============================================================================
# Policy Application Metrics
# ============================================================================

mesh_policy_applied_total = _CounterWrapper(
    'mesh_policy_applied_total',
    'Total number of policies applied to data mesh domains',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'policy_id', 'status')
)

mesh_policy_revoked_total = _CounterWrapper(
    'mesh_policy_revoked_total',
    'Total number of policies revoked from data mesh domains',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'policy_id', 'reason')
)

mesh_policy_application_duration_seconds = _HistogramWrapper(
    'mesh_policy_application_duration_seconds',
    'Policy application duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    expected_labels=('tenant_id', 'status')
)


# ============================================================================
# Compliance Metrics
# ============================================================================

mesh_compliance_check_duration_seconds = _HistogramWrapper(
    'mesh_compliance_check_duration_seconds',
    'Data mesh compliance check duration in seconds',
    unit='s',
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    expected_labels=('tenant_id', 'domain_id', 'compliance_status')
)

mesh_compliance_violations_total = _CounterWrapper(
    'mesh_compliance_violations_total',
    'Total number of compliance violations detected',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'violation_type', 'severity')
)

mesh_compliance_checks_total = _CounterWrapper(
    'mesh_compliance_checks_total',
    'Total number of compliance checks performed',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'compliance_status')
)

mesh_compliance_report_generated_total = _CounterWrapper(
    'mesh_compliance_report_generated_total',
    'Total number of compliance reports generated',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'compliance_status')
)


# ============================================================================
# Topology Metrics
# ============================================================================

mesh_topology_update_duration_seconds = _HistogramWrapper(
    'mesh_topology_update_duration_seconds',
    'Data mesh topology update duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    expected_labels=('tenant_id',)
)

mesh_topology_updates_total = _CounterWrapper(
    'mesh_topology_updates_total',
    'Total number of topology updates',
    unit='1',
    expected_labels=('tenant_id',)
)

mesh_topology_update_failures_total = _CounterWrapper(
    'mesh_topology_update_failures_total',
    'Total number of topology update failures',
    unit='1',
    expected_labels=('tenant_id', 'error_type')
)

mesh_domain_count = _UpDownCounterWrapper(
    'mesh_domain_count',
    'Current number of data mesh domains',
    unit='1',
    expected_labels=('tenant_id', 'status')
)

mesh_relationship_count = _UpDownCounterWrapper(
    'mesh_relationship_count',
    'Current number of relationships between domains',
    unit='1',
    expected_labels=('tenant_id',)
)


# ============================================================================
# Health Status Metrics
# ============================================================================

mesh_domain_health_status = _UpDownCounterWrapper(
    'mesh_domain_health_status',
    'Current health status of data mesh domains (1=healthy, 0.5=degraded, 0=unhealthy)',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'health_status')
)

mesh_domain_health_status_changes_total = _CounterWrapper(
    'mesh_domain_health_status_changes_total',
    'Total number of domain health status changes',
    unit='1',
    expected_labels=('tenant_id', 'domain_id', 'previous_status', 'new_status')
)

mesh_domain_health_check_duration_seconds = _HistogramWrapper(
    'mesh_domain_health_check_duration_seconds',
    'Domain health check duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    expected_labels=('tenant_id', 'domain_id', 'health_status')
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_tenant_id(tenant_id: Optional[str]) -> str:
    """
    Get tenant ID for metrics labels (use 'system' if None).

    Args:
        tenant_id: Tenant ID or None

    Returns:
        Tenant ID string or 'system'
    """
    return str(tenant_id) if tenant_id else 'system'


def get_domain_id(domain_id: Optional[str]) -> str:
    """
    Get domain ID for metrics labels (use 'unknown' if None).

    Args:
        domain_id: Domain ID or None

    Returns:
        Domain ID string or 'unknown'
    """
    return str(domain_id) if domain_id else 'unknown'

