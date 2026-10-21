# Round-2 Deep Review — Findings Supplement
**Companion to** [oss-maturity-assessment-2026-10-05.md](oss-maturity-assessment-2026-10-05.md) — read that first for the baseline.

**Date:** 2026-10-05 · **Branch:** `prepro01` (working tree where noted)
**Method:** Eight parallel read-only deep-dive investigations into the *inside* of the code (domain logic, concurrency, API surface, adversarial security, frontend data layer, public-mirror build — executed, not inferred — working-tree delta, SDK/CLI developer surface) plus four sub-reports (billing, pipeline state machines, marketplace orders, governance + plan limits). Every BLOCKER below was independently re-verified by the reporting agent; two of them were found independently by two different agents.

---

## 1. Executive summary

**Round 2 changes the picture materially.** Round 1 concluded: strong architecture/traceability, release blockers concentrated in license/secrets/SSO/CI/no-releases. Round 2 went inside the code and found that **the domain-correctness and defense-in-depth layers are substantially weaker than the architectural surface suggested**:

- **2 live cross-tenant compromise paths** (anonymous self-enrollment into any tenant; user-creation API that plants accounts with roles in any tenant) — both independently confirmed by two agents.
- **The tenant-isolation backstop does not exist on the HTTP path**: RLS policies exist in the schema, but the middleware that arms the per-request GUC exists only in prose. The whole cross-tenant boundary rests on per-view queryset discipline.
- **The pilot's central pipeline is the least-mature code in the product**: the dlt ingest/export spine has unguarded status transitions, duplicate-data re-runs, cursor-advance-on-failure data loss, no crash recovery, and a "cancel" that doesn't stop anything — while the pilot scope (PILOT_SCOPE.md) makes ingest→export the core story.
- **The money path has float math and a plan-change endpoint that never touches Stripe** — plus a downgrade guard that is structurally inert.
- **The developer surface doesn't exist publicly**: four registries, four 404s; the publish pipeline is miswired; docs describe a phantom SDK.
- **The public mirror builds clean and boots, but fails its own CI** (GATE-29: 192 violations blocking; test collection crash on paid imports).

The good news has a shape too: the strong patterns are *specific, named, and reusable* — `locked_contract_version()`, the entitlement idempotent-create, the files `get_object()` IDOR audit, timing-safe login, refresh-family rotation, the side-effect outbox, per-attempt savepoints. The repo knows how to do every one of these correctly; the failures are overwhelmingly **the correct pattern applied in one path and not its sibling**.

---

## 2. New BLOCKERs (round 2, all VERIFIED)

| # | Finding | Evidence |
|---|---|---|
| R2-B1 | **Anonymous self-enrollment into ANY tenant.** `POST /api/v1/auth/register` (AllowAny) accepts client `tenant_id`, checks only `is_active()`, creates an ACTIVE user + membership. Tenant UUIDs are exposed in marketplace listings. Cross-confirmed by two agents. (Precondition: registration enabled for the environment.) | `hub/apps/auth/views.py:1501-1531,1644-1697` |
| R2-B2 | **API-key scope escalation.** Any member mints keys with free-form scopes incl. `"*"` and `scheduled_ingestion:internal` (which passes `WorkerInternalAPIPermission` → worker-internal endpoints that bypass validation/quota); `APIKeyViewSet` doesn't override update/destroy → any member can PATCH anyone's key. `ENFORCE_JWT_SCOPES` default False. | `hub/apps/auth/serializers.py:150-158`, `services.py:36-120`, `views.py:2121+` |
| R2-B3 | **Event bus is self-defeating by construction.** Publisher dedup key == consumer dedup key → every published event is consumed as its own duplicate. Latent only because no process runs `start_listening()`. | `hub/apps/core/events/publisher.py:90-104` vs `bus.py:1032-1058`, `deduplication.py:136-186` |
| R2-B4 | **Business events published inside `transaction.atomic` before commit** — phantom events on rollback; with async persistence the phantom Event rows are durable and replayable. | `tenants/services.py:341-381`, `files/services.py:359-366`, `datasets/services.py:411-454` |
| R2-B5 | **Contract search re-index is dead code** (missing import, ImportError swallowed) → contract edits never reach search; stale results indefinitely. | `contracts/cache_invalidation.py:134-143` |
| R2-B6 | **Tenant hard delete is blocked by `User.tenant on_delete=RESTRICT`** for every real tenant; sweep has no user-cleanup step → the 90-day erasure contract silently fails forever. | `users/models.py:73-75`, `tenants/tenant_hard_delete_sweep.py:141` |

