# GA Readiness Audit — May 2026

**Date:** 2026-05-16
**Auditor:** Platform Engineering (Phase 285.1)
**Scope:** All 26 GA-stage feature flags across 13 unified readiness gates
**Target:** ≥95 score for 22/26 flags; ≥70 for all remaining with documented closure plan

## 13-Gate Unified Rubric (Phase 285.1)

Each gate scores 0–10. Total: 0–130; normalized to 0–100 scale.

| # | Gate | What it checks |
|---|------|---------------|
| 1 | CLI | `datahub <group>` command exercises the feature with ≥2 subcommands |
| 2 | SDK | SDK module with dedicated API class + ≥2 methods |
| 3 | RLS | Model has `tenant_id` → paired RLS policy migration exists |
| 4 | Throttle | View/ViewSet carries `throttle_classes`; covered by `check_throttle_coverage.py` |
| 5 | Audit | Feature emits audit events on state transitions / access |
| 6 | E2E | Playwright spec exercises the feature end-to-end against real backend |
| 7 | A11y/Axe | Route appears in axe manifest + passes axe audit (no critical/serious violations) |
| 8 | Dark Mode | Feature renders correctly in dark palette; no white-screen on theme toggle |
| 9 | Error UX | ErrorDisplay / RetryBanner / toast patterns used; no white-screens on API 4xx/5xx |
| 10 | i18n | All user-facing strings are in `en.ts` (no hardcoded English in components) |
| 11 | Runbook | Operational runbook exists in `docs/runbooks/` with triage matrix + escalation |
| 12 | Metrics | Prometheus metrics + Grafana dashboard; metric counters exist for key operations |
| 13 | Docs | Feature appears in PRODUCT_GUIDE + API reference; flag documented |

### Scoring conventions

| Score | CLI | SDK | Error UX |
|-------|-----|-----|----------|
| **10** | Dedicated command group with ≥2 subcommands | Dedicated SDK class with ≥2 methods | ErrorDisplay + RetryBanner; toast on transient errors; all API 4xx/5xx paths have user-facing messages |
| **7** | Command group exists with 1 subcommand, or feature exercised through adjacent group | SDK class exists with 1 method, or feature exercised through adjacent module | ErrorDisplay used for main flow; some edge-case error states silently handled |
| **5** | No direct CLI; feature exercised through API/adjacent group tangentially | No dedicated SDK class; feature accessible through generic HTTP client | Basic error handling (console.error or simple text); some error paths white-screen |
| **0** | No CLI path exists | No SDK path exists | No error handling |

## Per-Flag Scores (13-Gate Unified)

### 1. `data_quality_enabled` — Score: 122/130 (94)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub dq` group with run/list/quality subcommands |
| SDK | 2 | 10 | `client.dq` (DQAPI) with ≥2 methods |
| RLS | 3 | 10 | DQ models have tenant_id + RLS |
| Throttle | 4 | 10 | DQ views covered in `_MODULES` |
| Audit | 5 | 10 | DQ_RUN_COMPLETED, DQ_RULE_FAILED events |
| E2E | 6 | 10 | `frontend/e2e/journeys/dq-run.spec.ts` |
| A11y | 7 | 10 | DQ routes in axe manifest |
| Dark | 8 | 9 | DQ pages tested; scorecard chart uses adaptive palette |
| ErrorUX | 9 | 10 | ErrorDisplay on run failure; RetryBanner on transient backend errors |
| i18n | 10 | 10 | All DQ strings in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/data-quality.md` |
| Metrics | 12 | 10 | `dq_run_duration_seconds`, `dq_rule_evaluation_total` |
| Docs | 13 | 3 | PRODUCT_GUIDE §4 covers DQ but lacks GA flag documentation |

### 2. `data_quality_advanced_enabled` — Score: 122/130 (94)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | Same `datahub dq` group; `dq quality` subcommands |
| SDK | 2 | 10 | Same `client.dq` module |
| RLS | 3 | 10 | Shared with `data_quality_enabled` |
| Throttle | 4 | 10 | Same views; advanced endpoints have tighter rates |
| Audit | 5 | 10 | ADVANCED_DQ_ACCESSED event |
| E2E | 6 | 10 | Advanced DQ E2E spec |
| A11y | 7 | 10 | Advanced DQ routes in axe manifest |
| Dark | 8 | 9 | Trends/scorecards use adaptive charts |
| ErrorUX | 9 | 10 | Same DQ error patterns |
| i18n | 10 | 10 | All strings in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/data-quality.md` |
| Metrics | 12 | 10 | `dq_advanced_query_duration_seconds` |
| Docs | 13 | 3 | PRODUCT_GUIDE lacks GA flag documentation |

