# Phase 250.0.23 — OTel sampling adjustment for asset creation

**Status**: Authoritative
**Phase**: 250.0.23
**Owners**: SRE / Observability

## Why this exists

Phase 240's OTel auto-instrumentation samples at the global rate (`OTEL_TRACES_SAMPLER_ARG`, default `0.1` in production). For Phase 250's fail-closed paths, this is too coarse:

- **Fail-closed paths** are rare but high-value (every rejection is a customer-facing event that may cascade into a support ticket). Tail-sampling at 10% loses 90% of the diagnostic signal.
- **Happy-path workflow steps** are frequent and look-alike. Sampling at 10% is sufficient.

Phase 250.0.23 introduces per-path sampling: 100% on fail-closed paths, 10% on happy-path workflow steps.

## Implementation

The Hub's existing OTel config at [hub/apps/observability/otel_config.py](../../hub/apps/observability/otel_config.py) supports custom samplers. Phase 250.0.23 ships a `ParentBasedWithPathOverrideSampler` that wraps the default sampler with per-span-name overrides:

```python
# hub/apps/observability/asset_creation_sampler.py (NEW)
from opentelemetry.sdk.trace.sampling import (
    Decision, ParentBased, Sampler, SamplingResult, TraceIdRatioBased,
)


_FAIL_CLOSED_SPAN_NAMES = frozenset({
    "asset.workflow.compliance_check_inmemory",
    "asset.workflow.dq_check_inmemory",
    "asset.workflow.fail_closed_rejected",
    "asset.workflow.rolled_back",
    "asset.workflow.compensate_attach_dataset",
    "asset.workflow.compensate_validate_contract",
    "asset.workflow.compensate_odps_link",
})


class FailClosedAwareSampler(Sampler):
    """Phase 250.0.23 — sample 100% on fail-closed paths, 10% otherwise.

    Wraps a default ratio-based sampler. The override matches by exact
    span name (cheap; predictable). For matched spans, force-sample;
    for unmatched, defer to the wrapped sampler.
    """

    def __init__(self, default_ratio: float = 0.1):
        self._default = TraceIdRatioBased(default_ratio)

    def should_sample(
        self,
        parent_context,
        trace_id,
        name,
        kind=None,
        attributes=None,
        links=None,
        trace_state=None,
    ) -> SamplingResult:
        if name in _FAIL_CLOSED_SPAN_NAMES:
            return SamplingResult(
                decision=Decision.RECORD_AND_SAMPLE,
                attributes=attributes or {},
                trace_state=trace_state,
            )
        return self._default.should_sample(
            parent_context, trace_id, name,
            kind=kind, attributes=attributes,
            links=links, trace_state=trace_state,
        )

    def get_description(self) -> str:
        return f"FailClosedAwareSampler(default={self._default.get_description()})"
```

Wire into the existing config:

```python
# hub/apps/observability/otel_config.py (extend existing _build_sampler)
def _build_sampler() -> Tuple[Sampler, float]:
    # ... existing branches ...
    
    # Phase 250.0.23 — fail-closed paths get 100% sampling.
    if env == "production" and feature_flags.is_fail_closed_aware_sampling_enabled():
        from hub.apps.observability.asset_creation_sampler import FailClosedAwareSampler
        return FailClosedAwareSampler(default_ratio=0.1), 0.1
    
    # ... existing fallback ...
```

## Activation

Activate via env var (default OFF, opt-in via Helm):
```yaml
# helm/values.yaml
api:
  env:
    OTEL_FAIL_CLOSED_AWARE_SAMPLING_ENABLED: "true"
```

This avoids surprising trace-volume spikes on first deploy. After 7-day soak with metrics confirming the volume increase is bounded (~+15% for production traffic), default-on can be considered.

## Cost impact

Estimated trace-volume increase:
- Before Phase 250 (10% sampling): ~10 traces/sec at 100 RPS × 10% = ~1 trace/sec/path.
- After Phase 250.0.23: ~1.15 traces/sec/path (15% increase from fail-closed paths being ~5% of traffic at 100% sampling).
- Tempo storage cost: ~$0.10/GB/month × ~5 GB increase/month = ~$0.50/month — negligible.

## Verification

Post-deploy:
1. Tempo query: `{service.name="hub-api", span.name="asset.workflow.fail_closed_rejected"}` returns 100% of fail-closed events.
2. Tempo query: `{service.name="hub-api", span.name="asset.workflow.contract_create"}` returns ~10% of executions (default rate).
3. Grafana panel "trace volume per span name" shows the expected uneven distribution.

## Roll-back

If trace volume blows up unexpectedly:
```yaml
api:
  env:
    OTEL_FAIL_CLOSED_AWARE_SAMPLING_ENABLED: "false"
```
Restart pods; sampling reverts to default 10% across the board.

## Related

- ADR-AST-001 (defines fail-closed semantics).
- Phase 240.2.C (existing OTel TraceContext propagation).
- [docs/runbooks/data-quality.md](data-quality.md) — analogous DQ tracing setup.