---

## 3. HIGHs (round 2, all VERIFIED)

### 3.1 Security & authorization
| # | Finding | Evidence |
|---|---|---|
| R2-S1 | **RLS GUC never set on the HTTP request path.** The middleware described in settings comments/docs does not exist (zero `set_config` call sites); the test suite was quietly re-documented to match the absence. Tenant isolation rests 100% on queryset filtering; either production RLS is inert or an out-of-repo mechanism the runbooks contradict sets it. | `hub/apps/auth/middleware.py` (499 lines, zero GUC), `hub/apps/auth/tests/test_rls_middleware_guc.py:22-30`, `settings.py:2127` comment |
| R2-S2 | **UserViewSet.create plants users in ANY tenant with client-supplied `tenant` + `role_ids`** (create has no admin gate; update/destroy do). | `users/views.py:76-135`, `users/serializers.py:83-91` |
| R2-S3 | **SQL injection into customer warehouse via DQ `warehouse-run`** — raw f-string SQL from client `check_definitions`, row-count exfiltration channel. | `dq/warehouse_sql_compiler.py:110-250`, `dq/views.py:571-627` |
| R2-S4 | **SQLi via compliance `warehouse-scan` flips the compliance gate** — injected SQL returning 0 rows ⇒ `allowed_to_store=True` ⇒ Phase 272.2 gate silently approves. | `compliance/warehouse_sql_compiler.py:128-196`, `compliance/services.py:1066-1072` |
| R2-S5 | **Presigned-PUT replay TOCTOU** — scan benign file → re-PUT malware through the same still-valid URL → served as CLEAN. | `files/views.py:454-461,754-797,870-888` |
| R2-S6 | **Warehouse SSRF guards double-broken**: validator import crashes (`ImportError` — guard never ran), key list omits `host`, no re-check at update; tenant Databricks tokens POSTed to arbitrary internal hosts with response exfiltration. | `warehouses/models.py:259-279`, `integrations/services/connection_service.py:169` |
| R2-S7 | **Worker-key ingestion endpoint**: committed default `HUB_WORKER_API_KEY` in compose + `X-Tenant-ID` any-tenant + no validation/quota/AV on the internal upload path. | `docker-compose.yml:1004`, `scheduled_ingestion/worker_services.py:293-312` |
| R2-S8 | **Staging Redis no-auth (4 instances, public ports) with rq pickle** → unauthenticated queue push → worker RCE on the staging host; Grafana `admin/admin` default; staging mounts the whole repo (live `.env` + `.git/` inside containers). | `docker-compose.staging.yml:141-252,1076-1085,384-385` |
| R2-S9 | **SPARQL security validator bypassed on the virtual-dataset execution path** (3 call sites execute tenant SPARQL without `validate_sparql_query`). | `virtualization/services/query_service.py:3250-3279` et al. |
| R2-S10 | **DQ webhook/Slack alerts POST to tenant-supplied URLs with zero SSRF validation + up to 32 forwarded headers** (Authorization/Host injection). | `dq/clients/webhook_client.py:57-65` |
| R2-S11 | **Exception `str()` leakage to clients** (SQL fragments, paths in the 500 envelope) + DRF lowercase `.code` shadows the canonical error-code map. | `api/exceptions.py:111-124,159,169` |
| R2-S12 | **GraphQL accepts token-version-revoked JWTs** (no DRF auth, `verify_version=False`) — terminated users' tokens live ~1h; MFA is dead code while SECURITY.md advertises it; impersonation escape via `switch_tenant` mints a non-audited permanent pair; magic-byte validation OFF by default; ClamAV fails open. | `graphql/` auth, `auth/mfa.py` (0 call sites), `tenants/impersonation_middleware.py:94-121`, `settings.py:1567` |
| R2-S13 | **Stripe webhook "idempotency" is check-then-act** (no atomic claim) — concurrent deliveries double-apply handlers; webhook delivery counters lose updates (no `F()`, no lock) → duplicate POSTs. | `billing/views.py:1021-1051`, `webhooks/service.py:571-572,803-806` |