### 3. `compliance_fail_closed_enabled` — Score: 128/130 (98)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub compliance` group |
| SDK | 2 | 10 | `client.compliance` (ComplianceAPI) |
| RLS | 3 | 10 | Asset/ComplianceRun models have RLS |
| Throttle | 4 | 10 | Asset creation views covered |
| Audit | 5 | 10 | TENANT_FEATURE_FLAG_CHANGED, COMPLIANCE_GATE_FAILED |
| E2E | 6 | 10 | `frontend/e2e/journeys/asset-create-fail-closed.spec.ts` |
| A11y | 7 | 10 | Asset creation routes in axe manifest |
| Dark | 8 | 10 | AssetCreatePage dark-mode tested |
| ErrorUX | 9 | 10 | COMPLIANCE_GATE_BLOCKED rendered via ErrorDisplay; RetryBanner when degraded |
| i18n | 10 | 10 | Error messages in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/RB-COMP-001-compliance-fail-closed.md` |
| Metrics | 12 | 8 | `compliance_intake_gate_events_total` covers fail-closed; no dedicated counter |
| Docs | 13 | 10 | PRODUCT_GUIDE + ADR document fail-closed; flag documented |

### 4. `asset_creation_enabled` — Score: 124/130 (95)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub assets` group with create/list/update subcommands |
| SDK | 2 | 10 | `client.assets` (AssetsAPI) |
| RLS | 3 | 10 | Asset models have RLS |
| Throttle | 4 | 10 | Asset views covered |
| Audit | 5 | 10 | TENANT_ASSET_CREATION_FLIPPED |
| E2E | 6 | 10 | `frontend/e2e/journeys/asset-create.spec.ts` |
| A11y | 7 | 10 | Asset routes in axe manifest |
| Dark | 8 | 10 | Dark mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on create/update failure; validation errors surfaced inline |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/asset-creation.md` |
| Metrics | 12 | 8 | Asset creation metrics exist; no flag-specific counter |
| Docs | 13 | 6 | PRODUCT_GUIDE mentions asset creation; flag doc incomplete |

### 5. `datasets_enabled` — Score: 118/130 (91)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub datasets` group |
| SDK | 2 | 10 | `client.datasets` (DatasetsAPI) |
| RLS | 3 | 10 | Dataset models have RLS |
| Throttle | 4 | 10 | Dataset views covered; throttle scope registered |
| Audit | 5 | 10 | DATASET_ACCESSED events |
| E2E | 6 | 10 | Dataset E2E specs |
| A11y | 7 | 10 | Dataset routes in axe manifest |
| Dark | 8 | 10 | Tested |
| ErrorUX | 9 | 10 | ErrorDisplay on API failure; inline validation on edit |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 5 | `datasets-files-dr.md` is DR-focused, not operational |
| Metrics | 12 | 10 | `dataset_operations_total` |
| Docs | 13 | 5 | PRODUCT_GUIDE covers Datasets; flag not documented |

### 6. `files_enabled` — Score: 118/130 (91)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub files` group |
| SDK | 2 | 10 | `client.files` (FilesAPI) |
| RLS | 3 | 10 | File models have RLS |
| Throttle | 4 | 10 | File views covered |
| Audit | 5 | 10 | FILE_ACCESSED, FILE_METADATA_VIEWED |
| E2E | 6 | 10 | File E2E specs |
| A11y | 7 | 10 | File routes in axe manifest |
| Dark | 8 | 10 | Tested |
| ErrorUX | 9 | 10 | ErrorDisplay on upload failure; progress indicator on large files |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 5 | `datasets-files-dr.md` is DR-focused |
| Metrics | 12 | 10 | `file_operations_total` |
| Docs | 13 | 5 | PRODUCT_GUIDE covers Files; flag not documented |

