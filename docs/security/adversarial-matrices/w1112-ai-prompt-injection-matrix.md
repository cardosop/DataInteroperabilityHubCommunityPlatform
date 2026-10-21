# W11.12 — AI-Surface Prompt-Injection Red-Team Matrix

**Change:** `openspec/changes/oss-release-remediation` — W11.12
**Date:** 2026-10-16
**Register rows closed:** 19 (AI-surface risks — prompt injection, excessive
agency)
**OWASP LLM Top 10 mapping:** LLM01 (prompt injection), LLM02 (insecure
output handling), LLM06 (excessive agency).
**Scope note (paid layer):** the AI/ML surfaces (`hub/apps/ai`,
`hub/apps/ml`) are paid-layer apps (Phase 313.1 `paid_urls`); the threat
model, this matrix and the suites are committed to the public tree with
the scoping note per decision D5 — the public tree does not advertise the
paid-layer surface as shipped, but the verification artifacts travel with
it. The LLM live path is dormant by default (`LLM_API_KEY` unset — every
call takes the rule-based fallback); every cell below is pinned against
the REAL client/view code, so the defenses bite the moment an operator
wires a provider key.

Every cell carries ONE named test. Cells are verified mechanically by
`scripts/tests/test_w1112_ai_threat_model_veracity.py` — a cited test that
does not resolve on disk flips the pin RED. The third-party-boundary seam
(the W11.7 `_StubStripeRefund` pattern): the LLM provider HTTP transport
and the ODH inference client are scripted; the code under test is never
mocked.

## Matrix M1 — LLM01 input gates (the deterministic detector)

