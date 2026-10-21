# Search MVP Rollout Runbook (Phase 273)

Status: 2026-05-12

## Pre-Deploy Smoke Checklist

Run against staging after deploy:

```bash
# 1. Search availability (MVP gate removed)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.stagingmeshant-internal.example.com/api/search/?q=test&types=assets" \
  | jq '. | length'

# 2. Rate limit verification (60/min default)
for i in $(seq 1 61); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $TOKEN" \
    "https://api.stagingmeshant-internal.example.com/api/search/?q=test"
done
# 61st should return 429 with Retry-After header

# 3. Audit event verification
# Check AuditEvent table for SEARCH_PERFORMED rows with matching tenant_id

# 4. Metrics verification
# Grafana search-overview dashboard (UID: meshant-search-overview-273)
# should show metrics within 5 minutes of deploy

# 5. SPARQL endpoint
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "https://api.stagingmeshant-internal.example.com/api/v1/semantic/sparql/" \
  -d '{"query": "SELECT * WHERE { ?s ?p ?o } LIMIT 1", "format": "json", "timeout": 5}'

# 6. Semantic dereference
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.stagingmeshant-internal.example.com/api/v1/semantic/dereference/asset/<uuid>/"
```

## On-Call Alerts

- `sum(rate(search_no_result_total[5m])) / sum(rate(search_request_duration_seconds_count[5m])) > 0.5 for 10m`
  → "Search returning >=50% empty for 10 minutes — index probably broken"

- `histogram_quantile(0.95, search_request_duration_seconds) > 2 for 5m`
  → "Search p95 latency above 2s"

## Rollback

If search needs to be re-gated (emergency):
1. Add `/search` back to `NON_MVP_PATHS` in `mvpNav.ts`
2. Add `<MvpGatedRoute>` wrapper in `routes.tsx`
3. Add `"search/"` to `MVP_GATED_RELATIVE_PREFIXES` in `mvp_mode.py`
4. Redeploy frontend and backend