### 7. `compliance_consent_enabled` — Score: 112/130 (86)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 5 | No dedicated `consent` CLI group; phase232 programme commands touch consent indirectly |
| SDK | 2 | 5 | No dedicated ConsentAPI; Phase232ProgrammeAPI covers consent paths indirectly |
| RLS | 3 | 10 | Consent models have RLS |
| Throttle | 4 | 10 | Consent views in `_MODULES` (283.3.1.2) |
| Audit | 5 | 10 | CONSENT_GRANTED, CONSENT_WITHDRAWN events |
| E2E | 6 | 10 | Consent E2E spec |
| A11y | 7 | 10 | ConsentDashboard in axe manifest |
| Dark | 8 | 9 | ConsentDashboard dark-mode tested; HMAC proof modal needs verification |
| ErrorUX | 9 | 10 | ErrorDisplay on consent grant/withdraw failure; validation errors surfaced |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/RB-COMP-002-consent.md` |
| Metrics | 12 | 10 | `consent_operations_total` |
| Docs | 13 | 6 | PRODUCT_GUIDE lacks GA flag documentation; consent model documented in ADR |

### 8. `compliance_ropa_enabled` — Score: 125/130 (96)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub ropa` group with generate/export/list subcommands |
| SDK | 2 | 10 | `client.ropa` (RopaAPI) |
| RLS | 3 | 10 | RoPA models have RLS |
| Throttle | 4 | 10 | RoPA views in `_MODULES` (283.3.3.4) |
| Audit | 5 | 10 | ROPA_GENERATED, ROPA_EXPORTED |
| E2E | 6 | 10 | RoPA E2E spec |
| A11y | 7 | 10 | RopaList in axe manifest |
| Dark | 8 | 8 | RopaList dark-mode tested; preview modal pending |
| ErrorUX | 9 | 10 | ErrorDisplay on generate failure; export errors surfaced |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/phase232-ropa.md` |
| Metrics | 12 | 10 | `ropa_generation_duration_seconds` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers RoPA; GA flag docs updated (283.6.9) |

### 9. `compliance_dpia_enabled` — Score: 128/130 (98)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub dpia` group with create/list/review subcommands |
| SDK | 2 | 10 | `client.dpia` (DpiaAPI) with ≥2 methods |
| RLS | 3 | 10 | DPIA models have RLS |
| Throttle | 4 | 10 | DPIA views in `_MODULES` (283.3.5.4) |
| Audit | 5 | 10 | DPIA_CREATED, DPIA_REVIEWED events |
| E2E | 6 | 10 | DPIA wizard + review E2E specs (284.F.5 closes prior gap) |
| A11y | 7 | 10 | DpiaWizard in axe manifest |
| Dark | 8 | 8 | DpiaWizard dark-mode tested; review steps need verification |
| ErrorUX | 9 | 10 | ErrorDisplay on submit/review failure; wizard steps preserve state on error |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/RB-COMP-005-dpia.md` |
| Metrics | 12 | 10 | `dpia_operations_total` |
| Docs | 13 | 10 | PRODUCT_GUIDE + API reference cover DPIA; flag documented |

### 10. `compliance_dsar_enabled` — Score: 126/130 (97)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub dsar` group with list/status/respond subcommands |
| SDK | 2 | 10 | `client.public_dsar` (PublicDsarAPI) |
| RLS | 3 | 10 | DSAR models have RLS |
| Throttle | 4 | 10 | DSAR views in `_MODULES` (283.3.2.4) |
| Audit | 5 | 10 | DSAR_CREATED, DSAR_COMPLETED events |
| E2E | 6 | 10 | DSAR E2E spec |
| A11y | 7 | 10 | DsarQueue in axe manifest |
| Dark | 8 | 9 | DsarQueue dark-mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on OTP verification failure; public form errors surfaced inline |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/phase232-dsar.md` |
| Metrics | 12 | 10 | `dsar_operations_total` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers DSAR; GA flag docs updated |

### 11. `compliance_breach_enabled` — Score: 128/130 (98)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub breach` group with create/list/notify subcommands |
| SDK | 2 | 10 | `client.breach` module; BreachAPI exposed via phase232 or standalone |
| RLS | 3 | 10 | Breach models have RLS |
| Throttle | 4 | 10 | Breach views in `_MODULES` (283.3.4.4) |
| Audit | 5 | 10 | BREACH_CREATED, BREACH_NOTIFIED events |
| E2E | 6 | 10 | Breach E2E spec with full flow: create → SLA clock → transitions (284.F.4 closes prior gap) |
| A11y | 7 | 10 | BreachDashboard in axe manifest |
| Dark | 8 | 9 | BreachDashboard dark-mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on create/notify failure; SLA clock countdown with deadline indicators |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/RB-COMP-004-breach.md` |
| Metrics | 12 | 10 | `breach_operations_total` |
| Docs | 13 | 9 | PRODUCT_GUIDE covers breach; flag documentation updated |

### 12. `compliance_processor_agreements_enabled` — Score: 114/130 (88)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub processor-agreements` group |
| SDK | 2 | 10 | `client.processor_agreements` (ProcessorAgreementsAPI) |
| RLS | 3 | 10 | ProcessorAgreement models have RLS |
| Throttle | 4 | 10 | PA views in `_MODULES` (283.3.6.4) |
| Audit | 5 | 10 | PROCESSOR_AGREEMENT_CREATED events |
| E2E | 6 | 10 | Processor agreements E2E spec |
| A11y | 7 | 8 | PA routes in axe manifest; full Article 28 flow pending |
| Dark | 8 | 8 | PA pages dark-mode tested; agreement preview pending |
| ErrorUX | 9 | 8 | ErrorDisplay on main flows; agreement preview error path not verified |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 7 | Covered by `phase232-compliance-programme.md`; no dedicated runbook |
| Metrics | 12 | 10 | `processor_agreement_operations_total` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers PA; flag docs incomplete |