| # | Attack class | Named test | Expected |
|---|---|---|---|
| 1.1 | Instruction-override corpus (OWASP LLM01 payloads: ignore/disregard/forget, role-switch, jailbreak, JSON smuggling) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptInjectionDetector::test_instruction_override_payload_corpus_blocked` | every payload → `InjectionVerdict(blocked=True)` |
| 1.2 | Delimiter breakout (`</user_query>`, `[SYSTEM]`, `### System`) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptInjectionDetector::test_delimiter_breakout_payloads_blocked` | every payload blocked |
| 1.3 | Benign-corpus anti-false-positive ratchet (12 realistic queries) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptInjectionDetector::test_benign_query_corpus_passes` | every query passes (fail-closed degradation, never denial) |
| 1.4 | Benign schema fields pass | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptInjectionDetector::test_benign_schema_fields_pass` | passes |
| 1.5 | Schema field-name + description injection (the two-party surface: an external source schema steering the tenant's mappings) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptInjectionDetector::test_schema_injection_in_field_names_and_descriptions_blocked` | blocked |

## Matrix M2 — LLM01 prompt construction (delimiters + framing)

| # | Attack class | Named test | Expected |
|---|---|---|---|
| 2.1 | Per-call unpredictable delimiters + data-only framing | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_query_wrapped_in_unpredictable_delimiters_with_data_only_framing` | `<user_query_<32-hex>>` pair + "untrusted" framing |
| 2.2 | Static attacker close-tag is inert data | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_attacker_close_tag_is_inert_data_inside_the_delimited_block` | the attacker's `</user_query>` sits inside the data block; the real terminator carries the token |
| 2.3 | Schema prompt delimiter separation | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_schema_prompt_delimiters_separate_data_blocks` | both schemas wrapped in tokenized delimiters |
| 2.4 | Hardened system prompt | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_system_prompt_marks_user_content_untrusted` | provider request carries the data-only system framing |
| 2.5 | Detected payload never reaches the provider | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_injection_query_never_reaches_the_provider` | ZERO provider calls + rule-based fallback cached |
| 2.6 | Non-TLS provider URL fails closed | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestPromptHardening::test_http_provider_url_fails_closed_to_rule_based` | `http://` URL → API key disabled, no call |

## Matrix M3 — LLM02 adversarial model output (strict validation)

| # | Attack class | Named test | Expected |
|---|---|---|---|
| 3.1 | Coerced model emits foreign filter keys (`tenant_id`, junk) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_model_output_with_hallucinated_keys_is_normalized` | foreign keys dropped; only contract keys remain |
| 3.2 | Invalid intent (`drop_tables`) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_invalid_intent_fails_closed_to_rule_based` | rule-based fallback, never echoed |
| 3.3 | Multiple JSON objects / prose-wrapped JSON | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_multiple_json_objects_take_the_first_balanced_object` | first balanced object, greedy-regex class dead |
| 3.4 | Unbalanced JSON | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_unbalanced_json_fails_closed` | fallback |
| 3.5 | Entity flooding / non-string entities | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_entities_are_bounded_and_string_only` | bounded to 10; non-string → fallback |
| 3.6 | Matches outside the caller's schemas (hallucinated mappings) | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_schema_matching_rejects_matches_outside_the_schemas` | fallback to the rule-based matcher |
| 3.7 | Confidence out-of-range / match_type not whitelisted | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_confidence_clamped_and_match_type_whitelisted` | clamped to [0,1]; invalid type → fallback |
| 3.8 | Injected schema never reaches the provider | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestOutputValidation::test_schema_injection_never_reaches_the_provider` | ZERO provider calls + rule-based result |

## Matrix M4 — view-level cells (real DRF stack, real DB, real audit rows)

| # | Attack class | Named test | Expected |
|---|---|---|---|
| 4.1 | NL-search injection fails closed with forensic trail | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_nl_search_injection_query_fails_closed_with_audits` | 200 rule-based interpretation + `AI_PROMPT_INJECTION_BLOCKED` + `AI_NATURAL_LANGUAGE_SEARCH_PERFORMED` audit rows; ZERO provider calls |
| 4.2 | Coerced model output cannot escape tenant scope | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_adversarial_model_output_cannot_escape_tenant_scope` | `tenant_id` filter dropped; only caller-tenant rows returned |
| 4.3 | Schema-matching injection blocked + audited | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_schema_matching_injection_blocked_with_audits` | `AI_PROMPT_INJECTION_BLOCKED` + `AI_SCHEMA_MATCHING_PERFORMED`; ZERO provider calls |
| 4.4 | Oversized schema rejected | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_oversized_schema_rejected` | 400 (the pre-fix surface fed arbitrary-sized dicts into the prompt) |
| 4.5 | Benign NL search audited | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_benign_nl_search_emits_performed_audit` | `AI_NATURAL_LANGUAGE_SEARCH_PERFORMED` row |
| 4.6 | Tenant-bound cache keys | `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py::TestAIViewRedTeam::test_nl_search_cache_is_tenant_bound` | tenant B's identical query re-runs the provider (no cross-tenant cache reuse) |

## Matrix M5 — ML-inference boundary cells

| # | Attack class | Named test | Expected |
|---|---|---|---|
| 5.1 | ODH exception text (connection strings/credentials) never reaches the client | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_odh_error_details_never_reach_the_client` | 503 generic detail, secret absent (the pre-fix `{e!s}` echo — the W11.6 class) |
| 5.2 | Unexpected prediction failure is generic | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_unexpected_prediction_failure_is_generic` | 500 generic detail (the pre-fix `ODHClientError = Exception` fallback classified every programming error as an ODH outage) |
| 5.3 | Oversized model input rejected | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_oversized_input_rejected` | 400 + ZERO ODH calls (the pre-fix path forwarded arbitrary-sized `input` to the scheduler) |
| 5.4 | Prediction success audited | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_prediction_success_emits_audit` | `ML_PREDICTION_PERFORMED` row |
| 5.5 | Benign prediction still reaches ODH (positive control) | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLPredictBoundaries::test_benign_prediction_still_reaches_odh` | one ODH call, hub model UUID as deployment id |
| 5.6 | Client-supplied `deployment_id` validated before URL interpolation | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLDeploymentPredictBoundaries::test_deployment_id_path_segment_validated` | traversal/whitespace shapes → 400 + ZERO ODH calls; slug shape passes |
| 5.7 | Retrieve failure is generic | `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py::TestMLDeploymentPredictBoundaries::test_get_deployment_failure_is_generic` | 503 generic, secret absent |

## Root fixes shipped by this suite (TDD, RED-first)

1. **No prompt-injection defense existed anywhere** (grep-proven). New
   deterministic detector `hub/apps/ai/prompt_injection.py` (instruction
   overrides, prompt exfiltration, delimiter breakout, JSON smuggling —
   conservative: a false positive degrades to the rule-based fallback,
   never denies service). The RED phase caught two corpus gaps
   (`pretend you are …`, `disregard … rules`) — the corpus is the
   anti-regression ratchet.
2. **Raw interpolation into prompts** (`Query: "{query}"`, raw
   `json.dumps(schema)`) — now per-call tokenized delimiters + data-only
   framing in both prompt builders, and the hardened system prompt.
3. **Greedy `\{.*\}` output parsing + zero shape validation** (LLM02) —
   balanced-brace extraction + strict validators for the query
   interpretation (allowed intents, bounded entities, allowed filter keys,
   ISO dates) and the schema matching (matches must reference fields that
   EXIST in the caller's schemas; confidence clamped; match_type
   whitelisted). Any violation fails closed to the rule-based fallback.
4. **Schema size cap** — `SchemaMatchingRequestSerializer` rejects
   schemas > 64 KiB (the pre-fix surface accepted arbitrary-sized dicts
   into the prompt).
5. **Non-TLS `LLM_API_URL`** now disables the live path at client init
   (the API key is never sent over plaintext).
6. **No audit trail on the AI/ML surfaces** — new
   `AI_NATURAL_LANGUAGE_SEARCH_PERFORMED`, `AI_SCHEMA_MATCHING_PERFORMED`,
   `AI_PROMPT_INJECTION_BLOCKED`, `ML_PREDICTION_PERFORMED` events
   (best-effort, the Phase 273 pattern).
7. **ML predict error-echo leaks** — all 16 `{e!s}` interpolations + the
   training-list `str(e)` row removed from `hub/apps/ml/views.py`; the
   ODH branches now classify by error SHAPE (`_is_odh_error`) through one
   helper (`_odh_error_response`) — the pre-fix `ODHClientError =
   Exception` fallback (the hyphenated package dir makes the import
   always fail) classified every programming error as an ODH outage AND
   let real ODH errors (file-path-loaded class) fall through to the
   generic 500.
8. **Unbounded ML predict input** — 64 KiB bound on both predict paths,
   rejected before the ODH client is called.
9. **Unvalidated `deployment_id`** — slug-shaped only (the client-
   supplied value is interpolated into the ODH URL path).
10. **Agent/tool boundary ABSENCE proven** — the veracity pin AST-scans
    the non-test tree for agentic-framework imports and tool-call sites:
    zero. The AI surfaces are prompt-only (LLM06 excessive agency has no
    tool substrate to exploit).

## OPEN-THREATS (recorded, not claimed fixed)

* **The LLM live path is undocumented in settings/env templates** —
  `LLM_API_KEY`/`LLM_API_URL`/`LLM_MODEL` are not declared in
  `hub/settings.py` or `.env*.template`; an operator enabling the path
  should get a documented guardrail config (key source, provider allowlist,
  the W11.12 defenses activation note).
* **Both live predict endpoints bypass `run_inference`** — plan limits,
  contract input validation, entitlement checks and `ModelInference`
  audit rows are skipped on the API path (only the workflow path runs
  them). Recorded for a follow-up lane; the W11.12 bounds close the
  abuse surface until then.
* **Cross-tenant deployment predict ownership** — `deployments/predict`
  trusts the client-supplied `deployment_id` (now slug-validated) with no
  tenant-ownership check; the ODH-side authorization is the remaining
  boundary.
* **`ModelInference` rows persist raw input/output JSON** — retention and
  PII scope for stored model I/O is undecided.
* **`ai-agent` marketplace contracts store third-party `api_key` +
  `endpoint` verbatim** — no invocation path exists (proven by the
  agent/tool absence pin); the storage itself is a confidentiality
  surface for the marketplace lane.
* **Detector false positives degrade, never deny** — a flagged benign
  query still gets the rule-based interpretation; this tradeoff is
  deliberate (documented in `prompt_injection.py`).
* **The deterministic detector is one layer** — for a tenant with
  adversarial partners, the paid-layer deployment should add provider-side
  moderation/guardrails on top; the in-code layer is the committed
  baseline.
