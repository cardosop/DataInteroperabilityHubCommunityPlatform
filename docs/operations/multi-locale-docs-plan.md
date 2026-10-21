# Multi-Locale Documentation Plan (281.B.7.9)

**Date:** 2026-05-15  
**Target:** Critical docs available in es, fr, de, pt, ja. Machine-translation option for remainder.

## 1. Critical Docs — 5-Locale Coverage

| Document | en | es | fr | de | pt | ja | Priority |
|---|---|---|---|---|---|---|---|
| Production Deployment Runbook | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | P0 |
| Capacity Planning Guide | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | P0 |
| Data Retention Schedule | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | P0 |
| Maintenance Window Template | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | P0 |
| Incident Response (`INCIDENT_RESPONSE.md`) | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | P0 |
| API Reference (`API_REFERENCE.md`) | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | P1 |
| Product Guide (`PRODUCT_GUIDE.md`) | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | P1 |
| Developer Guide (`DEVELOPER_GUIDE.md`) | ✅ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | ⚠️ | P1 |

**Legend:** ✅ = complete (human-reviewed), ⚠️ = machine translation seed (needs review),  — = not translated

## 2. Frontend i18n Coverage (6 locales, 143 keys each)

| Locale | Unique % | Keys Translated | Review Status |
|---|---|---|---|
| en | — | 143 (reference) | Complete |
| es | 99.1% | 143/143 | Machine seed, human review pending |
| fr | 97.3% | 143/143 | Machine seed, human review pending |
| de | 96.2% | 143/143 | Machine seed, human review pending |
| pt | 98.0% | 143/143 | Machine seed, human review pending |
| ja | 100.0% | 143/143 | Machine seed, human review pending |

## 3. Machine Translation Pipeline

For docs not yet human-translated, a CI pipeline generates machine-translated versions:
- Source: English Markdown files under `docs/`
- Target: `docs/{lang}/` directories (es, fr, de, pt, ja)
- Generated files carry a `⚠️ MACHINE TRANSLATION — NOT HUMAN REVIEWED` banner
- Pipeline runs on every push to `main` that changes English docs

## 4. Human Review Queue

| Doc | Word Count | Est. Review Time | Reviewer |
|---|---|---|---|
| Production Deployment Runbook | ~1,200 words | 30 min/locale | Platform (per locale) |
| Data Retention Schedule | ~1,500 words | 35 min/locale | Legal + Platform |
| Incident Response | ~800 words | 20 min/locale | Security |
| Capacity Planning Guide | ~1,000 words | 25 min/locale | Platform |

## 5. Doc Language Selector

- Frontend: Language selector in header (flag icon + locale name)
- Backend: `Accept-Language` header respected via `LocaleMiddleware`
- Docs: `?lang=es` query parameter or language subdomain (`es.meshant-internal.example.com`)
