# AI Search — Sunset Plan

**Decision:** Sunset (285.5.3.D, 2026-05-17)
**Effective:** Deprecation notice immediate. Removal Q4 2026.
**Migration target:** Discovery Agent (Phase 286.2)

## Why Sunset

AI Search was an early experimental feature that performed semantic embedding-based
search over the catalogue. It has been superseded by:

1. **Ontology-aware search** (`semantic_search_enabled`, GA as of Phase 284.D) —
   provides semantic query expansion through tenant ontology relations (synonyms,
   equivalent classes, parent/child concepts) without the operational cost of
   maintaining embedding indices.

2. **Discovery Agent** (planned Phase 286.2) — a next-generation discovery
   experience that will subsume the AI Search use case with a more maintainable
   architecture.

## Timeline

| Date | Action |
|------|--------|
| 2026-05-17 | Deprecation notice added to AISearchPage + Sunset header on ai/ endpoints |
| 2026-09-01 | ai/ endpoints return 410 Gone; AISearchPage redirects to /search |
| Q4 2026 | Remove ai/ app, AISearchPage.tsx, and route from codebase |

## Migration Path

Users currently relying on AI Search should migrate to:

1. **For semantic search:** Enable `semantic_search_enabled` on the tenant and
   use the ontology-aware search toggle on the catalogue Search page. This
   provides semantic query expansion without embedding indices.

2. **For AI-powered recommendations:** Use the marketplace recommendation
   service (`UC-MKT-ADV-005`), which provides listing recommendations based on
   catalogue metadata and trust signals.

3. **For advanced discovery:** Monitor Phase 286.2 for the Discovery Agent release.

## Affected Code

- `hub/apps/ai/views.py` — AISearchViewSet (add Sunset header)
- `frontend/src/features/ai/components/AISearchPage.tsx` — deprecation banner
- `frontend/src/app/routes/routes.tsx` — `/ai-search` route (remove Q4 2026)

## Related

- `docs/ga-readiness-audit-2026-05.md` — AI Search not in GA scope
- `hub/apps/search/views.py` — UnifiedSearchView (canonical search endpoint)
- `frontend/src/features/semantic/components/SemanticSearchFacets.tsx` — ontology-aware search facets