### 3.2 Money & domain
| # | Finding | Evidence |
|---|---|---|
| R2-D1 | **Float is the money type with three rounding semantics on one charge path** — 2.23 charges 222¢, records 223¢; half-cent prices break refunds entirely (Stripe rejects 13¢ refund of a 12¢ charge); ledger drifts from gateway. | `marketplace/payment_service.py:148,657,687,85-90` |
| R2-D2 | **Plan change never touches the Stripe subscription** — metadata rename only; no price change, no proration (zero proration code), no cancel on downgrade. "Downgraded" tenants keep paying PRO forever. | `billing/services.py:556-563` |
| R2-D3 | **Downgrade guard structurally inert** — keys on `TenantPlan.order`, which the canonical seeder never populates (all 0). | `billing/views.py:333-335`, `seed_default_plans.py:184-192` |
| R2-D4 | **Order state machine PATCH-able around** — writable `status`/`listing`/`approved_by`, guard misses REQUESTED→FULFILLED; re-aiming `listing` grants entitlement for an un-ordered asset. | `marketplace/order_serializers.py:43-51`, `models.py:503-508` |
| R2-D5 | **Governance final-approval bypasses the consumer KYC gate** (marketplace path enforces it); reverse direction: marketplace approve force-APPROVEs multi-step chains, skipping GovernanceService/compliance/ABAC. | `marketplace/apps.py:72-78`, `order_views.py:488-507` |
| R2-D6 | **Multi-step approval chains are broken end-to-end**: snapshot format `{step, role, label}` vs validator reading `approvers` (always `[]`) → step 1+ permanently unapprovable; the registered `governance.approval.advance` chain is never executed in production (quorum/identity/stage rules = dead code); no segregation of duties. | `business_rules.py:1459`, `chain_registry.py:98` |
| R2-D7 | **Usage metering double-bills**: no idempotency key on `stripe.UsageRecord.create`; `UsageRecord` lacks a unique constraint (get_or_create race duplicates rows); workflow retries re-record usage. | `billing/services.py:789-857`, `models.py:273-281` |
| R2-D8 | **Cancelled order still gets an ACTIVE entitlement** (`or` fallback defeats the skip-dict); `/purchase` has no duplicate-active-order guard → double charge, second order stuck forever; re-buy → unhandled IntegrityError → stuck order. | `order_views.py:762-768,942-973`, `order_completion.py:22-51` |