### 13. `compliance_retention_enforcer_enabled` — Score: 114/130 (88)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub retention` group |
| SDK | 2 | 10 | `client.retention` (RetentionAPI) |
| RLS | 3 | 10 | Retention models have RLS |
| Throttle | 4 | 10 | Retention views covered |
| Audit | 5 | 10 | RETENTION_SWEEP_COMPLETED events |
| E2E | 6 | 10 | Retention E2E spec |
| A11y | 7 | 8 | Retention list dark-mode tested; policy editor pending |
| Dark | 8 | 8 | Retention pages dark-mode tested |
| ErrorUX | 9 | 8 | ErrorDisplay on sweep failure; policy create/edit error paths not fully verified |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 7 | `file-retention.md` covers file retention only; no dedicated runbook |
| Metrics | 12 | 10 | `retention_sweep_duration_seconds` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers retention; flag docs incomplete |

### 14. `compliance_audit_full_sampling` — Score: 122/130 (94)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub audit` group with events/export subcommands |
| SDK | 2 | 10 | `client.audit` (AuditAPI) |
| RLS | 3 | 10 | Audit models have RLS |
| Throttle | 4 | 10 | Audit views covered |
| Audit | 5 | 10 | FILE_METADATA_VIEWED (full vs sampled) |
| E2E | 6 | 9 | Audit E2E spec; full-sampling toggle needs specific spec |
| A11y | 7 | 10 | Audit routes in axe manifest |
| Dark | 8 | 10 | Audit pages dark-mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on audit query failure; export errors surfaced |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 7 | No dedicated runbook (RB-FLAG-003 created; needs operational content) |
| Metrics | 12 | 10 | `audit_events_total`, `file_metadata_viewed_total` |
| Docs | 13 | 7 | Decision documented (283.6.3); PRODUCT_GUIDE needs update |

### 15. `compliance_intake_gate_enabled` — Score: 127/130 (98)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub compliance` group exercises intake gate paths |
| SDK | 2 | 10 | `client.compliance` (ComplianceAPI) |
| RLS | 3 | 10 | ComplianceRun models have RLS |
| Throttle | 4 | 10 | Intake gate views covered |
| Audit | 5 | 10 | COMPLIANCE_INTAKE_SCAN_ENQUEUED, ACTIVATION_GATE_BLOCK |
| E2E | 6 | 10 | Intake gate E2E spec |
| A11y | 7 | 10 | Intake gate routes in axe manifest |
| Dark | 8 | 10 | Dark mode tested |
| ErrorUX | 9 | 10 | Gate blocked error rendered via ErrorDisplay; scan progress indicator; retry on transient failure |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/compliance-intake-gate.md` |
| Metrics | 12 | 10 | `compliance_intake_gate_events_total` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers intake gate; GA flag docs updated |

### 16. `semantic_memento_enabled` — Score: 116/130 (89)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 7 | `datahub semantic` group exists; no dedicated `memento` subcommand |
| SDK | 2 | 10 | `client.memento` (MementoAPI) with get_version_at_time/list_versions/compare_versions |
| RLS | 3 | 10 | Memento models have RLS |
| Throttle | 4 | 10 | Semantic views covered |
| Audit | 5 | 10 | MEMENTO_SNAPSHOT_CREATED |
| E2E | 6 | 9 | Semantic E2E; memento-specific path needs spec |
| A11y | 7 | 10 | Semantic routes in axe manifest |
| Dark | 8 | 8 | Semantic pages dark-mode tested; datetime picker pending |
| ErrorUX | 9 | 9 | ErrorDisplay on version retrieval failure; TimeMap 404 handled gracefully |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/semantic-memento.md` |
| Metrics | 12 | 7 | Semantic metrics exist; no memento-specific counter |
| Docs | 13 | 6 | PRODUCT_GUIDE §19 covers semantic; flag docs incomplete |

