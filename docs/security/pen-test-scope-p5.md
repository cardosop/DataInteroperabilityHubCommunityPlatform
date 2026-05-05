# P5 External Pen-Test Scope — Federated Asset Surface

> **Audience**: External pen-test vendor, P5 release manager, Platform security.
> **Phase**: 250.5.E.3 — closes audit gap S-1 / S2-5.
> **Last updated**: 2026-05-04.
> **Status**: Authored as a launch-prerequisite for federated-import GA. Companion to [threat-model-asset-creation-federated.md](threat-model-asset-creation-federated.md).
> **Vendor brief**: this document is the contractual scope for the external pen test scheduled before P5 prod-GA. The vendor SHALL deliver a written report against every test case below, with reproduction steps + proof-of-concept artefacts.

---

## P5 exit criterion

Per Phase 250.5.E.4, **the external pen test is a P5 prod-GA exit criterion**. P5 prod-GA cannot ship until:

1. The vendor has executed every test case in this scope (or formally documented out-of-scope deferrals with mitigations).
2. Every CRITICAL and HIGH finding is either remediated OR has a documented platform-security sign-off accepting the residual risk + a follow-up ticket.
3. The vendor's final report is filed at `docs/security/pen-test-reports/p5-<vendor>-<YYYY-MM-DD>.md` (path TBD by release manager).
4. Platform-security lead + DPO + P5 release manager have signed off on the report (mirrors the threat-model sign-off process — see § Sign-off in the companion threat model).

The merge-gating CI check at `hub/tests/test_security_docs_phase_250_5_e.py::TestPenTestScopeStructure::test_pen_test_scope_marks_p5_exit_criterion` enforces presence of this section so future contributors don't accidentally drop the exit-criterion language.

---

## Surface 1 — Federated-import endpoint

**Endpoint coverage**:

* `POST /api/v1/assets/data-first/`
* `POST /api/v1/assets/`
* `POST /api/v1/assets/{id}/external-resources/download/`
* `POST /api/v1/assets/{id}/external-resources/batch-download/`
* `GET  /api/v1/assets/{id}/external-resources/`
* `PATCH /api/v1/assets/{id}/`
* `POST /api/v1/marketplace/connections/` (per-tenant connector CRUD)
* `POST /api/v1/marketplace/connections/{id}/sync/` (manual sync trigger)

**Test cases the vendor SHALL execute**:

1. **Tenant-flag bypass** — call `create_federated_asset_with_contracts` via every public surface (REST, GraphQL, scheduled-ingestion worker, orchestration workflow direct invoke) on a tenant whose `federated_import_enabled=False`. Confirm rejection happens at every entry; report any path that succeeds.
2. **Cross-region consent bypass** — when consumer + source tenants are in different regions, attempt the import without `cross_region_consent=True`. Vary the surface (REST body, X-Cross-Region-Consent header proposal, manipulating `source_metadata.source_tenant_id` to point at a same-region tenant after passing the gate). Report any path that bypasses.
3. **Marketplace_type spoofing** — submit a federated import with a `marketplace_type` enum value that shouldn't dispatch to the implemented connector (e.g. `"OPEN_DATA"` on a Hub configured for `CKAN_INSTANCE` only). Confirm rejection at the connector-factory layer.
4. **Connection-config injection** — submit a `MarketplaceConnection.config` JSON containing fields the connector code might pass through to subprocess / shell / SQL (e.g. `"endpoint_url": "http://evil; rm -rf /"`). Confirm input is escaped / parameterised / validated at every consumption point.
5. **Auto-activation gate bypass** — exploit the `tenant.asset_auto_activate_on_gate_pass` flag to make a federated asset auto-activate without DQ / compliance pass (see [threat model](threat-model-asset-creation-federated.md) S2 / T1 + Phase 250.2.A.1).
6. **Idempotency-key replay** — submit two federated-import calls with the same `Idempotency-Key` but different bodies. Confirm the second is rejected per Phase 226 G10b idempotency contract.
7. **Body-size cap evasion** — submit a federated import with chunked transfer-encoding to evade `DATA_FIRST_MAX_BODY_BYTES`. Confirm rejection with HTTP 411.
8. **Workflow direct invocation** — bypass the REST surface by invoking the orchestration `create_federated_assets_task` directly (via internal API or message bus). Confirm the gate fires at the service-entry, not the HTTP-entry.

