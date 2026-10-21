# Fernet Webhook-Secret Key Rotation

**Scope:** the webhook-secret encryption layer (`hub/apps/webhooks/encryption.py`).
**Status:** authoritative runbook — cites the real machinery only.
**Owner:** Security Team.

## Background

Webhook secrets are encrypted field-level with a layered scheme:

| Prefix | Meaning | Rotatable? |
|---|---|---|
| `aws-kms:` | AWS KMS ciphertext (Phase 211, primary when `AWS_KMS_KEY_ID` is set) | Yes — via KMS key rotation, no data re-encryption |
| `v1:` | Fernet ciphertext (fallback when KMS is unavailable) | Yes — via this runbook |
| `vault:v1:` | Legacy Vault Transit (no longer decryptable) | No — historical rows only |
| plain text | Legacy pre-migration record | Migrate on first re-save |

The Fernet key is derived from `ENCRYPTION_KEY` (`hub/apps/webhooks/encryption.py::_get_fernet`:
`sha256(raw)` → urlsafe-base64 → `Fernet`). Rotating the Fernet key therefore
means **re-encrypting every `v1:` row** with the new key — decrypt with the old,
encrypt with the new. The command that does this exists and is production-wired:

```
python manage.py rotate_webhook_encryption_key --old-key <current> --new-key <replacement>
```

## Pre-rotation checks

1. **Confirm the current key decrypts.** Run the dry-run BEFORE touching anything:
   ```bash
   python manage.py rotate_webhook_encryption_key \
       --old-key "${OLD_ENCRYPTION_KEY}" --new-key "${NEW_ENCRYPTION_KEY}" --dry-run
   ```
   The dry-run samples the FIRST 5 rotatable rows (a smoke probe, not an
   exhaustive verify — the full pass happens in step 3). A decrypt FAILED on
   any sampled row means the `--old-key` value does not match the deployed
   `ENCRYPTION_KEY` — stop and fix the old-key value; never proceed.
2. **Back up the database** (the webhooks table) — the standard
   `create_backup.sh` flow, before the rotation window.
3. **Prefer KMS.** If `AWS_KMS_KEY_ID` is configured, new writes already use
   KMS; schedule KMS key rotation instead and treat the Fernet path as the
   fallback that still needs this procedure for rows written while KMS was
   unavailable.

## Rotation procedure

1. **Stage the replacement key.** Generate it with a CSPRNG and keep it in the
   secrets store (never the repo):
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. **Dry-run** (above) — samples 5 rotatable rows decrypting under the old
   key, without writing.
3. **Rotate** (batched, 100 rows per `transaction.atomic()` block):
   ```bash
   python manage.py rotate_webhook_encryption_key \
       --old-key "${OLD_ENCRYPTION_KEY}" --new-key "${NEW_ENCRYPTION_KEY}"
   ```
   Optional: `--tenant-id <uuid>` to roll a single tenant first as a canary.
   Prefix semantics (W11.5-fixed): `aws-kms:` and `vault:` rows are SKIPPED
   and reported — they are not Fernet ciphertexts (the pre-fix loop
   double-wrapped them as plaintext, corrupting the blobs); `v1:` rows
   decrypt under the old key and re-encrypt under the new; legacy
   PLAIN-TEXT rows are opportunistically encrypted with the new key.
4. **Verify** a sample decrypts under the NEW key:
   ```bash
   python manage.py rotate_webhook_encryption_key \
       --old-key "${NEW_ENCRYPTION_KEY}" --new-key "${NEW_ENCRYPTION_KEY}-dummy" --dry-run
   ```
   (dry-run with the new key as `--old-key`: the sample must decrypt OK.
   A self-pair `--old-key == --new-key` is rejected by the command.)
5. **Flip the environment.** Update `ENCRYPTION_KEY` (ExternalSecrets /
   `.env.production` / helm values — per `RB-SEC-001-credential-rotation.md`)
   and deploy. New writes now encrypt with the new key.
6. **Post-checks:** webhook delivery smoke test (`/health/` + one test
   delivery); confirm no `v1:` row remains decryptable under the old key;
   record the rotation in the audit ledger.

## Rollback

Re-run the command with the keys swapped (the rotation is symmetric):

```bash
python manage.py rotate_webhook_encryption_key \
    --old-key "${NEW_ENCRYPTION_KEY}" --new-key "${OLD_ENCRYPTION_KEY}"
```

Then restore `ENCRYPTION_KEY` to the old value and deploy. Note the window:
rows written between the flip and the rollback were encrypted with the new
key — the rollback re-encrypts them with the old key, so run the rollback
command AFTER the env restore decision is final.

## Constraints

* **`vault:v1:` rows are not recoverable** — the legacy Vault Transit backend
  is retired; affected rows must be re-provisioned manually (their secrets
  re-entered), not rotated.
* **Plain-text legacy rows** are re-encrypted opportunistically on save, not
  by this command.
* The rotation window is additive, not atomic across the fleet — the command
  itself is transactional per batch, so an interrupted run resumes safely:
  already-rotated rows carry the `v1:` prefix with the new key; re-running
  with the same `--old-key` would fail the dry-run for those rows, so resume
  with a fresh dry-run against the REMAINING old-key rows or finish the run
  to completion before the env flip.
* The W11.5 sweep gate (`scripts/check_crypto_random.py`) and the
  password-hashing pins (`hub/apps/auth/tests/test_w115_password_hashing.py`)
  are the adjacent V6 controls; see
  `docs/audits/w115-crypto-audit-2026-10-16.md`.