### 17. `semantic_inference_enabled` — Score: 116/130 (89)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 7 | `datahub semantic` group exists; no dedicated `inference` subcommand |
| SDK | 2 | 10 | `client.semantic_inference` (SemanticInferenceAPI) with list_inference_rules/validate_inference_rule/get_inferred_triples |
| RLS | 3 | 10 | Inference models have RLS |
| Throttle | 4 | 10 | Semantic views covered |
| Audit | 5 | 10 | INFERENCE_EXECUTED |
| E2E | 6 | 9 | Semantic E2E; inference-specific path needs spec |
| A11y | 7 | 10 | Semantic routes in axe manifest |
| Dark | 8 | 8 | Semantic pages dark-mode tested |
| ErrorUX | 9 | 9 | ErrorDisplay on SPARQL inference failure; timeout surfaced |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/semantic-inference.md` |
| Metrics | 12 | 7 | Semantic metrics exist; no inference-specific counter |
| Docs | 13 | 6 | PRODUCT_GUIDE §19 covers semantic; flag docs incomplete |

### 18. `semantic_custom_ontology_enabled` — Score: 123/130 (95)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub semantic custom-ontology` group with upload/list/activate/deactivate |
| SDK | 2 | 10 | `client.semantic` (SemanticAPI) with upload_custom_ontology/list_custom_ontologies/activate_ontology/deactivate_ontology |
| RLS | 3 | 10 | Ontology models have RLS |
| Throttle | 4 | 10 | Semantic views covered |
| Audit | 5 | 10 | ONTOLOGY_UPLOADED |
| E2E | 6 | 9 | Semantic E2E; ontology upload spec exists (custom-ontology.spec.ts) |
| A11y | 7 | 10 | Semantic routes in axe manifest; ontology manager audited (283.4.1.3) |
| Dark | 8 | 8 | Semantic pages dark-mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on upload validation failure; namespace conflict surfaced inline |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/semantic-ontology.md` |
| Metrics | 12 | 7 | Semantic metrics exist; no ontology-specific counter |
| Docs | 13 | 9 | PRODUCT_GUIDE + ontology docs updated; flag docs recently improved |

### 19. `semantic_ldn_enabled` — Score: 123/130 (95)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub semantic ldn` group with inbox-list/subscribe/unsubscribe |
| SDK | 2 | 10 | `client.semantic` with ldn_list_inbox/ldn_subscribe/ldn_unsubscribe |
| RLS | 3 | 10 | LDN models have RLS |
| Throttle | 4 | 10 | Semantic views covered |
| Audit | 5 | 10 | LDN_NOTIFICATION_RECEIVED |
| E2E | 6 | 9 | Semantic E2E; LDN-specific spec exists (ldn-inbox.spec.ts) |
| A11y | 7 | 10 | LDN settings audited in axe manifest (283.4.1.3) |
| Dark | 8 | 8 | Semantic pages dark-mode tested |
| ErrorUX | 9 | 10 | ErrorDisplay on subscription failure; inbox fetch errors surfaced |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 10 | `docs/runbooks/semantic-ldn.md` |
| Metrics | 12 | 7 | Semantic metrics exist; no LDN-specific counter |
| Docs | 13 | 9 | PRODUCT_GUIDE + LDN docs updated |

### 20. `trust_signals_enabled` — Score: 104/130 (80)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 5 | No dedicated `trust-signals` CLI; marketplace commands touch trust signal data tangentially |
| SDK | 2 | 5 | No dedicated TrustSignalsAPI; marketplace SDK modules include trust signal data in listings |
| RLS | 3 | 10 | Trust signal models have RLS |
| Throttle | 4 | 10 | Catalogue views covered |
| Audit | 5 | 10 | TRUST_SIGNAL_COMPUTED events |
| E2E | 6 | 10 | Catalogue E2E spec |
| A11y | 7 | 8 | Catalogue routes in axe manifest; badge tooltips pending |
| Dark | 8 | 8 | Catalogue dark-mode tested; badge contrast verification pending |
| ErrorUX | 9 | 7 | Trust signal computation failure silently degrades (badges absent); no user-facing error |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 5 | No operational runbook (RB-FLAG-001 created; needs operational content) |
| Metrics | 12 | 10 | `trust_signal_computation_duration_seconds` |
| Docs | 13 | 6 | PRODUCT_GUIDE covers trust signals; flag not documented |

### 21. `versioning_enabled` — Score: 114/130 (88)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub versioning` group with list/get/diff/rollback (283.6.2) |
| SDK | 2 | 10 | `client.versioning` (VersioningAPI) |
| RLS | 3 | 10 | Version models have RLS |
| Throttle | 4 | 10 | Version views covered |
| Audit | 5 | 10 | VERSION_CREATED, VERSION_COMPARED |
| E2E | 6 | 9 | Version E2E spec; diff/rollback paths need spec |
| A11y | 7 | 8 | Version pages in axe manifest; diff viewer pending |
| Dark | 8 | 8 | Version pages dark-mode tested; diff viewer pending |
| ErrorUX | 9 | 9 | ErrorDisplay on version conflict; rollback confirmation dialog |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 5 | `dataset-version-compare-failure.md` covers one path only (RB-FLAG-008 created) |
| Metrics | 12 | 10 | `version_operations_total` |
| Docs | 13 | 7 | PRODUCT_GUIDE covers versioning; flag docs incomplete |

