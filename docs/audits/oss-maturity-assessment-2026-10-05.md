# Open-Source Maturity Assessment — DataInteroperabilityHub

**Date:** 2026-10-05 · **Branch audited:** `prepro01` @ `99aa6d0a9` (plus working-tree delta noted where material)
**Method:** Six parallel read-only investigations (security, backend, frontend, testing/CI, ops/release, journey/UC/persona matrix) plus independent spot-verification of every BLOCKER claim.
**Evidence classes:** `VERIFIED` = read on disk / git object store inspected; `INFERRED` = reasoned from evidence, not executed. Unverified cloud-credential *validity* is treated as LIVE until rotated.

---

## 1. Executive summary

**Verdict: NOT READY for open-source release.** This is a pre-release engineering workspace with unusually deep test, traceability, and hardening discipline — but the release-shaped artifacts are missing, the git history contains live cloud credentials, and the committed code contains an unauthenticated SSO account-takeover path. Nothing about the *engineering culture* is disqualifying; several *specific, fixable* items are.

**P0 blockers (release-stopping):**

| # | Blocker | Evidence |
|---|---|---|
| 1 | **No OSI license.** `LICENSE.txt` (VERIFIED) reads: *"This software is proprietary. All rights reserved."* The SDK's `pyproject.toml` declares MIT. Release is not legally possible until re-licensed with legal sign-off. | `LICENSE.txt`, `sdk/python/pyproject.toml` |
| 2 | **Live cloud credentials in git history.** `.env.test` (committed 2025-12-12, deleted at the OSS split 2026-08-14, fully recoverable) contained a GCP SA private key, AWS key pair, Azure SP secret, Databricks PAT, Stripe test key, and a Snowflake PAT that **expires 2027-06-19**. GitHub secret scanning will reject any push of this history. | git history `f3f84bc51`; VERIFIED by security agent |
| 3 | **Staging credentials in tracked files AND 17 reachable tags.** `backups/*/config_*.tar.gz` (188 tracked files) embed `.env.staging` with a real `SECRET_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`. All `backup-staging-*` tags are reachable from `origin/main`. A plain `git clone` retrieves staging credentials. | VERIFIED by ops agent via `git cat-file` |
| 4 | **Unauthenticated OIDC SSO account takeover (live code).** `POST /api/v1/auth/sso/oidc/callback/` is `AllowAny`, decodes a client-supplied `id_token` with `verify_signature/aud/exp` **all disabled** (`hub/apps/auth/sso.py:188-196`), finds-or-`create_user`s an **ACTIVE** user from the unverified `email` (`sso.py:205-223`), and issues a real platform JWT (`sso_views.py:325`). Precondition: tenant has an OIDC entry in `TenantConfig.sso_config` — which pilot task 3.1 (marked done) is actively wiring against the customer IdP. Spot-verified by me against the working tree. | `hub/apps/auth/sso.py:188-223`, `hub/apps/auth/sso_views.py:305-332` |
| 5 | **CI has had zero runs since 2025-04-25.** The 79-workflow, 30+-gate fleet is operator-armed on 4 branches; Actions minutes were exhausted and never re-enabled (`ci.yml:1-27` header, VERIFIED). Every "green gate" claim in this repo is a *local* run. The first real CI run will likely trip the fully expired mutation-gate allowlist (148/148 entries expired 2026-07-25). | `ci.yml:1-27`, `scripts/mutation_coverage_allowlist.txt` |
| 6 | **Real TLS private keys tracked in HEAD.** `infrastructure/postgres/certs/{ca,postgres,pgbouncer}.key` are genuine 4096-bit RSA private keys. | VERIFIED by security agent |
| 7 | **No release has ever existed.** 17 tags, all `backup-staging-*`; zero semver tags; CHANGELOG 100% `[Unreleased]`; `main` is **766 commits behind** the working branch (last main commit 2026-03-16), so the deploy/docker-build trigger branches are stale. | VERIFIED by me and ops agent |
| 8 | **A stranger cannot bootstrap the project.** No README quickstart; `setup.sh` uses a legacy binary and a wrong `manage.py` path; `make dev-env` leaves a literal `__INTERNAL_API_KEY__` placeholder that crashes the microservices; the two commands README/CONTRIBUTING tell contributors to run first (`make boundary-check`, `make publish-check`) **do not exist** as Makefile targets. | VERIFIED by me |

**What is genuinely strong (and rare):**