---

## Surface 2 — SSRF guard bypass attempts

**Code path**: `hub/apps/security/url_validators.py::SSRFGuard.validate(url, allowlist=None)` invoked from `ExternalResourceReference.clean()` AND `MarketplaceConnection.clean()`.

**Test cases the vendor SHALL execute**:

1. **Loopback variants** — `http://127.0.0.1`, `http://localhost`, `http://0.0.0.0`, `http://[::1]`, `http://127.1`, `http://2130706433` (decimal-encoded), `http://0x7f000001` (hex-encoded). Confirm every form is rejected.
2. **RFC1918 ranges** — `http://10.0.0.1`, `http://172.16.0.1`, `http://192.168.0.1`, `http://192.168.1.255`. Confirm rejection at every range boundary.
3. **Link-local + cloud IMDS** — `http://169.254.169.254` (AWS / Azure / GCP IMDS), `http://fd00::` (IPv6 ULA). Confirm IMDS access is blocked specifically (this is the highest-impact SSRF target).
4. **Non-http(s) schemes** — `file:///etc/passwd`, `gopher://attacker:1234/_GET / HTTP/1.1`, `ftp://attacker/`, `dict://attacker:11211/stats`, `ldap://attacker/`. Confirm scheme-allowlist is enforced.
5. **DNS rebinding** — register a domain whose A record resolves to a public IP at allowlist-CRUD time but rebinds to RFC1918 at fetch time. The current mitigation is the egress NetworkPolicy at the cluster-network layer — confirm the policy actually blocks the rebound packet.
6. **URL-parser confusion** — `http://attacker.com#@127.0.0.1`, `http://attacker.com?ignored=1@10.0.0.1/`, `http://[::ffff:127.0.0.1]/` (IPv4-mapped IPv6). These exploit URL-parser quirks where the validator and the HTTP client disagree on the destination.
7. **Allowlist injection** — submit a `MarketplaceConnection.config.endpoint_url` that's allowlisted for the tenant but redirects (HTTP 302) to an internal URL. Confirm the connector follows redirects only against the allowlist (not the resolved URL).
8. **Header-based SSRF** — exploit `Host` / `X-Forwarded-Host` / `X-Original-URL` headers in the connector's outbound request to make the destination differ from the URL the validator approved.
9. **Time-of-check vs time-of-use** — submit an allowlist URL that resolves to a public IP at validation but to an internal IP at fetch. Confirm DNS-pin (or absence) is documented.
10. **Cloud IMDS v2 token bypass** — confirm the connector's outbound HTTP client doesn't accidentally satisfy IMDSv2's token-fetch step (specifically, that `X-aws-ec2-metadata-token-ttl-seconds` header isn't passed through from caller-supplied headers).

---

## Surface 3 — IDOR across `ExternalResourceReference`

**Test cases the vendor SHALL execute** (these complement the existing automated `test_idor.py` suite — vendor SHALL replicate AND extend):