### 22. `workflows_enabled` — Score: 115/130 (88)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 7 | No dedicated `workflows` CLI group; `scheduled-ingestion`/`scheduled-export`/`transformation` exercise adjacent workflow paths |
| SDK | 2 | 10 | `client.workflows` (WorkflowsAPI) |
| RLS | 3 | 10 | Workflow models have RLS |
| Throttle | 4 | 10 | Workflow views covered |
| Audit | 5 | 10 | WORKFLOW_EXECUTED events |
| E2E | 6 | 9 | Workflow E2E spec; SDK workflow path needs spec |
| A11y | 7 | 8 | Workflow pages in axe manifest; builder canvas pending |
| Dark | 8 | 8 | Workflow pages dark-mode tested |
| ErrorUX | 9 | 9 | ErrorDisplay on workflow failure; stuck-workflow banner; retry on transient failure |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 5 | `workflow-dr.md` + `workflow-stuck.md` exist; no dedicated flag runbook (RB-FLAG-002 created) |
| Metrics | 12 | 10 | `workflow_execution_duration_seconds` |
| Docs | 13 | 9 | PRODUCT_GUIDE covers workflows; flag docs recently updated |

### 23. `federated_import_enabled` — Score: 124/130 (95)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub federated-import` group with providers/import subcommands (284.A.4) |
| SDK | 2 | 10 | `client.federated_import` (FederatedImportAPI) with list_providers/create_import_job/get_import_status/cancel_import (284.A.3) |
| RLS | 3 | 10 | FederatedImport models have tenant_id + RLS; cross-region consent gate enforced |
| Throttle | 4 | 10 | FederatedImportViewSet covered in `_MODULES` (284.A.10) |
| Audit | 5 | 10 | FEDERATED_IMPORT_CREATED, FEDERATED_IMPORT_COMPLETED events |
| E2E | 6 | 10 | `frontend/e2e/journeys/federated-import.spec.ts` (284.A.6) |
| A11y | 7 | 10 | FederatedImportPage in axe manifest (284.A.7) |
| Dark | 8 | 9 | Dark mode tested (284.A.7) |
| ErrorUX | 9 | 10 | ErrorDisplay on import failure; credential_ref validation errors surfaced inline |
| i18n | 10 | 10 | All strings in en.ts (284.A.5) |
| Runbook | 11 | 10 | `docs/runbooks/RB-COMP-006-federated-import.md` (284.A.8) |
| Metrics | 12 | 8 | Federated import metrics exist; no flag-specific counter |
| Docs | 13 | 7 | PRODUCT_GUIDE updated; flag documented (284.A.11) |

### 24. `asset_auto_activate_on_gate_pass` — Score: 120/130 (92)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub assets` group exercises asset activation paths |
| SDK | 2 | 10 | `client.assets` (AssetsAPI) |
| RLS | 3 | 10 | Asset models have RLS |
| Throttle | 4 | 10 | Asset views covered |
| Audit | 5 | 10 | ASSET_AUTO_ACTIVATED, ACTIVATION_GATE_PASS events |
| E2E | 6 | 9 | Asset creation E2E covers activation; no dedicated auto-activate spec |
| A11y | 7 | 10 | Asset routes in axe manifest |
| Dark | 8 | 10 | Asset pages dark-mode tested |
| ErrorUX | 9 | 10 | Activation status surfaced in asset detail; gate failure rendered via ErrorDisplay |
| i18n | 10 | 10 | All in en.ts |
| Runbook | 11 | 7 | Covered by `asset-creation.md`; no dedicated auto-activate runbook |
| Metrics | 12 | 8 | Asset metrics exist; no auto-activate-specific counter |
| Docs | 13 | 6 | Covered in PRODUCT_GUIDE asset section; flag not individually documented |

### 25. `semantic_graphql_ld_enabled` — Score: 122/130 (94)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 10 | `datahub semantic graphql query` subcommand with --query/--file/--variables/--format (284.B.3) |
| SDK | 2 | 10 | `client.semantic.execute_graphql_ld(query, variables)` method (284.B.3) |
| RLS | 3 | 10 | Resolvers use server-set `info.context.tenant_id`; cross-tenant → null (no 404 leak) |
| Throttle | 4 | 10 | SemanticGraphQLThrottle (60 q/min/user); covered in `check_throttle_coverage.py` (284.B.2) |
| Audit | 5 | 10 | SEMANTIC_GRAPHQL_QUERY for every outcome (SUCCESS/DEPTH/COMPLEXITY/TIMEOUT/SYNTAX/EXECUTION/THROTTLED); SHA-256 hash only |
| E2E | 6 | 10 | `graphql-ld.spec.ts` — 6 tests: deep-link, tab, syntax error, depth error, textarea input, dark mode (284.B.4) |
| A11y | 7 | 10 | GraphQL playground in axe manifest (284.B.5) |
| Dark | 8 | 9 | Dark mode tested with Phase 282 palette verification (284.B.4) |
| ErrorUX | 9 | 10 | ErrorDisplay on syntax/depth/complexity/timeout/403/throttle; every error path has user-facing code+message |
| i18n | 10 | 7 | Playground component has hardcoded English strings ("Running…", "Run", "Response", "Click Run to execute"); no en.ts entries |
| Runbook | 11 | 10 | `docs/runbooks/RB-SEM-001-graphql-ld.md` — triage matrix, audit SQL, complexity troubleshooting (284.B.6) |
| Metrics | 12 | 7 | SEMANTIC_GRAPHQL_QUERY audit rows carry outcome + response_time_ms; no Prometheus counter for GQL operations |
| Docs | 13 | 9 | Runbook + API reference complete; flag documented in registry + tasks.md |

