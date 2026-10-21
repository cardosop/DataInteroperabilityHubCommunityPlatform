# W11.1 Threat-Model Refresh Ledger — 2026-10-15

STRIDE one-pager per changed surface (oss-release-remediation W1–W5),
committed WITH the fixes they describe. Every mitigation row cites its
verifying test or gate — the P4 rule applied to threat models: a
mitigation with no pin is prose, not a fix. The mechanical veracity
pins live in `scripts/tests/test_w111_threat_model_veracity.py`
(existence, six STRIDE categories per page, every backticked artifact
citation resolves on disk, ≥1 test/gate citation per category section).

| Surface | Page | Key mitigations cited (shipped) | Open threats documented |
|---|---|---|---|
| auth-tenant (W1) | `docs/security/threat-models/stride-auth-tenant-w1.md` | RLS request-path arming (W1.20/D2 — SET LOCAL GUCs, fail-closed, `user_lookup_alias`); OIDC+JWKS SSO (W1.5); register/user-create gates (W1.1/W1.2/W1.2b); API-key scope minting (W1.3a); warehouse SQLi compilers (W1.11); SSRF re-validation + hop-3 block (W1.13); worker internal path (W1.14); envelope no-`str(exc)` (W1.16); Stripe atomic claim (W1.17); hardening (W1.18); audit sweep (W1.19) | W1.20 72h soak + prod flip ops-scheduled; W1.6/1.8/1.9/1.10/1.12/1.15 unchecked lanes |
| money (W2) | `docs/security/threat-models/stride-money-w2.md` | decimal + ROUND_HALF_UP cents helper (W2.1); Stripe webhook signature + secret-file + idempotency E2E (W2.0/W2.10); order state machine (W2.3); governance chain + segregation ledger (W2.4); metering idempotency keys (W2.5); entitlement locks + revoke audit (W2.6); plan limits incl. AR cap + counter reconciliation (W2.7/W2.8) | live-account switch ops-scheduled; Stripe E2E env-gated (W16) |
| pipeline (W3) | `docs/security/threat-models/stride-pipeline-w3.md` | guarded run state machines + CHECK constraints (W3.1); uniform completion (W3.2); idempotent re-runs + processed-keys (W3.3); cursor-on-success (W3.4); heartbeat/lease + stuck-run detectors + cancel (W3.5/W3.6); catalog parity by source key (W3.8) | live-Databricks round-trip env-gated; heartbeat tuning ops-configurable |
| event-bus (W4) | `docs/security/threat-models/stride-event-bus-w4.md` | sent/cons dedup namespaces (W4.1); on_commit publishing + listener deployment (W4.1); emitter decision table (W4.1b); search reindex (W4.2); locked contract versions + conflict-to-409 (W4.4) | cross-service durability out of OSS scope; bus DAST in W11 lanes |
| frontend-identity (W5) | `docs/security/threat-models/stride-frontend-identity-w5.md` | impersonation token lifecycle + bearer swap + flag-or-role gate (W5.1); identity cache bus + tenant-keyed capabilities (W5.2) | identity E2E in nightly lanes; SW caching out of scope |

**Evidence conventions:** citations are bare repo-relative paths (the
pin resolves them) — `path:line` anchors appear in prose only where the
file-level citation is ambiguous. The five pages were written AFTER the
fixes shipped (the refresh models the shipped tree, not the plan).

**Falsifiability:** the veracity pin file is wired into the CI lint job
(a removed page, a renamed citation, or a dropped STRIDE section flips
it RED); the pin suite itself is registry-listed in the falsifiability
harness convention (scripts/tests runs in CI).