- **Tenant isolation is complete and enforced**: 114/114 tenant-scoped models have RLS policy migrations, with a diff-based blocking CI gate, an allowlist, and a `tenant_context` pattern in worker paths. The CLAUDE.md contract is TRUE here.
- **Migration hygiene is best-in-class**: drift check on every branch, reversibility against a real Postgres (~670 migrations reversed + re-applied), django-migration-linter wired in.
- **Traceability discipline**: 100% backend marker coverage (182 journeys, 147 UCs), 94% E2E journey coverage, zero gate-invisible journeys, all sync gates green today.
- **An "anti-theater" meta-layer**: a falsifiability harness that proves gates *can* fail, a CI-arming checker, 101 self-tests for the tooling, skip-debt ratchets that are actually shrinking.
- **Real production-grade thinking**: ExternalSecrets for Helm secrets, SHA-pinned Actions with a dependabot rotation strategy, copyleft-blocking license scans, Merkle-chained audit logs, fail-hard production settings, promtool-validated alerts, staging backup/restore drills with recorded evidence.

The recurring systemic weakness is **documented enforcement that doesn't exist**: advisory gates presented as blocking, retracted-but-still-quoted contract claims, dead scripts wired to nothing. Section 10 inventories it.

---

## 2. Maturity scores

Scale 1–5 (5 = release-grade). Scores weigh breadth, depth, veracity (does it actually enforce what it claims), and OSS fitness.

| Dimension | Score | One-line justification |
|---|---|---|
| Backend architecture | **4.0** | Real RLS/audit/throttle/migration estate; a 215k-LOC contracts monolith and contract drift drag it down |
| Traceability (personas/UC/journeys) | **4.5** | Best dimension in the repo; 100% backend coverage, gates actually green |
| Frontend engineering | **3.5** | Strong security/resilience + deep test estate; dead gates, i18n façade, Node-18 workflow rot |
| Testing & CI | **3.0** | Extraordinary breadth and meta-testing; but zero CI runs since 2025-04, warn-only-by-default, ~58% of quality scripts orphaned |
| Ops & release | **3.0** | Real drills and pipeline engineering; no releases, no versions, broken bootstrap, unproven K8s deploy |
| Security | **2.5** | Internals are excellent (RLS, token hygiene, encryption, hardening); a live auth bypass, SAML stub, and credential-laden history dominate the score |
| Docs & governance | **3.0** | Deep, honest in places, self-contradictory in others; broken contributor entry points; 1,348-file doc duplication |
| **Overall OSS readiness** | **1.5** | Not releasable today (license, secrets, auth bypass, dead CI, no releases) |

---

## 3. Feature / functionality maturity matrix

