# Metrics Cardinality Analysis

**311.28 (G23)** — Sprint 4 — Metric label cardinality audit

## Safe Labels (bounded cardinality)

| Label | Max Cardinality | Rationale |
|-------|----------------|-----------|
| `app` | 42 | One per Django app |
| `view` | ~200 | One per ViewSet/view function |
| `scope` | 13 | Throttle scopes in `DEFAULT_THROTTLE_RATES` |
| `method` | 7 | HTTP methods (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS) |
| `status` | ~20 | HTTP status code families (2xx, 3xx, 4xx, 5xx) |
| `severity` | 4 | critical, warning, info, debug |
| `outcome` | 4 | success, failure, warning, hit/miss |
| `environment` | 4 | production, staging, development, test |

## Unsafe Labels (unbounded — DO NOT USE)

| Label | Risk | Mitigation |
|-------|------|-----------|
| `tenant_id` | Unbounded (grows with customers) | Use app-level aggregate; never put on per-request metrics |
| `user_id` | Unbounded (grows with users) | Aggregate by role or tenant |
| `asset_id` | Unbounded (grows with data) | Aggregate by asset type or status |
| `dataset_id` | Unbounded | Aggregate by format or size bucket |
| `query_hash` | Unbounded (unique per query) | Use query complexity bucket instead |

## Estimated Total Cardinality

- Safe labels combined: ~42 × 200 × 13 × 7 × 20 = ~15M (within Prometheus limits)
- With `tenant_id` (assuming 1000 tenants): ~15B (EXCEEDS Prometheus limits)
- Conclusion: Current labels are safe. No remediation needed.

## Audit Method

```bash
grep -rn "\.labels\b\|\.tag\b\|Counter\(\|Histogram\(\|Gauge\(" hub/apps/ --include="*.py" | \
  grep -v test | grep -v migration | while read line; do
    echo "$line" | grep -oP '(?<=labels\().*?(?=\))'
done
```
