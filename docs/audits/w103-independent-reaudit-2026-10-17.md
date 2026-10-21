# W10.3 — Round-3 Independent Re-Audit of the W1/W2/W3 Security Surfaces (convention 13)

**Pass:** an independent second-pass agent review (2026-10-17, `prepro01`
working tree — the current state at review time), scoped to the ten
§1.1-register classes on the W1 (authz/tenant-scoping/upload/webhook/
compiler) and W2 (money) surfaces, plus spot-checks of the W3
(pipeline) surface. **Triage:** the owning lane (W10) triaged every
finding the same day — every BLOCKER/HIGH/MEDIUM root-fixed with
RED-first pins; deliberate postures recorded as accepted-with-rationale.

Convention 13: "each remediation commit is reviewed by a second pass
before merge; changed security surfaces get a round-3 targeted re-audit
in W10.3." This record is the round-3 evidence.

## Verdict table (as reported)

| # | Class | Enforcement point | Pinning test(s) | Review verdict |
|---|---|---|---|---|
| 1 | AuthN/AuthZ bypass | TOKEN_STALE grace (`hub/apps/auth/views.py`), API-key mint allowlist, ENFORCE_JWT_SCOPES default True, SSO JWKS verification | `test_refresh_grace_w110.py`, `test_security_hardening.py`, `test_api_key_auth.py`, `test_scope_bypass_prevention.py` | **GAP** — F1 (BLOCKER): the impersonation escape guards existed as pins ONLY, zero implementation |
| 2 | Cross-tenant isolation | RLS request-path arming (SET LOCAL GUCs, fail-closed), pre-tenant alias, `lint_no_client_tenant_id.py` | `test_rls_request_path_arming.py`, `test_rls_middleware_preauth_alias.py`, `test_lint_no_client_tenant_id.py` | **PASS** |
| 3 | Money integrity | cents helper, marketplace refund row lock + idempotency keys, payment state machine | `test_w29_cents_properties.py`, `test_w31_payment_state_machine.py`, W11.7 refund pins | **GAP** — F3/F4: billing admin refund (no key, no lock) + webhook refund handler (lockless RMW) |
| 4 | Injection | warehouse identifier allowlisting on both interpolation sites; SPARQL validator on the live paths | compiler property suites, `test_w114_sparql_properties.py`, `test_sparql_validation_w115.py` | **PASS** — F7 (LOW): local keyword list omitted MOVE/COPY/ADD |
| 5 | SSRF | all five gates live (warehouse/webhook/DQ/federation/LDN) | W1.13 pins, `test_federation.py`, `test_ldn.py`, alerting pins | **PASS** |
| 6 | File-upload abuse | staging-key presigned flow, magic-byte gate at complete, size caps | `test_w118_upload_abuse.py`, `test_presigned_replay_w112.py` | **GAP** — F5: worker/dlt ingestion bypassed the magic-byte gate; storage-read fail-open; unbounded multipart parts |
| 7 | Info leakage | W1.16 5xx redaction, graphql_ld envelope, audit redaction | `test_error_response_contract.py`, graphql_ld pins, `test_w116_exc_str_leak_ban.py` | **GAP** — F2/F6: `.message`/string-`.detail` bypassed the 5xx guard; five view sites shipped `str(exc)` |
| 8 | Webhook signature + idempotency | dual-secret construct_event, `claim_stripe_event`, unique constraints | `test_stripe_webhooks.py`, `test_webhook_idempotency.py` | **PASS** |
| 9 | Worker/internal paths | fail-closed key auth, per-file caps, ClamAV enqueue | `test_internal_worker_api.py`, `test_scan_unavailable_policy.py` | **PASS** — F8 (LOW): a third `==` comparison site in the middleware |
| 10 | Pipeline crash-recovery | dlt rerun idempotency, run state machines | W3.x suites | **NOT COVERED** by the independent pass (evidence-agent budget); the W3 lane's own evidence stands (W3.3/W3.8/W3.10 tasks) |

## Findings and triage

### F1 — BLOCKER — impersonation escape guards had NO enforcement — FIXED at root