Tiers: **A** = mature (deep backend + E2E + enforced contracts) · **B** = functional (shipped, good coverage, partial gaps) · **C** = early/thin (shipped, weak coverage or known gaps) · **D** = stub/broken (shipped code that doesn't work or is insecure) · **PAID** = excluded from the public mirror by `scripts/publish_paths_exclude.txt` (assessed for the private platform; journeys/UCs for these ship in docs but not code).

| Feature | hub/apps | Backend tests | E2E | Tier | Key notes |
|---|---|---|---|---|---|
| Assets / Files / Datasets | assets, files, datasets | ~2,200 (batch 1) | DPO/DE full | **A** | RLS-verified; ClamAV scan gated; presigned-upload re-signing correct |
| Contracts / ODPS / ODCS / Lineage | contracts (+jobs) | ~260 files (batch 2) | DPO/DE full | **A** | 215k LOC monolith (risk); lineage cap flags ×5 |
| Compliance + DQ + Governance | compliance, dq, governance | ~2,800 (batches 3–4) | CPO full | **A** | ABAC real at 14 sites; approval-chain contract verified |
| GDPR/privacy pack (DSAR, consent, RoPA, DPIA, breach) | 7 apps | batch 4-6 | CPO 67% | **B** | DSAR spec unregistered in persona aggregator; 5 CPO journeys "(Planned)" |
| Auth / tenants / users | auth, tenants, users, platform | batch 5 | AUTH 100% | **B→D for SSO** | JWT token-versioning, hashed API keys are excellent; **OIDC = P0 bypass, SAML = `{}` stub** |
| Search | search | batch 5 | DC full | **A** | Throttle tenant-keyed, `SEARCH_PERFORMED` audit verified |
| Scheduled ingestion / export | scheduled_ingestion/export | batch 5/13 | INGESTION/EXPORT 100% | **A** | dlt spine real; cursor-based incremental ingestion |
| Integrations / connectors | integrations | ~1,500 (batch 6, 21 sub-batches) | DE full | **A** | Live legs env-gated (W16); CKAN token rotation tooling real |
| Warehouses + Databricks control plane | warehouses, databricks_admin | ~1,300 (batches 10/13) | DB 100% (19 journeys) | **B** | **Provider-boundary contract violated in ≥5 places**; live-E2E gated; budget-cap guardrail real |
| Webhooks / Audit / Observability | webhooks, audit, observability, health | batch 8/10 | AUD 100% | **B** | Merkle audit chain real; webhook async-retry executor gap (known incident class) |
| Marketplace | marketplace | ~1,700 (batch 3) | MP 100% | **B · PAID** | Compliance-gate chain + ABAC real; Stripe live-path untested (Week-4 item 4.3) |
| Billing / subscriptions | billing | batch 3 | TA billing-upgrade | **B · PAID** | Free-plan invariants; Stripe idempotency untested |
| Semantic layer (SPARQL) | semantic | batch 12-2 (493) | via UC | **B · PAID** | `SPARQL_EXECUTED` audit + complexity chain verified; Fuseki ops finicky |
| ML inference / AI | ml, ai | batch 7 (12 sub-batches) | DS 100% (6 specs) | **C · PAID** | `ml_mvp_in_scope=false`; deployment_id contract |
| Social / communities | social | batch 5 | CM 100% (4 specs) | **C · PAID** | Small app; ratings/reviews tied to community |
| BaaS / developer portal | baas, developer | batch 8 | DEV 90% | **C · PAID** | Plugin lifecycle (ALPHA→BETA→AVAILABLE) real; GraphQL-LD journey "(Planned)" |
| GraphQL (3 stacks) | graphql, graphql_graphene, graphql_ld | batch 8-1 (~316) | — | **C · PAID** | Three parallel stacks; `graphql_ld` has no urls.py; consolidation needed |
| Data mesh / virtualization | mesh, virtualization | batches 4/8 | DMO 100% (5 specs) | **C** | Gated routes; virtualization UCs backend-only |
| Versioning / websocket | versioning, websocket | batch 8 | — | **C** | versioning = 1 view / 820 LOC |
| SSO (OIDC + SAML) | auth | new untracked tests (working tree) | UC-AUTH-006 | **D** | P0 bypass (OIDC), inert (SAML); active pilot work in uncommitted tree |
| PWA / offline | frontend public/ | — | — | **D** | `sw.js` never registered; manifest not linked; incoherent story |
| i18n (non-English) | frontend locale/ | — | — | **D** | 6 locales loaded, runtime hardcoded to English, es/fr ~63% translated |

---

## 4. Persona maturity matrix (13 personas, 182 journeys)

| Persona | Journeys | E2E spec | Backend marker | Critical | E2E% |
|---|---|---|---|---|---|
| Authentication (Visitor/All) | 11 | 11 | 11 | 4 | 100% |
| Cross-Cutting | 1 | 1 | 1 | 0 | 100% |
| Data Product Owner | 18 | 18 | 18 | 6 | 100% |
| Data Engineer | 16 | 16 | 16 | 3 | 100% |
| Data Consumer | 15 | 15 | 15 | 1 | 100% |
| Tenant Admin | 11 | 11 | 11 | 2 | 100% |
| Platform/Marketplace Admin | 21 | 21 | 21 | 2 | 100% |
| Auditor | 6 | 6 | 6 | 0 | 100% |
| Data Scientist | 5 | 5 | 5 | 0 | 100% |
| Data Analyst | 4 | 4 | 4 | 0 | 100% |
| Community Manager | 4 | 4 | 4 | 0 | 100% |
| Data Mesh Domain Owner | 6 | 6 | 6 | 0 | 100% |
| External Developer | 10 | 9 | 10 | 0 | 90% |
| Compliance & Privacy Officer | 18 | 12 | 18 | 6 | 67% |
| ODPS (DPO/DE/DC) | 6 | 1 | 6 | 0 | 17% |
| Marketplace Integration | 7 | 7 | 7 | 0 | 100% |
| Scheduled Operations | 4 | 4 | 4 | 4 | 100% |
| Databricks Control Plane | 19 | 19 | 19 | 1 | 100% |
| **Total** | **182** | **171 (94%)** | **182 (100%)** | **29** | — |

**Gate-invisible journeys (no E2E AND no backend marker): NONE.** Backend marker coverage is 100% for both journeys and UCs. All sync gates (GATE-26/27/28) ran green on 2026-10-05.

**Journeys with no E2E spec (12) — all backend-covered:**
CPO-011, CPO-012, CPO-013, CPO-014, CPO-016 (marked "(Planned)" in docs), **CPO-015** (DSAR — not marked planned but only has the unregistered `dsar-otp-flow.spec.ts`), DEV-010 (GraphQL-LD, "(Planned)"), and **ODPS-001…005** — the largest persona-level E2E hole (mitigated by 12 backend UC-ODPS markers + 3 frontend UC specs).

**Other traceability drift (gate-invisible):**
- 25 JOURNEY-named specs are imported by no persona aggregator (AUTH-005/006/007, CPO-017, PA-002…009, PA-015, EXPORT-002, TENANT-ONBOARDING, etc.) — they still run via the `testDir` glob but are invisible to persona-mapping and persona-scoped batch selection.
- `persona-journey-mapping.yaml` is stale in two ways: underscore-vs-hyphen persona keys; TA mapping missing 3 journeys (144 mapped vs 147 imported). The regenerator is "Planned (Phase 5)" — no drift check wired.
- Critical-registry header claims "37 UC + 33 journey" but the curated lists hold 35 + 29; the gate scripts regex the WHOLE file and absorb 6 paid Databricks IDs from another section into the blocking set — misleading header, silently widened gate.
- Duplicate spec `JOURNEY-EXPORT-001.spec.ts` exists in two directories and runs twice.
- Doc headers stale: USER_JOURNEYS.md says "181" (actual 182); USE_CASES.md says "146" (actual 147).
- 9 quarantined feature specs (none journey-named, none critical) — nightly-only, advisory.

**UC domains (147 UCs, 100% backend-marked):** Authentication 7, Asset Mgmt 4, Contract/Community 4, DQ 1, Compliance/Governance 14, Marketplace 11, Data Consumer/Analyst 5, Billing 2, Transformation 8, Scheduled Ingestion 5, Scheduled Export 4, Semantic 6, AI/ML 10, Social 6, Data Mesh 5, Virtualization 4, Advanced Observability 4, Integration Ecosystem 5, Developer Experience 7, ODPS 12, Lineage 3, Webhooks 1, Databricks Control Plane 19.

**Critical path: 100% healthy.** All 29 curated critical journeys have E2E + backend + doc entries; all 35 critical UCs backend-marked; none quarantined. (9 of the critical UCs are paid-layer.)

---

## 5. Dimension findings

### 5.1 Security

**P0 — must fix before any release (all VERIFIED unless noted):**

| Severity | Finding | Where |
|---|---|---|
| BLOCKER | OIDC SSO unauthenticated account takeover/creation: unverified `id_token` → `get_or_create` ACTIVE user → real JWT. No feature flag, no throttle. No adversarial SSO tests in committed code. **Pilot task 3.1 is wiring OIDC against the customer IdP — treat as urgent.** | `hub/apps/auth/sso.py:188-223`, `sso_views.py:305-332` |
| BLOCKER | Live cloud credentials recoverable from history (GCP SA private key, AWS pair, Azure SP secret, Databricks PAT, Stripe test key, Snowflake PAT expiring **2027-06-19**). History rewrite + full rotation mandatory. | git history (`f3f84bc51`) |
| BLOCKER | Staging `.env.staging` (SECRET_KEY, DB password, MinIO/Fuseki/Grafana passwords) in history AND in tracked `backups/*.tar.gz` AND in 17 reachable tags. | `backups/`, `backup-staging-*` tags |
| BLOCKER | Real 4096-bit RSA private keys tracked in HEAD. | `infrastructure/postgres/certs/*.key` |
| HIGH | SAML SSO is a stub — `_parse_saml_response` returns `{}`, no python3-saml/xmlsec anywhere. "SSO" as a documented feature is either a bypass (OIDC) or inert (SAML). | `hub/apps/auth/sso.py:96-99` |
| HIGH | Vulnerable-dependency findings never block PRs (pip-audit `|| true`; CVE audit `--non-blocking`); mixed pinned/ranged requirements. | `ci.yml:291-345`, `requirements.txt` |
| MEDIUM | `/metrics/` unauthenticated by design (asserted by a test); localhost fallback defaults in settings (S3 `localhost:9010`, service URLs) are self-hosting footguns. | `hub/settings.py:1445-1466` |

**Verified strengths:** RLS estate complete + CI-blocking; JWT with server-side token-version invalidation; APIKey/RefreshToken stored as SHA-256 hashes with family rotation; production fail-hard on DEBUG/SECRET_KEY/ENCRYPTION_KEY/CORS misconfig; Fernet encryption for webhooks/credentials/SSO configs; audit `redact_pii` with fail-closed tests; ExternalSecrets in Helm (no inline secrets); copyleft-blocking license scan; SHA-pinned Actions + dependabot strategy; `.gitignore` correctly covers `.env*` going forward.

### 5.2 Backend architecture

**Verified strengths:** RLS 114/114 (see §1); migration estate best-in-class; throttle/audit/metric contracts on search/SPARQL hot paths real and tenant-keyed; OpenAPI generated, validated, inventoried; RQ worker tiering with starvation prevention; 53-app manifest with clean core/paid split (`HUB_CORE_ONLY`).

**Findings:**

| Sev | Finding |
|---|---|
| HIGH | **Provider-boundary contract violated in ≥5 places** (advisory enforcement demonstrably leaked): `warehouses/views.py:361` (imports `budget_enforce`), `transformation/credential_resolver.py:48,439` (estate models + M2MTokenCache), `transformation/databricks_staging.py:22` (2nd unsanctioned `DatabricksApiClient` consumer), `jobs/tasks_base.py:569-589` (3 estate job imports), `users/management/commands/ensure_e2e_user_roles.py:235` |
| HIGH | **CLAUDE.md DRF-3.16 claim is FALSE against the pinned install**: "throttled() hook removed / dead code / crashes" — pinned `djangorestframework==3.16.1` still calls `self.throttled()`; two live overrides (`search/views.py:691`, `graphql_ld/views.py:746`) depend on it. A maintainer following the doc would delete a working 429-audit path. |
| HIGH | **Error-catalogue "merge gate" is false**: CI runs `check_error_codes_catalogue.py || true` with a ~720-code undocumented baseline; catalogue holds ~41 rows vs 570 `error_code=` usages. |
| MEDIUM | Contracts app = 215k LOC / 276 test files monolith; two committed 200KB+ `_services_legacy.py` files; 50 orphaned modules (incl. 5 unused API middlewares). |
| MEDIUM | Three parallel GraphQL stacks (strawberry active; graphene + channels commented out; `graphql_ld` has no urls.py). |
| MEDIUM | 8/15 signal modules lack `tenant_context` (currently enqueue-only — fragile as handlers accrete DB work; no lint). |
| MEDIUM | 132 management commands, 101 without audit coverage (cross-tenant-by-default contract is manual). |
| MEDIUM | Webhook async-retry executor gap: `WEBHOOK_ASYNC_DELIVERY=False` inline retry writes `next_retry_at` with no processor (recorded incident class: stale `attempt_number`, breaker poisoning). |
| LOW | `shared/` root dir dead; `cli/build/lib` tracked; honest `TODO: Implement actual…` workflow stubs exist in orchestration/marketplace/transformation workflows. |

### 5.3 Frontend

**Verified strengths:** axios evicted after the DPRK-linked RAT incident (tokens in module memory only, CSRF header, `X-Tenant-ID` skip-lists, `X-Correlation-ID`, RFC-8594 interceptor); capability gating with documented per-key fail-open/fail-closed semantics and incident history in comments; hardened error-boundary chunk-recovery; nginx config with CSP/HSTS/token-redaction; 350 vitest files + ~484 E2E specs + hard a11y CI gate; strict TS; 138 lazy route chunks.

**Findings:**

| Sev | Finding |
|---|---|
| HIGH | **Dead gates**: bundle-size gate trivially passes (baseline `total_gzipped_bytes: 0`, checker skips); a11y ratchet wired into no workflow (baseline placeholder since 2026-05-14). |
| HIGH | **Inconsistent Node across frontend CI**: `frontend-ci.yml`/`frontend-tests.yml`/`visual-regression.yml` pin Node 18 against Vite 7.3.1/React Router 7.13.2 engines (≥20/22) — broken or ignored; a `generate-sdk` step self-skips with `|| echo "script not found"`. |
| HIGH | **i18n is a façade**: runtime language hardcoded `'en'`, no switcher, `<html lang="en">`; es/fr ~63%; feature namespaces English-only; dead `ar.ts`. |
| HIGH | **No enforced visual regression**: Chromatic self-skips without external token; Playwright visual workflow archived. |
| MEDIUM | 2,401-line `routes.tsx` (138 lazy routes) + ~1,060-line `capabilitiesService.ts` — single-file monoliths. |
| MEDIUM | Vitest needs 10 sequential shards / 8 GB heap (OOM workaround); one test file excluded from default runs (needs 16–32 GB). |
| MEDIUM | 6.4 MB `storybook-static/` build output tracked; stray `frontend@0.0.0`/`bash` files; legacy `.eslintrc.cjs`; cross-major `glob` override; `@types/react-router-dom@5` against router v7. |
| LOW | Web-vitals gate is permanently advisory (`sys.exit(0)` always); Google Fonts CDN (airgap concern); no browserslist/platform statement. |

### 5.4 Testing & CI

**Verified strengths:** 2,600+ backend test files in 69 machine-checked batches with `TEST_DB=auto` fresh-clone isolation and free-plan invariants; skip-debt ratcheted and shrinking (3,087 sites, 0 expired, GATE-40 blocking); falsifiability harness proving gates can fail; CI-arming checker; 101 tooling self-tests; Docker-only contributor path works with zero third-party secrets; env policy (CI raises, local skips) with 5xx-as-down semantics.

**Findings:**

| Sev | Finding |
|---|---|
| BLOCKER | **Zero CI runs since 2025-04-25** (Actions exhausted; `ci.yml` header admits it). The entire merge-protection story is untested end-to-end; first real run will hit the expired mutation allowlist. |
| BLOCKER | **Fork CI breaks**: `visual-regression.yml` hard-fails on fork PRs (empty Chromatic token, `skip: false`, no guard); **zero `head.repo.fork` checks anywhere**; 30+ workflows consume org secrets. |
| HIGH | GATE-01…42 warn-only on PRs by design; enforcement lives in hand-duplicated "blocking twins" — GATE-37 (bandit) fell through and is unwired. |
| HIGH | Mutation allowlist fully expired (148/148 entries, 2026-07-25) → gate would hard-fail on next frontend run. |
| MEDIUM | 90% backend coverage threshold is theater (`continue-on-error` + exception swallow); four mutmut workflows DORMANT with `|| true`; `test-results-reporting.yml` has a path bug (aggregates nothing); quarantine baseline ratchet unwired. |
| MEDIUM | 97/168 quality scripts (58%) orphaned — including 26/28 `audit_*` and 32/34 `verify_*`; three reusable workflows have no caller. |
| MEDIUM | envpolicy adoption partial (19 files vs 24 raw `pytest.skip`); `make test` bare-pytest is a trap without the compose stack; committed run artifacts (`test-results/skip-events.jsonl`, `guard-failures/`). |

### 5.5 Ops & release

**Verified strengths:** real migration-reversibility gate; promtool-installing alert CI; staging backup/restore drills with recorded evidence; U.6–U.8 staging pipeline contract (post-deploy, migration rehearsal with data-loss veto, go/no-go ledger); deploy pipeline with auto-rollback; ExternalSecrets; 78 Grafana dashboards; django-structlog JSON logging with PII redaction; 192 runbook files + detailed incident policy; backup-postgres.sh with retention sweep.

**Findings:**

| Sev | Finding |
|---|---|
| BLOCKER | Proprietary `LICENSE.txt`; no releases/versions (see §1). |
| BLOCKER | Backup tarballs + tags carry staging credentials (see §1). |
| HIGH | **No stranger bootstrap**: README has no quickstart; `setup.sh` broken; `make dev-env` misses `__INTERNAL_API_KEY__`; `HOST_SIDE_VERIFICATION.md` assumes pre-existing containers. |
| HIGH | **Prod images unhardened**: zero digest pins, floating base tags, 14/16 Dockerfiles run as root, no Dockerfile HEALTHCHECKs, no migrations-on-boot in prod/staging, read-only rootfs in test stack only. |
| HIGH | **K8s deploy path unproven**: AWS staging "not provisioned yet" (2026-10-04 runbook decision); all CI validation dry-run; `k8s/` kustomize tree legacy/unexercised. |
| HIGH | **Observability blind spots**: 19/44 alert-rule files never loaded by any Prometheus config; Grafana dashboard provisioning lacks a provider file; no physical audit-DB isolation. |
| HIGH | **Data-restoration gaps**: prod backup verifies by size not hash; MinIO mirror leg empty with no restore path; tenant-deletion coverage audits are dead (`--ci` no-op, always exit 0, report untracked). |
| HIGH | `main` 766 behind; frontend-image fix in `docker-build.yml` uncommitted; `sdk-release.yml` publishes to prod PyPI/npm from a nonexistent `sdk/python_generated` dir; SSO IdP libs absent from requirements. |
| MEDIUM | `datacontract-service` installs `@datacontract/cli@latest` at build; `CI_CD_SUMMARY.md` claims "6 workflows" vs actual 79; helm chart metadata placeholder (`your-org`, `platform@example.com`). |

### 5.6 Docs & governance

| Finding | Note |
|---|---|
| MEDIUM | README is 33 lines aimed at the merge-back workflow, not at running/understanding the product — no quickstart, no architecture diagram, no feature list. |
| HIGH | README/CONTRIBUTING/OSS_CONTRIBUTION all reference `make boundary-check` / `make publish-check` — **targets that don't exist** (VERIFIED by me). First-run contributor experience breaks at step 1. |
| MEDIUM | `docs/docs/` = 1,348-file tracked duplicate of `docs/` (identical content); plus `docs/deprecated-doc/`, `docs/api-contracts/missing/` — navigation/sync burden. |
| MEDIUM | Governance doc counts drift: CLAUDE.md says 181/146 and "37+33"; actuals are 182/147 and 35+29; TRACEABILITY_ARCHITECTURE.md still says 166/142/152 (from 2026-06). |
| MEDIUM | Public mirror ships docs registries describing **paid-layer journeys whose code is excluded** by `publish_paths_exclude.txt` — verify the scrub pass rewrites them or the public repo documents features that don't exist. |
| LOW | No CODE_OF_CONDUCT.md, no issue templates, no GOVERNANCE.md; openspec contains scratch change dirs (`feat1`, `test2`, `perfect1`, `sonnetgapfix`); 127 stray `b*.txt` logs and a 0-byte `=` file in the root; 17 tags are backup dumps. |
| GOOD | SECURITY.md is substantive (PGP, SLAs, bounty); CONTRIBUTING.md documents DCO; PR template is genuinely good; CODEOWNERS is thorough (though it references `@meshant/…` teams); CHANGELOG is real, curated, Keep-a-Changelog format — but all Unreleased. |

---

## 6. The Open Core boundary (what actually ships publicly)

The public mirror excludes: 11 of 56 hub apps (marketplace, billing, semantic, baas, rate_limiting, ai, ml, social, graphql×3), all `services/` microservices, `infrastructure/`, `helm/` (except `community/`), `k8s/`, most of `monitoring/`, production compose files. Built by `scripts/publish_tree.sh` + `build_replace_text.py` scrub + `publish_paths_exclude.txt`, with a merge-back workflow (public PR → private review → DCO + gitleaks + boundary gates → publish) and a `remotes/public/main` mirror whose history was already scrubbed.

**Assessment:** the machinery is real and unusually thoughtful (the history-scrubbed public remote proves it has been exercised). But the primary repo — this working repo — carries all the P0 liabilities, and the sanitization itself is only partially verified (docs registries describing excluded features; the ops agent's finding that `main` and tags carry staging credentials means the *primary* history cannot be published as-is, only the filtered mirror).

---

## 7. Maintenance sustainability

- **Skip/placeholder debt**: 3,087 sites, ratcheted per-bucket, shrinking, 0 expired. Only ~27 sites carry the `TICKET=/EXPIRES=` annotations the contract prose describes — enforcement is a growth ratchet, not the documented "every reason" rule. Honest, but the doc overstates it.
- **Contract drift is a live failure mode**: CLAUDE.md encodes framework behaviors (DRF 3.16 hook, Django 6, RQ 2.x) that have already drifted once (the throttled() claim is now false; the semgrep claim was retracted in-place after P.9). No mechanism re-verifies contract claims against pinned dependencies. Recommend a quarterly "contract audit" job that re-runs this assessment's checks.
- **Docs-vs-reality pattern** (recurring across all six reports): advisory gates presented as blocking (error catalogue, 90% coverage, web-vitals, mutmut), dead scripts wired to nothing (a11y ratchet, bundle-size baseline, tenant-deletion audits, runbook coverage), orphaned workflows (3 reusable, 4 mutmut, archived visual), stale duplicated config (Node 18 vs 22).
- **Team-dependency risks**: single-maintainer knowledge embedded in Makefile batches, E2E wrapper concurrency guards, credential-drift detectors, and the publish pipeline; onboarding docs point at broken commands.

---

## 8. Remediation roadmap

### P0 — release-stopping (before any public repo exists)

1. **Legal**: choose an OSI license (recommend Apache-2.0 for the core given the dual-licensing model), get legal sign-off, replace `LICENSE.txt`, complete `NOTICE.md`; align SDK's MIT declaration with the chosen license.
2. **Secrets remediation (single tracked effort)**: run gitleaks/trufflehog over full history (agent's exhaustive pattern sweep was timeout-limited); rewrite history (filter-repo) removing `.env*`, `backups/*.tar.gz`, TLS keys, and the 17 `backup-staging-*` tags; **rotate every credential found**: GCP SA key, AWS pair, Azure SP secret, Databricks PAT, Snowflake PAT (expires 2027-06-19), Stripe test key, Django SECRET_KEY, staging DB/MinIO/Fuseki/Grafana passwords, and regenerate `infrastructure/postgres/certs/*`. Verify with secret-scanning on a dry-run push.
3. **SSO**: fix or disable before pilot OIDC go-live — JWKS-based signature/audience/expiry validation (authlib/pyoidc) or feature-flag the whole `SSOViewSet` off; delete the SAML stub or implement it; add adversarial SSO tests (unsigned token, wrong aud, expired, role forgery); add `throttle_classes`; record the decision for pilot task 3.1 (its IdP work is in the uncommitted tree — re-audit the final commit).
4. **CI reality**: re-arm Actions billing and run one full green pass; re-baseline the expired mutation allowlist (`--update`); add `head.repo.fork` guards + secret-presence self-skips + fix the visual-regression fork failure so a fork's CI is green out of the box.
5. **Release machinery**: merge `prepro01` → `main` (766 commits); cut the first semver tag; wire release-please; give every component one version (root `pyproject`, `hub/`, frontend, helm appVersion); publish the first real CHANGELOG release section.
6. **Bootstrap**: write an actual README quickstart (docker-only path, verified from a clean checkout); fix `setup.sh` or delete it; fix `make dev-env`'s `__INTERNAL_API_KEY__` miss; create the `make boundary-check` / `make publish-check` targets the docs promise (or fix the docs).

### P1 — before promoting to a community

7. Make the error-catalogue gate blocking (or relabel it); backfill the catalogue.
8. Correct CLAUDE.md's DRF 3.16 claim; decide the `throttled()` override policy; add a contract-drift audit to CI.
9. Clean up the 5 provider-boundary violations (route through the sanctioned seams); consider promoting GATE-29-style import checking to CI.
10. Fix dead gates: bundle-size baseline, a11y ratchet wiring, web-vitals label, Node version consistency across workflows, `test-results-reporting` path bug, quarantine baseline ratchet.
11. Delete `docs/docs/` duplication; fix stale registry counts (181/146, 37+33); wire the persona-mapping regenerator + drift check; fix duplicate EXPORT-001 spec.
12. Wire the 97 orphan scripts or delete them; load the 19 unloaded alert files (or delete); add Grafana provisioning provider file.
13. Hardening: digest-pin base images, non-root Dockerfiles, prod HEALTHCHECKs, migrations-on-boot or a documented gate; backup hash verification + a real MinIO restore drill; delete the backup tags and tarballs.
14. ODPS + CPO E2E journey specs (largest coverage holes); register the DSAR spec in the persona aggregator.

### P2 — maintenance debt

15. Decompose the contracts monolith; delete the 200KB legacy service files; consolidate the three GraphQL stacks.
16. Signal `tenant_context` lint; management-command audit coverage for the 101 uncovered commands.
17. Frontend: split `routes.tsx`; retire the cross-major `glob` override; remove `storybook-static`/stray files; i18n decision (finish es/fr or drop non-English claims); PWA decision (finish or delete).
18. Root litter cleanup (127 `b*.txt`, `=`, scratch openspec dirs); add CODE_OF_CONDUCT, issue templates, GOVERNANCE.md; de-duplicate the `runbooks/` root dir.

---

## 9. Honest credit

What deserves to survive open-sourcing scrutiny, verified and specific:

1. **Tenant isolation is real engineering, not aspiration**: 114/114 RLS-covered models, diff-based blocking lint, allowlist, `tenant_context` in workers, admin-DB BYPASSRLS pattern with audit events.
2. **Migration estate**: drift-checked on every branch, reversibility-proven against a live Postgres, linter-wired — this is how mature projects handle schema.
3. **The anti-theater layer**: a harness that mutates gates to prove they *can* fail, a checker that proves workflows are parseable and armed, 101 tests for the tooling itself. This is the strongest signal in the repo that the team cares about truth in its own CI.
4. **Security culture under pressure**: axios evicted after a real supply-chain attack with the rationale preserved in code; tokens in memory only; SHA-pinned Actions with a rotation strategy; ExternalSecrets; fail-hard production settings; credential-drift detectors built from rehearsed failure.
5. **Traceability discipline**: every journey and UC is backed by at least one executed test; the critical path is 100% covered and none of it is quarantined.
6. **Operational rehearsal evidence**: the pilot-readiness plan records real rehearsals with real root-cause fixes (silent `down -v` no-op, credential drift, CKAN probe vacuity) — honest execution records, not checklist theater.

The path to open source is not "fix everything": it is the eight P0 items in §8 — each is concrete, bounded, and mostly mechanical — followed by a decision on which P1 items gate the first release.

---

## Appendix — investigation sources

Six parallel read-only investigations (2026-10-05): security & secrets-in-history; testing & CI maturity; backend architecture; frontend maturity; ops/infra/release readiness; journey/UC/persona coverage matrix (all gates run live: GATE-26/27/28 green). Independent main-thread verification: LICENSE, SSO bypass code path, Makefile target existence, docs/docs duplication, registry counts, publish exclusion list, pilot-readiness task state, git tag/commit topology.
