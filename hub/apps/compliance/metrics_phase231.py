"""
Phase 231 — Prometheus counters for compliance intake gate and webhook paths.

Counters are best-effort: failures must never block business logic.
"""

from __future__ import annotations
# Stable label values for ``compliance_intake_gate_events_total{event=...}``.
EVENT_SCAN_ENQUEUED = "SCAN_ENQUEUED"
EVENT_ACTIVATION_GATE_BLOCK = "ACTIVATION_GATE_BLOCK"
EVENT_PUBLISH_GATE_NO_ASSET = "PUBLISH_GATE_NO_ASSET"
EVENT_PUBLISH_GATE_NO_RUN = "PUBLISH_GATE_NO_RUN"
EVENT_PUBLISH_GATE_THRESHOLD = "PUBLISH_GATE_THRESHOLD"
EVENT_GATE_OVERRIDDEN = "GATE_OVERRIDDEN"
EVENT_WEBHOOK_FIRED = "WEBHOOK_FIRED"
EVENT_SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


def record_compliance_intake_gate_event(event: str, tenant_id: str | None) -> None:
    """Increment OTel/Prometheus ``compliance_intake_gate_events_total``."""
    try:
        from hub.apps.observability import otel_metrics

        m = otel_metrics.compliance_intake_gate_events_total
        tid = str(tenant_id) if tenant_id is not None else "unknown"
        m.labels(event=event, tenant_id=tid).inc()
    except Exception:
        pass
