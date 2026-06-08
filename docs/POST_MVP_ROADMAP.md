# Post-MVP Roadmap

**311.36 (G28/G29/G18)** — Sprint 5

## Search Quality (G28)

**Current**: Full-text search on indexed fields (name, description, tags). No relevance scoring, typo tolerance, or synonym support.

**Proposed**:
- Relevance scoring via BM25/TF-IDF weighted by field importance
- Typo tolerance using fuzzy matching (Levenshtein distance ≤2)
- Synonym support via domain-specific thesaurus

**Effort**: 4-6 weeks (1 engineer). Risk: low (additive to existing index).

## WebSocket Real-Time Push (G29)

**Current**: Frontend polls every 30-60s for job status, compliance/DQ runs, marketplace orders.

**Proposed**:
- WebSocket endpoint at `wss://meshant-internal.example.com/ws/`
- Push events: `job.completed`, `compliance.scan_done`, `dq.run_complete`, `marketplace.order_status_changed`
- Fallback to polling if WebSocket disconnected
- Replace polling in top-10 views: JobsList, ComplianceRunDetail, DQRunDetail, OrderDetail, AssetDetail

**Effort**: 6-8 weeks (1 engineer + 1 frontend). Risk: medium (new infrastructure).

## Bulk/Batch API Endpoints (G18)

**Current**: Single-resource CRUD only. Programmatic users must loop over individual POST/PUT calls.

**Proposed**:
- `POST /api/v1/bulk/assets` — accepts `{assets: [...]}`, returns `{created: [...], errors: [...]}`
- `POST /api/v1/bulk/contracts` — same pattern
- Rate limit: `tenant_write` scope (100/min)
- Max batch size: 100 per request
- Idempotency via `Idempotency-Key` header

**Effort**: 3-4 weeks (1 engineer). Risk: low (additive endpoints).

## Additional Items

| Feature | Current | Proposed | Effort |
|---------|---------|----------|--------|
| Audit export | API-only | CSV/JSON export with date range filter | 2 weeks |
| Plan comparison tool | None | CLI `datahub billing plans compare` (done in 285.13.13.1) | ✅ Done |
| SDK async support | Sync-only | Async Python SDK with `asyncio` | 3 weeks |
| Mobile admin app | None | React Native admin dashboard (read-only MVP) | 8 weeks |
| GraphQL subscriptions | Strawberry queries only | WebSocket subscriptions for real-time data | 4 weeks |
