# W11.5 — ASVS V6 Crypto Audit (random sweep + hash strength)

**Date:** 2026-10-16
**Scope:** `hub/`, `cli/`, `scripts/` (Python). Register row 18 (insecure randomness)
verified; hash-strength reviewed per ASVS V6.
**Artifacts:** the sweep gate `scripts/check_crypto_random.py` (blocking, CI-wired),
the inventory report `docs/audits/w115-random-sweep-report.md` (generated),
the allowlist `scripts/crypto_random_allowlist.txt`,
the password-hashing pins `hub/apps/auth/tests/test_w115_password_hashing.py`,
the gate pins `scripts/tests/test_w115_crypto_random_sweep.py`,
the rotation runbook `docs/runbooks/fernet-key-rotation.md`.

## 1. `random.*` CSPRNG sweep (register row 18)

**Verdict: CLEAN — 13 `random.*` sites, 0 token-context, 0 allowlist entries needed.**

Every site is benign (backoff jitter, data sampling, trace sampling, test seeds,
capacity-test offsets) — full inventory in `docs/audits/w115-random-sweep-report.md`.
No `random.*` usage in any token/key/secret/nonce/reset/session context exists in
the tree; token material is generated via `secrets.token_urlsafe/token_hex`,
`uuid.uuid4` (CSPRNG-backed), or Django's password machinery (15 `secrets.*` call
sites in hub non-test code). The gate now PROVES this absence going forward:

* AST-based (attribute AND `from random import X` alias forms — the alias form is
  the classic checker blind spot, pinned);
* token-context classification via assignment-target + enclosing-function keyword
  matching; vendored trees (`venv/`, `site-packages/`) excluded by design;
* blocking in CI (`make quality-gates` + the lint job), exit 1 on any
  unallowlisted token-context site, dead-anchor detection via `--check-anchors`;
* planted-violation pins flip the gate RED (both import forms) — and the
  falsifiability-harness entry (`gate-62-crypto-random`) mutates the keyword
  list to prove the blindness pin bites.

## 2. Hash-strength audit

### 2.1 Password hashing — FINDING + FIX

**Finding:** the repo's ONLY `PASSWORD_HASHERS` definition lived inside the
TEST-env branch (MD5-first for suite speed — Django's documented test practice,
and the test-stack gunicorn must verify MD5 hashes for SDK-created users).
Production therefore leaned on Django's framework default (PBKDF2-SHA256 first)
— correct, but ABSENT: nothing declared it, and a future edit could reintroduce
MD5-first for production with nothing to catch it (the row-18 absence rule).

**Fix (this change):** the production posture is now EXPLICIT — a
non-test `PASSWORD_HASHERS` block declares PBKDF2-SHA256 first (1,200,000
iterations, Django 6 default — meets ASVS V6's ≥600k), PBKDF2SHA1 and MD5 last
for LEGACY VERIFICATION only (`check_password` dispatches on the hash prefix —
no migration, existing rows keep verifying). Pins (RED-first):
`hub/apps/auth/tests/test_w115_password_hashing.py` — the production block
exists and is PBKDF2-first (source-pinned), the test-env MD5-first speed swap is
the ONLY MD5-first site and keeps PBKDF2 listed, `make_password` follows the
configured first hasher, iterations ≥600k, and legacy MD5/SHA1 hashes verify.

### 2.2 API keys & refresh tokens — bare SHA-256 of high-entropy tokens

`APIKey.hash_key` and `RefreshToken.hash_token` are unsalted SHA-256. The
threat model makes this acceptable and it stays: the hashed values are
43-char `secrets.token_urlsafe(32)` (256-bit CSPRNG) — offline dictionary
attacks are infeasible regardless of hashing speed, and a slow KDF would add
login-path latency for zero protection. (The W11.2 matrix recorded this as an
OPEN-THREAT; this audit closes it with the rationale.) Any future change that
lowers token entropy below ~128 bits MUST switch to a slow hash first.

### 2.3 Webhook signing keys — sound

`WebhookSigningKey` material is `secrets.token_hex(32)` (256-bit CSPRNG),
stored encrypted (KMS-first / Fernet fallback), signatures are HMAC-SHA256,
and the lifecycle is a rolling 3-key window (1 ACTIVE + up to 2 RETIRING,
auto-pruned 7 days after RETIRED). Rotation exists per-webhook.

### 2.4 Fernet fallback encryption — derivation + rotation

The Fernet key derives from `ENCRYPTION_KEY` via SHA-256 → urlsafe-base64
(a key-normalization KDF for an arbitrary-length secret — sound; the secret
itself must be ≥128-bit random, which the G12 explicit-secrets contract now
enforces by failing closed on empty keys). AWS KMS is the preferred path when
`AWS_KMS_KEY_ID` is set.

**FINDING + FIX (rotation command):** `rotate_webhook_encryption_key` fed
EVERY row through decrypt-then-encrypt — non-Fernet ciphertexts
(`aws-kms:`, `vault:v1:`) pass through `_decrypt_with_key` unchanged and were
then FERNET-WRAPPED as plaintext, corrupting the KMS/Vault blobs into
double-encrypted garbage. The command now SKIPS both prefixes (reported,
untouched), rotates `v1:` rows old→new, and opportunistically encrypts legacy
plaintext rows. Pins (RED-first, `hub/apps/webhooks/tests/test_key_rotation_command.py`):
aws-kms row byte-identical after rotation, vault row untouched, plaintext row
encrypted under the new key — plus the existing rotate/dry-run/same-key pins.

**Runbook:** `docs/runbooks/fernet-key-rotation.md` — the verified procedure
(dry-run semantics, prefix skip, verification step, rollback, maintenance-window
notes). Known constraint recorded honestly: `encrypt_secret` is single-key, so
the env flip and the rotation must run in one maintenance window; the
`WebhookSigningKey.secret_encrypted` rows (not covered by the command) are
short-lived (7-day prune) and are re-created per webhook via `rotate_secret`
after the flip.

### 2.5 Non-security hash uses — reviewed, acceptable

MD5/SHA1 outside security contexts (cache keys, ETags, dedup state hashes,
gravatar email hashing, `oidc_jwks` cache-key SHA-1) — collision attacks have
no security impact there; recorded, not changed.

### 2.6 Adjacent V6 surfaces (already pinned by earlier workstreams)

* JWT: RS256 asymmetric with the production PEM-pair guard (W1.18), alg pinned.
* SSO state: HMAC-SHA256 with `SECRET_KEY`, single-use + IP-class bound (W1.5).
* OIDC ID tokens: RS256/ES256-only JWKS verification (W1.5).
* Impersonation JWT: short TTL + DB-checked session row (W5.1).