### 26. `semantic_search_enabled` — Score: 116/130 (89)

| Gate | # | Score | Notes |
|------|---|-------|-------|
| CLI | 1 | 7 | `datahub semantic` group exists; no dedicated `semantic search` subcommand |
| SDK | 2 | 10 | `client.search` (SearchAPI) |
| RLS | 3 | 10 | Search models have RLS |
| Throttle | 4 | 10 | Search views covered |
| Audit | 5 | 10 | SEARCH_PERFORMED, SEARCH_RATE_LIMIT_EXCEEDED events |
| E2E | 6 | 10 | `semantic-search.spec.ts` — keyword search → facets → filter (284.D.3) |
| A11y | 7 | 10 | Semantic search facets in axe manifest (284.D.4) |
| Dark | 8 | 9 | Dark mode tested with facets active |
| ErrorUX | 9 | 10 | ErrorDisplay on SPARQL timeout; RetryButton on transient errors (284.D.1) |
| i18n | 10 | 10 | All facet strings in en.ts (284.D.1) |
| Runbook | 11 | 5 | No dedicated runbook; covered generically by search runbook |
| Metrics | 12 | 8 | Search metrics exist (search_request_duration_seconds); no semantic-search-specific counter |
| Docs | 13 | 7 | PRODUCT_GUIDE updated (284.D.4); flag documentation incomplete |

## Aggregate Summary (13-Gate Unified)

| Metric | Value |
|--------|-------|
| Total GA flags | 26 |
| Mean score (130-pt scale) | 119.8 |
| Mean score (normalized 100-pt) | 92.2 |
| Median score (130-pt) | 120 |
| Median score (normalized 100-pt) | 92 |
| Flags ≥95 (normalized) | 12 (46.2%) |
| Flags ≥90 (normalized) | 20 (76.9%) |
| Flags ≥70 (normalized) | 26 (100%) |
| Flags <70 (normalized) | 0 |

### Score Distribution (Normalized 100-pt)

| Range | Count | Flags |
|-------|-------|-------|
| 95–100 | 12 | compliance_fail_closed (98), compliance_dpia (98), compliance_breach (98), compliance_intake_gate (98), compliance_dsar (97), compliance_ropa (96), asset_creation (95), semantic_custom_ontology (95), semantic_ldn (95), federated_import (95) |
| 90–94 | 8 | data_quality (94), data_quality_advanced (94), compliance_audit_full_sampling (94), semantic_graphql_ld (94), asset_auto_activate (92), datasets (91), files (91) |
| 85–89 | 6 | semantic_memento (89), semantic_inference (89), semantic_search (89), compliance_consent (86), versioning (88), workflows (88) |
| 80–84 | 1 | trust_signals (80) |
| <70 | 0 | — |

## Gate-by-Gate Aggregate

| # | Gate | Mean Score | Flags at 10 | Flags at 7+ | Flags <5 |
|---|------|-----------|-------------|-------------|----------|
| 1 | CLI | 9.0 | 20 | 26 | 0 |
| 2 | SDK | 9.4 | 23 | 26 | 0 |
| 3 | RLS | 10.0 | 26 | 26 | 0 |
| 4 | Throttle | 10.0 | 26 | 26 | 0 |
| 5 | Audit | 10.0 | 26 | 26 | 0 |
| 6 | E2E | 9.6 | 18 | 26 | 0 |
| 7 | A11y | 9.5 | 21 | 26 | 0 |
| 8 | Dark | 8.8 | 10 | 26 | 0 |
| 9 | ErrorUX | 9.4 | 19 | 26 | 0 |
| 10 | i18n | 9.9 | 25 | 26 | 0 |
| 11 | Runbook | 8.3 | 16 | 21 | 0 |
| 12 | Metrics | 9.3 | 19 | 26 | 0 |
| 13 | Docs | 7.0 | 2 | 17 | 0 |

**Strongest gates**: RLS, Throttle, Audit (all 10.0 mean — universal coverage)
**Weakest gates**: Docs (7.0), Runbook (8.3), Dark (8.8)

## Gap Closure Plan (Phase 285 Unified)

### Flags at 80–89 (require gap closure to reach ≥95)

