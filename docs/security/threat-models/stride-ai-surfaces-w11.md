# STRIDE Threat Model — AI Surfaces (W11)

One-pager for the oss-release-remediation W11.12 surface (paid layer —
private-repo scope, per register row 19 and decision D5): the natural-
language search + schema-matching endpoints (`hub/apps/ai`), the ML
inference predict paths (`hub/apps/ml`), the LLM provider client, and the
agent/tool boundary review. Every mitigation cites its verifying test or
gate (P4). Ledger:
`docs/audits/w1112-ai-surface-threat-model-2026-10-16.md`; red-team matrix:
`docs/security/adversarial-matrices/w1112-ai-prompt-injection-matrix.md`.

## Scope / assets

- NL query → LLM interpretation → tenant-scoped search across assets,
  contracts, datasets (`AIViewSet.natural_language_search`).
- Source/target schema dicts → LLM field mapping (`AIViewSet.schema_matching`)
  — the two-party surface: an external partner's source schema steers the
  mapping of the tenant's target schema.
- ML predict paths (`MLModelViewSet.predict`, `InferenceViewSet.predict`)
  forwarding model input to the ODH Inference Scheduler.
- The LLM provider client (OpenAI-format chat completions, dormant by
  default — `LLM_API_KEY` unset → rule-based fallback).
- The audit trail of every AI/ML execution (forensic substrate).

## Trust boundaries

- Tenant → AI API (authenticated, per-tenant throttled).
- AI API → external LLM provider (API key over TLS only).
- AI API → ODH Inference Scheduler (internal, plain HTTP on the cluster
  network).
- Model output → search/serialization/response path (never trusted).
- Frontend rendering of model-derived text (React-escaped).

## Spoofing

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Provider responses forged by a coerced model (instruction-following JSON, foreign filters) | Strict output validation against the response contract; ANY violation fails closed to the rule-based fallback | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Client-supplied deployment_id impersonating another deployment's path | Slug-shaped identifier validation before the ODH URL interpolation | hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py |

## Tampering

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Prompt injection via query text or schema field names/descriptions (LLM01) | Deterministic detector before prompt construction (fail closed, audited) + per-call tokenized delimiters + data-only framing in both prompt builders + hardened system prompt | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Malicious external source schema steering the tenant's field mappings | Detector on both schemas; model matches must reference fields that EXIST in the caller's schemas — hallucinated mappings fall back to the rule-based matcher | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Arbitrary-sized schema dicts inflating the prompt (token/cost abuse) | 64 KiB serializer cap — reject, never truncate | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Unbounded model input forwarded to ODH | 64 KiB bound on both predict paths before the client is called | hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py |
| Operator-set non-TLS provider URL exfiltrating the API key | Client init fails closed (key disabled) on non-https `LLM_API_URL` | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |

## Repudiation

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Injection attempts and AI/ML executions leave no forensic trail | `AI_PROMPT_INJECTION_BLOCKED`, `AI_NATURAL_LANGUAGE_SEARCH_PERFORMED`, `AI_SCHEMA_MATCHING_PERFORMED`, `ML_PREDICTION_PERFORMED` audit events (best-effort, the Phase 273 pattern) | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Rate-limit exhaustion unprovable | Per-tenant AI/ML throttles with 429 audit events (pre-existing) | hub/apps/ai/throttles.py |

## Information disclosure

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| ODH/LLM third-party exception text (connection strings, credentials, URLs) echoed to clients (the W11.6 class) | All 16 `{e!s}` interpolations + the training-list `str(e)` row removed; ODH branches classify by error shape through one helper — generic details only, exceptions logged server-side | hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py |
| Coerced model output escaping tenant scope | `tenant_id` is never read from model output; querysets are tenant-scoped at the view; the normalized shape drops foreign keys | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Cross-tenant cache reuse of LLM interpretations | Tenant-bound cache keys (view key includes tenant_id; client key includes the tenant context) | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Model-derived text XSS via the frontend | React-escaped rendering (no dangerouslySetInnerHTML on the AI pages) | frontend/src/features/ai/components/SchemaMatchingPage.tsx |

## Denial of service

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Provider outage cascading into the request path | Circuit breaker + retry on the LLM client and ODH client; every failure degrades to the rule-based fallback | hub/apps/ai/tests/test_llm_client.py |
| Injection payloads exhausting the provider quota | Blocked payloads never reach the provider (ZERO-call pins) | hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py |
| Tenant flooding the AI/ML surfaces | AITenantThrottle (30/min), MLTenantThrottle, MLInferenceThrottle (600/hr) — per-tenant keys | hub/apps/ai/throttles.py |

## Elevation of privilege

| Threat | Mitigation (shipped) | Verified by |
|---|---|---|
| Model output gaining agency (tool calls, API access — LLM06) | ABSENCE proven: the veracity pin AST-scans the non-test tree for agentic-framework imports and tool-call sites — zero; the AI surfaces are prompt-only, the system prompt grants no functions | scripts/tests/test_w1112_ai_threat_model_veracity.py |
| Programming errors masquerading as ODH outages (the `ODHClientError = Exception` fallback) | Private fallback classes + shape-based classification — only ODH-shaped errors map to 503/404; real bugs keep their 500 | hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py |
| ML flag/scope bypass on the predict paths | `ml_enabled` gate + `ml:write` scope + tenant-scoped querysets (pre-existing) | hub/apps/ml/tests/test_views.py |

## Open threats (not yet shipped — documented, not claimed)

- The live LLM path is dormant by default and its settings surface
  (`LLM_API_KEY`/`LLM_API_URL`/`LLM_MODEL`) is undocumented in the env
  templates — recorded in the matrix OPEN-THREATS with the guardrail
  checklist for enablement.
- Both live predict endpoints bypass `run_inference` (plan limits,
  contract validation, entitlements, `ModelInference` rows) — a follow-up
  lane.
- `deployments/predict` has no tenant-ownership check on the
  client-supplied `deployment_id` (slug-validated; ODH-side authorization
  is the remaining boundary).
- The deterministic detector is the committed baseline layer; provider-side
  guardrails remain an ops choice for the paid-layer deployment.
