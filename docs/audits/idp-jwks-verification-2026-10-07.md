# IdP JWKS verification — W1.0 (S3, D4 precondition)

Verified **2026-10-07** as the M1 precondition recorded in tasks.md W1.0
(oss-release-remediation). Contract: GATE-53
(`scripts/check_idp_jwks_decision.py`) enforces this record; the
capability itself is re-verifiable live with one command
(`make check-idp-jwks`).

## Outcome

- **Outcome:** JWKS_EXPOSED
- **Reason:** the pilot IdP serves a fetchable JWKS at its `jwks_uri`
  with 3 keys, all of them RSA RS256 signature keys that the OIDC
  verification stack (PyJWK — the same consumer path W1.5 uses) loads
  and can use to verify ID-token signatures. The D4 precondition (S3)
  is met; no fallback is needed.

## Live verification evidence

- **Check tool:** `scripts/check_idp_jwks.py` — the W1.0 capability
  check, executed LIVE over real HTTPS on 2026-10-07 (exit 0,
  `RESULT: CAPABLE (JWKS_EXPOSED) — 3 usable signing key(s)`) — plus
  the W16-gated live tests in
  `hub/apps/auth/tests/test_sso_idp_metadata.py` (the real discovery +
  real JWKS asserted on every live run; the scripted-surface contract
  pins use the REAL JWKS captured from the pilot IdP on 2026-10-07 as
  the fixture).
- **Discovery:** HTTP 200 at
  `https://<host>/oidc/.well-known/oauth-authorization-server` —
  issuer `https://<host>/oidc`, authorization/token endpoints present,
  `jwks_uri` = `https://ohio.cloud.databricks.com/oidc/jwks.json`
  (the Databricks regional OIDC surface).
- **JWKS:** HTTP 200 at the `jwks_uri` — 3 keys, kty=RSA ×3, all
  alg=RS256 use=sig, all loadable by PyJWK → 3 usable signing keys.
- **Key ids:** `646befd4…`, `jnRqFg`, `vBPZrA`.
- **Pilot IdP:** Databricks-as-IdP OIDC (openspec 0b.12), the SSO
  surface wired by pilot-readiness 3.1. If U later moves SSO to the
  corporate IdP (Okta/Auth0/Entra), the same check must pass against
  that IdP before W1.5's SSO E2E — re-run `make check-idp-jwks`.

## D4 consequence

- **D4 proceeds on the JWKS-verification plan** — W1.5 implements the
  OIDC callback with JWKS signature/aud/exp verification
  (authlib/pyoidc), deletes the SAML stub, and lands the adversarial
  tests (unsigned, wrong-aud, expired, role forgery) plus endpoint
  throttles exactly as decided.
- **No cert-pinned fallback** — the fallback decision is NOT taken and
  D4 is NOT re-scoped: the precondition (S3) is met. The fallback path
  remains documented in design.md only as the contingency for a future
  IdP that fails this check.

## Sign-off

| Party | Role | Status | Date |
|---|---|---|---|
| D (engineering) | Capability check executed live (real HTTPS, exit 0, 3 usable signing keys) | signed | 2026-10-07 |
| Meshant (U) | IdP JWKS capability + D4 path sign-off | signed | 2026-10-07 |