1. **Cross-tenant GET list** — replicate `test_cross_tenant_list_external_resources_returns_404`. Vary the auth surface (session cookie, JWT, API key) to confirm 404 is consistent.
2. **Cross-tenant POST download** — replicate `test_cross_tenant_download_external_resource_returns_404`. Confirm the response body NEVER carries the asset's name / key / external resource metadata, even on edge cases (asset name containing emoji, asset key matching a UUID format, etc.).
3. **AUDITOR mutate-deny on download endpoints** — replicate `AuditorMutationDenyTest`. Vary the role: TENANT_ADMIN should succeed, DATA_PROVIDER should succeed, AUDITOR should fail, DATA_CONSUMER should fail.
4. **AUDITOR list-access preserved** — confirm AUDITOR retains GET access to the list endpoint (sanity counter-test).
5. **External-resource ID enumeration** — submit a download request with a `resource_id` that doesn't exist for the asset. Confirm 404 with no enumeration of valid resource IDs in the body.
6. **UUID enumeration** — sequentially probe asset UUIDs (e.g. monotonically incrementing the LSB of a known UUID) to confirm the response distinguishes "exists for me" from "doesn't exist" only by 200 vs 404 — no information leak via response time, header presence, body shape.
7. **Cache-leak via Cache-Control headers** — confirm responses don't carry tenant-A asset metadata in `ETag` / `Last-Modified` / `X-Cache-Key` headers when accessed cross-tenant.
8. **Tenant-id-in-URL bypass** — attempt to access `/api/v1/tenants/<tenant_a_id>/assets/<asset_a_id>/external-resources/` (if such a nested route exists or is reachable via URL manipulation). Confirm the URL pattern doesn't bypass the standard tenant scoping.
9. **GraphQL IDOR** — query `{ assets(visibility: PUBLIC) { id name externalResources { id name url } } }` from tenant B's session and confirm only tenant B's federated assets are returned (NOT tenant A's PUBLIC ones).
10. **Bulk endpoint behavior** — submit a batch-download with one valid (own-tenant) resource_id and one cross-tenant resource_id. Confirm the entire batch is refused (not partial-success leaking the cross-tenant existence via the batch response shape).

---

## Surface 4 — Cross-tenant URL leakage

**Test cases the vendor SHALL execute**:

1. **Audit-log leakage** — query the audit endpoint as a tenant-B operator and confirm tenant-A's `FEDERATED_IMPORT_REJECTED` / `FEDERATED_IMPORT_CROSS_REGION_BLOCKED` / `FEDERATED_SOURCE_TENANT_DELETED` events are NOT visible. The tenant FK on `AuditEvent` should scope the query.
2. **Webhook payload leakage** — confirm webhook payloads delivered to tenant B's subscribers don't carry tenant-A's data when an event spans both (e.g. a federated cascade event references `source_tenant_id`).
3. **Search index leakage** — query the search endpoint as tenant B and confirm tenant-A's federated assets don't surface in results, even if they're set to `status=PUBLIC`. Federated assets MUST be tenant-scoped on the consumer side regardless of source-tenant visibility.
4. **Lineage graph leakage** — query the lineage / dependency endpoints (e.g. `/api/v1/assets/{id}/dependencies/`) as tenant B and confirm cross-tenant federated edges are hidden.
5. **Telemetry / metrics leakage** — confirm Prometheus metrics labels don't include cross-tenant identifiers in a way that lets a tenant-B operator infer tenant-A activity from public Grafana dashboards.
6. **Sunset / Deprecation header leakage** — confirm the Phase 250.3.B `Deprecation: true` + `Sunset: <date>` headers don't carry tenant-specific Sunset dates that would let an attacker correlate tenant identities.
7. **Schema-drift response leakage** — confirm the Phase 250.2.B `result_summary.schema_drift` payload (returned on data-first creation) doesn't carry the source contract's full schema field names if the contract belongs to a different tenant.
8. **OpenAPI / swagger doc leakage** — confirm the `/api/v1/openapi.json` endpoint doesn't enumerate every tenant's marketplace_type configurations or per-tenant connection IDs.
9. **Error-message leakage** — confirm 500 / 503 / 504 error responses don't include stack traces, query strings, or tenant identifiers anywhere in the body or headers.
10. **CORS preflight leakage** — confirm CORS preflight responses don't echo back arbitrary `Origin` headers (which would let an attacker confirm specific origins are allowlisted).

---

## Surface 5 — Ratelimit bypass

**Test cases the vendor SHALL execute**:

1. **Per-user throttle bypass** — exhaust the per-user 60/min throttle on `POST /api/v1/assets/data-first/`. Then attempt to bypass via: alternate auth (different JWT), alternate IP (X-Forwarded-For), alternate session, distinct user-agent. Confirm the throttle is keyed correctly.
2. **Per-tenant throttle bypass** — exhaust the per-tenant 600/min throttle. Attempt to bypass by: switching X-Tenant-Id header to a sibling tenant, using a service account / API key, hitting an alternate endpoint that maps to the same logical operation.
3. **Throttle window timing** — submit requests at exactly 60/min boundary. Confirm the throttle uses a sliding window (not fixed bucket — fixed buckets allow 2x burst at the boundary).
4. **Throttle-state injection** — submit an X-RateLimit-Reset / Retry-After header in the request to attempt to manipulate the throttle state.
5. **Cache-bypass via header variation** — vary `Accept-Encoding` / `Accept-Language` / `User-Agent` to confirm cache keys don't unintentionally fragment the throttle state.
6. **Long-running endpoint exhaustion** — submit data-first imports that take 30+ seconds each (legitimate long-running calls due to large file inference). Confirm worker-pool exhaustion has a bounded-concurrency limit per tenant (not just per-request rate-limit).
7. **Audit-write amplification** — exploit the per-rejection audit-write to amplify load (each rejected federated-import call writes 1-2 audit rows). Confirm per-tenant audit-write rate is bounded.
8. **Idempotency-key amplification** — submit a flood of distinct idempotency keys to fill the idempotency cache. Confirm cache size is bounded + LRU-evicted.
9. **Quota-check race** — submit N+1 download requests in parallel where the per-tenant daily quota is N. Confirm exactly N succeed (not N+1 due to TOCTOU).
10. **Rate-limit error info-leak** — submit requests until rate-limited. Confirm the 429 response body / headers don't leak the per-tenant throttle ceiling (which would help an attacker calibrate future load).

---

## Out-of-scope

The following are explicitly OUT of scope for this pen test (covered by separate work):

* **Compromised platform-admin account** — covered by Phase 234 audit-tamper-evidence (hash chain + S3 Object Lock).
* **Database-level tampering** — out of scope for application-layer pen test.
* **Source-side marketplace compromise** — Meshant assumes mutual untrust with external marketplaces; the threat model ends at "we sent the request the user asked us to send, to the URL the admin allowlisted, and we audited the request."
* **Phase 234 audit tamper-evidence** — separate work, not yet shipped.
* **TLS / certificate validation** — covered by infrastructure-layer pen test (separate engagement).
* **Frontend-only XSS / CSRF** — covered by separate FE-focused pen test (companion engagement).

---

## Vendor deliverables

The vendor SHALL deliver:

1. **Executive summary** — risk-rated findings table.
2. **Per-test-case report** — for every test case in this document, a result entry: PASS (mitigation works) / FAIL (vulnerability found) / N/A (out of scope after investigation). FAIL entries MUST include reproduction steps + PoC artefacts.
3. **Findings register** — per-finding severity (CRITICAL / HIGH / MEDIUM / LOW / INFO), CVSS score, recommended remediation.
4. **Methodology appendix** — tooling used (Burp, sqlmap, custom scripts), authentication context (test tenants, test users, role assignments).
5. **Retest scope** — explicit list of findings the vendor will retest after Meshant remediates.

Deliverables are filed at `docs/security/pen-test-reports/p5-<vendor>-<YYYY-MM-DD>.md` (path locked in by the P5 release manager at engagement-start time). Sign-off process per [threat-model-asset-creation-federated.md § Sign-off](threat-model-asset-creation-federated.md#sign-off).

---

## Remediation gates

* **CRITICAL** findings — release-blocker. Must be remediated AND retested PASS before P5 prod-GA.
* **HIGH** findings — release-blocker UNLESS platform-security lead + DPO sign off on residual-risk acceptance + follow-up ticket.
* **MEDIUM** findings — non-blocking; tracked as P5+ follow-up tickets with explicit owner + due date.
* **LOW / INFO** findings — captured in the findings register; no release impact.

The remediation-gate ladder is documented here so the vendor's CRITICAL classification has unambiguous release impact — there's no ambiguity about whether a CRITICAL finding "should" block release.