### 3.3 Pipelines (the pilot's spine)
| # | Finding | Evidence |
|---|---|---|
| R2-P1 | **Zero transition guards on the shared run lifecycle** — any caller flips any status; racing workers last-write-wins; FAILED→COMPLETED re-fires side effects (duplicate cost rows, pause-counter reset). | `data_movement/worker_run_lifecycle.py:26-83`, `scheduled_ingestion/internal_views.py:297-311` |
| R2-P2 | **Re-runs duplicate data** — export append-without-dedup; ingestion re-reads everything (incremental helpers are dead code). | `data_movement/dlt_resources.py:67-68`, `ingestion_execution.py:139-165` |
| R2-P3 | **DATABRICKS_SOURCE cursor advances even on failed loads** — violating the module's own "advance ONLY after success" contract → permanent row loss. | `ingestion_execution.py:248-260`, `dlt_incremental.py:52-64` |
| R2-P4 | **No crash recovery**: no heartbeat/lease; stuck-run detectors can't see PENDING runs or NULL `started_at`; neither detector is scheduled anywhere; cancel is cosmetic (flags flip, dbt runs on). | `detect_stuck_runs.py:51-75`, `transformation/views.py:1533-1546` |
| R2-P5 | **Side effects fire on only SOME completion paths** — the dlt dispatch spine skips `apply_run_completion_side_effects` (no `next_run_at`, no auto-pause, no DLQ sync for dlt tenants). | `scheduled_ingestion/services.py:111-144` |
| R2-P6 | **Internal config endpoint serves decrypted credentials with fallback-open auth** when `INTERNAL_API_KEY` is unset (sibling endpoint masks — this one doesn't). | `data_movement/internal_views.py:27-29,64,85` |
| R2-P7 | **dlt-flagged tenants get metadata-only ingestion** — no File/Dataset/DQ/search created (semantic regression vs legacy path). | `ingestion_execution.py:148-164` |

### 3.4 Data integrity & caches
| # | Finding | Evidence |
|---|---|---|
| R2-I1 | **Unlocked read-max-then-insert version allocation at 6+ sites** while `locked_contract_version()` exists and is used elsewhere; ML contract generation deterministically collides on version=1. | `integrations/services/discovery_service.py:1219-1234`, `ml/services.py:157` |
| R2-I2 | **Pre-commit cache invalidation** in `update_contract` (concurrent readers re-cache the old row); contracts-list cache **returns empty for page ≥ 2** (double-slice); lineage edits never invalidate the lineage cache; `.update()` transitions bypass signals/caches. | `contracts/cache_invalidation.py:233-296`, `views_crud.py:458-484`, `lineage_edit_service.py:577` |
| R2-I3 | **Soft-delete vs unique constraints**: re-listing a DELETED asset → permanent conflict; re-creating a soft-deleted tenant's slug → 500; soft-deleted `ExternalResourceReference` **still grants data access** (deletion is cosmetic in access paths). | `marketplace/models.py:129-133`, `virtualization/services/query_service.py:601` |
| R2-I4 | **Admin tenant delete bypasses the tombstone signal** (QuerySet.update skips post_save) → consumer 90-day grace never materializes; Delta Share PROTECT FKs also doom the hard-delete sweep. | `tenants/admin_tenant_delete.py:182-187` |

### 3.5 Frontend (identity-boundary class)
| # | Finding | Evidence |
|---|---|---|
| R2-F1 | **Impersonation is a non-functional shell that lies about identity** — token never persisted/attached; admin acts under their own identity while the red banner says otherwise. | `impersonationStore.ts:16-27` vs `client.ts:282-336,437-442` |
| R2-F2 | **Query cache never cleared on logout/login/tenant switch** + tenant-less keys → cross-tenant display; capabilities cache not tenant-keyed. | `AppProviders.tsx:22`, `Header.tsx:92-110`, `capabilitiesService.ts:415-434` |
| R2-F3 | **`useActiveTenantId()` always null** (store field never written) → SSE notification stream dead in production ("real-time" = 60s poll). | `authStore.ts:79,109`, `useNotificationStream.ts:22` |
| R2-F4 | **Auth lifecycle races**: safety timeout doesn't cancel the retry loop (late success re-authenticates after logout); two refresh paths, single-flight on one; `refreshUser` logs out on any transient error. | `authStore.ts:165-214,405-421`, `authService.ts:146-176` |
| R2-F5 | Zero dirty-state guards; silent `console.error` save failures in scheduled edit pages; audit-log pagination is a stub (`console.log('Next page')`). | `ScheduledIngestionEditPage.tsx:53-55`, `AuditEventListPage.tsx:45-46` |

### 3.6 Public mirror (executed)
| # | Finding | Evidence |
|---|---|---|
| R2-M1 | **The published tree fails its own CI**: shipped `ci-core.yml` runs GATE-29 blocking → 192 violations (warn-only in private); ≥14 core test modules carry unguarded top-level paid imports → pytest collection crash; shipped `seed_smoke_fixtures` crashes on `--help`. | executed against `/tmp/public-tree-check` |
| R2-M2 | **Current public remote is stale** (2026-08-14, no CI, `mvp-up` references a missing compose file) — the next sync exposes R2-M1. History scrub verified effective. | `remotes/public/main` inspected |
| R2-M3 | **Shipped docs describe paid features unannotated** (23 marketplace journey mentions, ~zero "paid" labels) — the public repo documents journeys whose code isn't in it. | `docs/USER_JOURNEYS.md` in built tree |

### 3.7 Developer surface
| # | Finding | Evidence |
|---|---|---|
| R2-X1 | **Zero installable artifacts**: all four documented packages 404 on PyPI/npm (verified live). Release pipeline publishes the untested generated package, not the 1,201-test handwritten SDK; TS regenerate targets `sdk/typescript`, publish reads `sdk/js`. | registry checks + `sdk-release.yml` |
| R2-X2 | **Docs describe a phantom SDK** (`api_key=` vs `api_token=`, nonexistent extras/modules); CLI login prints "Login successful." and exits 0 on failed auth; Python proactive refresh is dead (frozen model, swallowed); JS SDK has unbounded 401 loop and a RED jest suite as shipped; committed test credentials in the shipped tree. | `cli/datahub_cli/auth.py:141-145`, `sdk/python/client.py:310-312`, `sdk/js/client.ts:112-136` |

---

## 4. The recurring meta-patterns (round-2 level)

These are the *classes* that generate the findings above — they matter more than any individual bug:

1. **The correct pattern exists, and the sibling path doesn't use it.** Locked allocator vs 6 unlocked sites; KYC in one approve path; `run_after_commit` in one file; on_commit invalidation in assets but not contracts; masked internal creds in one endpoint, unmasked in its sibling; SSRF guard real for webhooks, ImportError-broken for warehouses.
2. **Designed-but-never-wired.** Event bus (no listener ever starts; dedup self-defeating); business-rules chains (governance chain registered, never executed); incremental ingestion helpers (dead); MFA (dead, advertised); useOptimisticMutation (0 callers); mutmut fleet (DORMANT).
3. **Defense-in-depth exists as schema, not as runtime.** RLS policies complete (114/114) but the per-request GUC arm is prose; API-key scopes exist but default-off and self-mintable; magic-byte validation exists but default-off; ClamAV exists but fails open; throttles exist but the middleware no-ops without tenant context; deprecation headers exist but sunset enforcement doesn't; a11y ratchet exists but is wired to nothing.
4. **Docs describe machinery that isn't there** — and when tests noticed, the *tests* were re-documented to bless the absence (RLS GUC test), the same pattern as the round-1 retractions. The contract prose is ahead of the implementation in exactly the security-critical places.
5. **State machines are rare and unguarded where they matter** — transformation has a good one; orders have one with a PATCH-sized hole; runs/ingestions/exports have none; PaymentTransaction has none.
6. **Idempotency is assumed from check-then-act** — Stripe webhooks, webhook deliveries, subscription create, usage sync, tenant slug, marketplace `/purchase`.

---

## 5. Impact on the round-1 verdict

The round-1 verdict stands, and round 2 **adds** to the P0 list:

- P0 now includes: fix **R2-B1/R2-B2/S2** (cross-tenant enrollment, user-creation, API-key escalation) and decide **R2-S1** (arm RLS per request or correct the docs + do a full queryset-coverage audit) *before the pilot tenant onboards real users* — the pilot has a real customer IdP and real tenant UUIDs.
- Fix **R2-S3/S4** (warehouse SQLi) before any tenant runs DQ/compliance warehouse scans on the pilot.
- Fix **R2-D1/D2/D3** (money path) before any Stripe charges are real in production (Stripe is Week-4 item 4.3 — currently test-mode only, which is the window).
- The **dlt pipeline defects (R2-P1..P7) are directly in the pilot scope** (INGESTION-001/003, EXPORT-001/002, DB-013 are the pilot's own critical journeys). Pilot smoke results on these paths must be read with these defects in mind.
- **R2-S8** (staging Redis pickle + repo bind-mount + Grafana defaults) must be fixed before staging is exposed to any non-VPN traffic.
- The **public mirror** needs the R2-M1 fixes before the next sync (or the sync lands a red CI).

Also note the **positive deltas**: round 2 verified some things round 1 couldn't — webhook signature verification with dual secrets is real; payment-intent idempotency keys are real; double-fulfillment on the paid path is genuinely blocked; refresh-token family rotation is real; timing-safe login is real; the files `get_object()` IDOR audit is a reference-quality pattern; the public history scrub is effective; the core-only boot smoke passes.

---

## 6. Consolidated severity ledger (round 2)

- **BLOCKER: 6** (R2-B1…B6)
- **HIGH: 37** (S1–S13, D1–D8, P1–P7, I1–I4, F1–F5, M1–M3, X1–X2 as listed)
- **MEDIUM: ~45** (detailed in the eight source reports; highlights: refresh grace-period session transfer, impersonation escape, cookie-domain CSRF surface, CSV formula injection, RoPA PDF unescaped HTML, ClamAV fail-open, H5 magic-byte default-off, H9 staging exposure, webhook hop-2 SSRF, A-4..A-7 governance edges, B-4..B-10 plan-limit edges, E2/E5/E6/E8 soft-delete edges, D3/D4 cache edges, MEDIUM-3..21 frontend items)
- **LOW: ~40**

Full evidence per finding lives in the eight round-2 source reports (agent transcripts, this session). Suggested next step: fold the P0/P1 additions into the round-1 remediation roadmap (§8 of the main assessment) as revision 2, and open tracking tickets for the HIGHs by area owner.
