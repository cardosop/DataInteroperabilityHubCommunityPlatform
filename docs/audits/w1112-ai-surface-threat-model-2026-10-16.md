# W11.12 — AI-Surface Threat Model + Red-Team Ledger (2026-10-16)

Claim-to-verification ledger for the W11.12 lane (register row 19 — AI
surface risks; paid layer — private-repo scope). Threat model:
`docs/security/threat-models/stride-ai-surfaces-w11.md`; red-team matrix:
`docs/security/adversarial-matrices/w1112-ai-prompt-injection-matrix.md`;
veracity pin (Django-free, CI-wired):
`scripts/tests/test_w1112_ai_threat_model_veracity.py`.

| Surface | Page | Key mitigations cited (shipped) | Open threats documented |
|---|---|---|---|
| NL search → LLM interpretation → tenant-scoped search | `docs/security/threat-models/stride-ai-surfaces-w11.md` | Deterministic injection detector (fail closed), tokenized delimiters + data-only framing, strict output validation, tenant-bound cache keys, per-surface audit events | LLM path dormant + undocumented env surface; provider-side guardrails left to ops |
| Schema matching (two-party surface) | same | Detector on both schemas, matches restricted to the caller's fields, 64 KiB schema cap, blocked + performed audit events | External-partner adversarial schemas rely on the committed in-code layer |
| ML predict paths → ODH scheduler | same | 64 KiB input bound, slug-shaped `deployment_id`, shape-based ODH error classification, generic details (no exception echo), `ML_PREDICTION_PERFORMED` audit | `run_inference` bypass (limits/entitlements/rows), cross-tenant predict ownership, `ModelInference` raw I/O retention |
| LLM provider client | same | Non-TLS URL fails closed, circuit breaker + retry, hardened system prompt, third-party-boundary transport seam | Provider-side moderation not wired (dormant path) |
| Agent/tool boundary | `scripts/tests/test_w1112_ai_threat_model_veracity.py` | ABSENCE proven by AST gate over the non-test tree (no agentic imports, no tool-call sites) | The `ai-agent` marketplace contract stores third-party keys verbatim (no invocation path — recorded) |

## Verification summary (2026-10-16)

- Red-team suite `hub/apps/ai/tests/test_w1112_prompt_injection_red_team.py`
  **25/25** — real client + real DRF stack, scripted provider transport
  (third-party-boundary seam), real audit rows.
- ML boundary suite `hub/apps/ml/tests/test_w1112_ml_predict_boundaries.py`
  **7/7** — real views, scripted ODH client injected at the
  client-construction seam.
- Veracity pin `scripts/tests/test_w1112_ai_threat_model_veracity.py`
  **11/11** (RED-first: 9/11 failed before the artifacts/fixes landed).
- Regressions: `hub/apps/ai/tests/` 130 passed; `hub/apps/ml/tests/test_views.py`
  26 passed; `hub/apps/ml/tests/test_inference_service.py` 20 passed.
- RED phase root fixes, all drill-proven: detector corpus gaps
  (`pretend you are …`, `disregard … rules/directions`) caught by the
  corpus pins; the exception-echo pins flipped RED on the pre-fix
  `{e!s}` sites; the 500-vs-503 classification pins flipped RED on the
  pre-fix `ODHClientError = Exception` fallback.

## Recorded, not claimed fixed

The OPEN-THREATS lists in the matrix and the one-pager: the dormant LLM
settings surface, the `run_inference` bypass on both predict paths,
cross-tenant `deployment_id` ownership, `ModelInference` raw I/O
retention, the `ai-agent` key storage, and the detector's
degrade-never-deny tradeoff.