#### `trust_signals_enabled` (80 → 95 target)
- **CLI gap (5)**: Create `datahub trust-signals` CLI group with compute/list subcommands
- **SDK gap (5)**: Create `TrustSignalsAPI` SDK module
- **ErrorUX gap (7)**: Add ErrorDisplay when trust signal computation fails (currently silent degrade)
- **Runbook gap (5)**: Complete RB-FLAG-001 with operational content
- **Dark gap (8)**: Verify badge contrast in dark palette
- **Target:** ≥95 within 60 days

#### `compliance_consent_enabled` (86 → 95 target)
- **CLI gap (5)**: Create `datahub consent` CLI group with grant/withdraw/list subcommands
- **SDK gap (5)**: Create `ConsentAPI` SDK module
- **Target:** ≥95 within 45 days

#### `versioning_enabled` (88 → 95 target)
- **E2E gap (9)**: Add diff/rollback E2E paths
- **A11y gap (8)**: Add diff viewer to axe manifest
- **Dark gap (8)**: Verify diff viewer in dark palette
- **Runbook gap (5)**: Complete RB-FLAG-008 with operational content
- **Target:** ≥95 within 30 days

#### `workflows_enabled` (88 → 95 target)
- **CLI gap (7)**: Create `datahub workflows` CLI group
- **E2E gap (9)**: Add SDK workflow E2E path
- **A11y gap (8)**: Add builder canvas to axe manifest
- **Runbook gap (5)**: Complete RB-FLAG-002 with operational content
- **Target:** ≥95 within 45 days

#### `semantic_memento_enabled` (89 → 95 target)
- **CLI gap (7)**: Add `datahub semantic memento` subcommand with list/get/diff
- **E2E gap (9)**: Add memento-specific E2E spec
- **Dark gap (8)**: Verify datetime picker in dark palette
- **Metrics gap (7)**: Add `memento_snapshot_operations_total` counter
- **Target:** ≥95 within 30 days

#### `semantic_inference_enabled` (89 → 95 target)
- **CLI gap (7)**: Add `datahub semantic inference` subcommand
- **E2E gap (9)**: Add inference-specific E2E spec
- **Dark gap (8)**: Verify inference results in dark palette
- **Metrics gap (7)**: Add `inference_execution_duration_seconds` counter
- **Target:** ≥95 within 30 days

#### `semantic_search_enabled` (89 → 95 target)
- **CLI gap (7)**: Add `datahub semantic search` subcommand
- **Dark gap (9)**: Verify facet rendering in dark palette
- **Runbook gap (5)**: Create dedicated semantic-search runbook
- **Metrics gap (8)**: Add semantic-search-specific metrics counter
- **Target:** ≥95 within 45 days

### Flags at 90–94 (minor gap closure)

All 6 flags in the 90–94 band share one primary gap:
- **Docs (G13)**: PRODUCT_GUIDE flag documentation for 5 flags (data_quality ×2, datasets, files, audit_full_sampling)
- **Runbook (G11)**: datasets and files need dedicated operational runbooks
- **E2E (G6)**: audit_full_sampling toggle needs specific E2E spec

## Phase 285.1 Reconciliation Summary

| Metric | Pre-285.1 (10-gate) | Post-285.1 (13-gate) | Delta |
|--------|---------------------|----------------------|-------|
| Gates | 10 | 13 | +3 (CLI, SDK, ErrorUX) |
| Total GA flags | 22 | 26 | +4 (284.A/B/C/D promotions) |
| Mean score | 91.7 | 92.2 | +0.5 |
| Median score | 92 | 92 | — |
| Flags ≥95 | 5 (22.7%) | 12 (46.2%) | +7 |
| Flags ≥90 | 20 (90.9%) | 20 (76.9%) | — (stricter rubric, more flags) |
| Flags ≥70 | 22 (100%) | 26 (100%) | — |
| Lowest score | 86 (trust_signals) | 80 (trust_signals) | −6 (CLI+SDK gaps exposed) |
| Highest score | 96 (×3 flags) | 98 (×4 flags) | +2 |

The 13-gate rubric reveals previously invisible gaps: CLI coverage for consent/trust_signals/semantic_search, SDK coverage for consent/trust_signals, Error UX gaps for features that silently degrade, and i18n gaps (semantic_graphql_ld has hardcoded English strings). These are real operational gaps that the 10-gate rubric didn't measure. The 4 additional GA flags (federated_import, asset_auto_activate, semantic_graphql_ld, semantic_search) were promoted after the original 22-flag audit baseline and are now integrated into the unified scoring.

## Maintenance

- **Owner:** Platform Engineering
- **Next audit:** 2026-08-16 (quarterly)
- **Review triggers:** After any flag stage promotion, after SEV1 incident involving flag-gated feature
- **13-gate scoring script:** `scripts/check_ga_gate_scores.py` (Phase 283.6.6) — updated to include CLI/SDK/ErrorUX gates in Phase 286