- **Finding:** `IMPERSONATION_TENANT_SWITCH_BLOCKED` / `IMPERSONATION_SESSION_ENDED`
  existed ONLY in `hub/apps/auth/tests/test_impersonation_w16.py` (pins asserting
  behavior no code implemented). `switch_tenant` re-minted a claim-less JWT pair
  under an impersonation JWT — the round-1 P0 the W1.19 sweep had wrongly
  recorded as shipped ("W1.6 impersonation blocks ✓"). Static impossibility
  proof: the two wire codes/audit actions existed in no non-test code path
  (grep + end-to-end reads of `switch_tenant`, `JWTAuthentication`, DRF
  settings, `ImpersonationMiddleware`, and the route wiring).
- **Fix (W10 lane, same day):** (1) `JWTAuthentication.authenticate` binds any
  token carrying `impersonation_session_id` to its `ImpersonationSession` row
  (pre-tenant alias; malformed claim fails closed) — a missing/ENDED session →
  401 `IMPERSONATION_SESSION_ENDED` on every DRF surface; (2) `switch_tenant`
  refuses an impersonation-tagged request with 403
  `IMPERSONATION_TENANT_SWITCH_BLOCKED` + an audit row carrying the session id;
  (3) the X-Tenant-Id scoping branch refuses impersonation-linked bearers
  (claim checked directly — `ImpersonationMiddleware` runs after the scoping
  middleware, so the request tag is not set yet); (4) the middleware's session
  lookup switched from a hardcoded `using("admin")` to the canonical
  `user_lookup_alias()` (the hardcoded alias opens a separate psycopg
  connection whose MVCC snapshot cannot see TestCase-created rows — the tag
  silently never fired under pytest, found by the fix's own pin run).
- **F1b (found by the fix verification, same class):** the strawberry GraphQL
  view is a plain Django `View` — NO DRF authentication ever ran on the
  graphql path, so the W11.2 matrix row 2.11 (revoked-token 401) was a FALSE
  PASS: the entire `test_graphql_auth.py` suite (6/8 incl. the valid-JWT
  control) failed with the resolver-level anonymous error. Fixed: the view's
  `dispatch` now runs the DRF default authenticators first and maps
  `AuthenticationFailed` to the pinned GraphQL error shape
  (`errors[0].extensions.code` + `WWW-Authenticate`); the anonymous 200
  contract is unchanged. `test_graphql_auth.py` **8/8 GREEN** after the fix.
- **Error codes + audit:** both codes catalogued in
  `docs/api/error-codes.md`; `IMPERSONATION_TENANT_SWITCH_BLOCKED` added to
  `hub/apps/audit/event_types.py` (+ `__all__`).
- **Pins:** the pre-existing RED spec `hub/apps/auth/tests/test_impersonation_w16.py`
  (7 tests: blocked switch + audit row, regular-token control, ACTIVE control,
  ENDED → 401 on REST + GraphQL, unknown session → 401, claim-less control) —
  **7/7 GREEN**; `test_graphql_auth.py` 8/8.
- **Correction:** the W1.6 promotion note in tasks.md (written from the W1.19
  claim before this re-audit landed) was corrected to record the re-audit
  finding and the fix.

### F2 — MEDIUM — 5xx guard ordered after leaky branches — FIXED at root

- **Finding:** `get_error_message` returned `exc.message` and joined
  detail-dicts BEFORE the 5xx check — repo-defined service exceptions carrying
  environment text (warehouses/core-services/integrations) leaked verbatim at
  5xx; `get_error_details` put `str(exc.detail)` into the envelope with no
  status check.
- **Fix:** the 5xx redaction now runs FIRST and unconditionally in
  `hub/apps/api/exceptions.py` (message + details); typed 4xx messages are
  preserved (the W1.16 contract).
- **Pins:** `test_error_response_contract.py` gains the two RED-first shapes
  (`.message`-bearing exception at 5xx → generic + no leak; string-`.detail` at
  5xx → no leak) + the W116 ordering pin (the guard line must precede every
  `str(exc)` site).

### F3 — MEDIUM — billing admin refund: no idempotency key, no lock — FIXED at root

- **Finding:** `BillingService.process_refund` called `stripe.Refund.create`
  with no `Idempotency-Key` and no local balance lock — a retry after a lost
  response was a fresh wire refund (the admin double-refund class). The billing
  app carries no local payment ledger to lock (recorded — the marketplace path
  got the full W11.7 treatment; billing's ledger is the W11.7 OPEN-THREATS
  item), so the wire-level dedup is the fix available today.
- **Fix:** deterministic `idempotency_key=f"refund_{payment_intent_id}_{amount_cents}"`
  on the wire call — an identical retry replays the same key and Stripe
  collapses it to the original refund; a key collision with different params
  fails loudly at Stripe.
- **Pins:** `hub/apps/billing/tests/test_services.py::BillingRefundIdempotencyPinTest`
  (3 tests, third-party-boundary seam): the key is present and deterministic;
  identical retries replay the same key; distinct amounts carry distinct keys.
- **Recorded (not fixed — design-level):** a local remaining-balance guard
  needs a billing payment/refund ledger (the W11.7 OPEN-THREATS item); ticket
  at W10.5.

### F4 — LOW — marketplace webhook refund handler lockless RMW — FIXED at root

- **Finding:** `_handle_charge_refunded` did a lockless read-modify-write —
  two concurrent `charge.refunded` events (distinct ids — the claim dedup only
  collapses same-event replays) could under-count the local refund total.
- **Fix:** the handler body now runs inside `transaction.atomic()` with
  `select_for_update()` on the payment row — the loser re-reads the committed
  total and the cumulative delta converges.
- **Pins:** `test_w117_refund_race.py::WebhookRefundHandlerRaceTest` (real
  threads, real DB, TransactionTestCase): partial + full events racing →
  `refund_amount` converges to 10.00, payment REFUNDED — never a lost update.

### F5 — MEDIUM — ingestion bypasses the magic-byte gate; fail-open read; unbounded parts — FIXED at root

- **Finding (a):** the worker/dlt catalog path (`scheduled_ingestion/catalog_records.py`)
  created ACTIVE File rows with NO magic-byte check — a PE payload named `.csv`
  through the worker credential was catalogued unverified. **(b)**
  `magic_byte_check_post_upload` returned None (skip) on a storage read error —
  a fail-open skip-the-gate bypass (SHA-256 covers bit-integrity only, never
  disguise). **(c)** the multipart initiate serializer accepted any
  `chunk_size`/`chunk_number` — the staging bucket could be flooded with
  unbounded parts.
- **Fix:** (a) the shared creation core now runs
  `validate_magic_bytes_for_content_type` on the in-memory content before the
  File row exists (the gate can never be skipped by a storage read failure
  there); (b) the complete-time read failure now RAISES
  `FILE_CONTENT_VALIDATION_UNAVAILABLE` (catalogued, 502 — the completion
  fails closed, the client retries); (c) initiate bounds: `chunk_size` ≤ 5 GiB,
  `chunk_number` ≤ 10,000 (S3's limits).
- **Pins:** `test_w38_catalog_records.py` (PE-as-CSV → `FILE_FORMAT_MISMATCH`,
  no File row); `test_magic_bytes.py` (read error → fail-closed raise);
  `test_serializers.py` (part-count + part-size bounds, boundary values pass).
- **Recorded (accepted):** browser-PUT presign cannot carry S3
  `content-length-range` (POST-only) — the complete-time size check remains
  the enforcement (the W11.8 recorded posture).

### F6 — MEDIUM — in-scope views shipped `str(exc)` into envelopes — FIXED at root

- **Finding:** five sites (semantic ontology/JSON-LD-context/relationships
  503s, semantic endpoint-create 500, warehouses 200-connection-test DSN
  text, files quota 503) plus three more the fix sweep caught (semantic 503s
  counted twice, files multipart-list 502 f-string, files storage-copy 502
  details, files storage-verification 502 details).
- **Fix:** every site now returns the generic message + logs the real
  exception server-side (typed codes preserved); the W116 AST ban module list
  extended to the four view modules (semantic/views, semantic/views_ontology,
  warehouses/views, files/views) with line-anchored allowlists ONLY for the
  deliberate keeps (the 400 FILE_FORMAT_MISMATCH typed message, the
  NoSuchUpload classification string).
- **Pins:** `scripts/tests/test_w116_exc_str_leak_ban.py` (ban extended,
  planted-violation drill still bites).

### F7 — LOW — virtualization forbidden list omitted MOVE/COPY/ADD — FIXED at root

- **Fix:** the local `SPARQL_FORBIDDEN_KEYWORDS` now carries all nine
  canonical update verbs.
- **Pins:** `test_sparql_validation_w115.py` — MOVE/COPY/ADD rejected on the
  business-rules path + a list-parity pin against the canonical validator.

### F8 — LOW — plain `==` comparison of the shared worker key — FIXED at root

- **Fix:** the TenantScopingMiddleware's worker-key branch now uses
  `hmac.compare_digest` (the internal_auth.py contract).
- **Pins:** the `WorkerKeyComparisonPin` source scan extended to
  `hub/apps/auth/middleware.py` (a regression to `==` fails it).

### F9 — LOW — documented postures — RECORDED (accepted with rationale)

- `SCAN_UNAVAILABLE_POLICY` defaults to "allow" — the W1.18 documented
  availability-over-assurance decision (explicit `"block"` available).
- `data_movement/internal_views.py` reads by id without tenant scoping behind
  the shared INTERNAL_API_KEY — response is masked (credentials excluded,
  pinned); the worker credential is the trust boundary, a by-design worker
  primitive.

### Not covered by the independent pass

- Class 10 (pipeline crash-recovery): the evidence-gathering sub-agent did not
  return before budget — recorded NOT-COVERED rather than skimmed; the W3
  lane's own evidence stands (`test_w33_idempotent_reruns.py`, W3.10 crash
  drills, W3.8 batch evidence in tasks.md).
- Live-stack verification (real PgBouncer pooling, production RLS role,
  Stripe/ClamAV wire behavior) is covered by the W10.2 staging soak evidence,
  not by this static pass.

### Chain-registry note (recorded)

`semantic.query.execute` is registered in the chain registry but the live path
calls `validate_sparql_query` directly — security-equivalent (the same
canonical validator runs); the ad-hoc state-machine convention says leave
alone unless touched; recorded, not changed.

### F10 — MEDIUM — the W1.15 SPARQL validation seam was LOST (found by the fix verification) — FIXED at root

- **Finding:** the round-3 table recorded class 4 (injection) as PASS on the
  virtualization surface — WRONG. The fix verification ran the W1.15 pin
  suite (`test_sparql_validation_w115.py`): **8/8 SERVICE/GRAPH pins RED** —
  the `commercial_hooks.validate_virtual_dataset_sparql` seam the W1.15 fix
  routed the three virtualization paths through was dropped in a later
  refactor (zero references in the tree; the workflow dispatched straight to
  the semantic client with no pre-dispatch validation). Same "pins without
  enforcement" class as F1.
- **Fix:** the seam rebuilt in `hub/apps/core/commercial_hooks.py`
  (`register_virtual_dataset_sparql_validator` /
  `validate_virtual_dataset_sparql` — GRAPH rejected in every mode, SERVICE
  delegated to the registered validator, the unregistered core-only default
  fails closed with the pinned codes); the semantic app re-registers its
  canonical `validate_sparql_query` in `ready()`; the three virtualization
  paths + the workflow's pre-dispatch leg call the seam.
- **Pins:** `test_sparql_validation_w115.py` **13/13 GREEN** (the 8
  SERVICE/GRAPH pins + 3 accept-controls + the two W10.3 MOVE/COPY/ADD pins).

### F11 — LOW — the W11.8 fail-open magic-byte pin blessed the skip (found by the fix verification) — pin rewritten

- The pre-existing `test_post_upload_gate_fails_open_on_storage_error`
  asserted the SKIP behaviour (read error → None → the disguise check never
  ran). Rewritten to the new fail-closed contract
  (`FILE_CONTENT_VALIDATION_UNAVAILABLE`); the W11.8 tasks.md note about the
  deliberate fail-open is superseded by this record.

### Verification-environment notes (recorded, not code findings)

- The shared host-side 313full test DB was destroyed by a pytest run without
  `--reuse-db` (the documented `TEST_DB_SUFFIX` hazard) and rebuilt with a
  fresh migrate; the round-3 verification battery then ran on a session-
  private pg_dump clone (a sibling session was testing against the shared DB
  concurrently — the clone avoided the cross-session TRUNCATE contention).
- `test_error_response_contract.py` carries 4 failures in the
  `TestErrorResponseContract` shape tests — the W12.10 sibling lane's
  in-flight flat-vs-nested envelope drift, not this lane's change (the
  `TestExceptionHandlerNoLeak` class is 6/6).
- The sibling tree's `unique_active_filename_per_tenant` collision test
  depends on the files.0017 constraint being present in the test DB; the
  first clone (created via a pipe whose restore errors were filtered) had
  lost it — the rebuilt clone carries it and the test passes.
