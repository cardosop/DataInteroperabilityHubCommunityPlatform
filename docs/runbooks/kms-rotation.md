# KMS Key Rotation Runbook

**Phase 260.7.H** — closes pass-3 B3-6.

## Scope

This runbook documents the AWS KMS key rotation policy for the Meshant
platform. It covers:

1. **Policy**: 365-day automatic rotation cadence on every customer-managed
   KMS (CMK) key the platform owns.
2. **Coverage**: which platform components use which keys, and which keys
   currently exist vs. are intended for future addition.
3. **Operational steps**: how to verify rotation is enabled, how to monitor
   rotation events, and how to manually rotate a key (key-material
   rotation, NOT alias re-target — see "Manual rotation" below).

The IaC contract is pinned in
[`infrastructure/terraform/modules/kms/main.tf`](../../infrastructure/terraform/modules/kms/main.tf)
and verified by [`tests/infrastructure/test_kms_rotation_policy.py`](../../tests/infrastructure/test_kms_rotation_policy.py).
A regression that drops `enable_key_rotation = true` from any
platform-owned CMK fails the test.

## Policy

**Every customer-managed KMS key the Meshant platform creates MUST
enable automatic key rotation.**

* `enable_key_rotation = true` on the `aws_kms_key` resource (Terraform
  AWS provider 5.x). This sets `KeyRotationStatus = Enabled` on the
  underlying KMS key.
* AWS KMS rotates **symmetric** CMKs on a **365-day cadence** (annual).
  This cadence is fixed by AWS for symmetric CMKs — see the
  [AWS KMS docs on automatic rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html)
  ("AWS KMS rotates symmetric encryption KMS keys every 365 days from the
  enable date"). The platform does NOT need (and cannot configure) a
  different cadence; the AWS-native default IS the policy.
* Asymmetric CMKs are NOT used by the platform. If they are added later,
  this runbook MUST be updated — asymmetric keys do NOT support automatic
  rotation in AWS KMS and require a different operational pattern
  (manual key replacement + re-encrypt).
* AWS-managed keys (`aws/s3`, `aws/rds`, etc.) are rotated by AWS on a
  3-year cadence and are out of scope for this policy — the platform
  does not own them and cannot influence their rotation.

## Coverage matrix

| Component | Encryption type | Key | Rotation status | Source |
|-----------|-----------------|-----|-----------------|--------|
| **Application field encryption** (webhook secrets, integration credentials, encrypted JSON fields) | Customer-managed CMK (Fernet wrapping via `encrypt_secret`) | `alias/meshant-app-encryption-{env}` (e.g. `alias/meshant-app-encryption-prod`) | ✅ Enabled (`enable_key_rotation = true` in [`infrastructure/terraform/modules/kms/main.tf`](../../infrastructure/terraform/modules/kms/main.tf) line 112) | Phase 211 |
| **Legacy `hub-assets-{env}` bucket** (NOT deployed by current envs — see note below) | Customer-managed CMK (SSE-KMS) | `alias/meshant-s3-{env}` declared in [`infrastructure/terraform/s3/main.tf`](../../infrastructure/terraform/s3/main.tf) line 54 | ✅ Enabled (`enable_key_rotation = true` line 56) | Phase 51 (legacy) |
| **S3 file storage** (`hub-files-{env}-{account}` bucket — the ACTIVELY-deployed file storage) | AWS-managed (SSE-S3 / AES256) — NO CMK | n/a (`sse_algorithm = "AES256"` in [`infrastructure/terraform/modules/s3-buckets/main.tf`](../../infrastructure/terraform/modules/s3-buckets/main.tf) line 83) | n/a (AES256 is symmetric AES-256-GCM rotated by AWS S3 internally) | Phase 213 |
| **S3 file storage (FUTURE — when CMK is added)** | Customer-managed CMK (SSE-KMS) | `alias/meshant-file-storage-{env}` (planned ARN: `arn:aws:kms:{region}:{account}:key/...`) | ✅ MUST be enabled when the key is added — pinned by `test_kms_rotation_policy.py::test_all_platform_kms_keys_have_rotation_enabled` | 260.7.H (this runbook is the contract) |

> **Note on the legacy `infrastructure/terraform/s3/` module**: this
> module declares an `hub-assets-{env}` bucket with a customer-managed
> CMK, but neither `environments/staging/main.tf` nor
> `environments/prod/main.tf` source it (they wire `module "s3"` from
> `modules/s3-buckets` instead — the actively-deployed file storage).
> The legacy module's `meshant_s3` key is included in the rotation
> policy contract REGARDLESS of deployment status: if a future PR
> revives the module or copies its pattern, the test guards against
> a regression that would skip rotation. Cleanup of the legacy module
> is tracked separately as ops hygiene; out of scope for 260.7.H.

### Why S3 file storage is currently AES256, not CMK

The existing `aws_s3_bucket_server_side_encryption_configuration.files`
([s3-buckets/main.tf line 78-87](../../infrastructure/terraform/modules/s3-buckets/main.tf))
uses `sse_algorithm = "AES256"` (SSE-S3) rather than SSE-KMS. SSE-S3 is
sufficient for at-rest encryption of file blobs because:

1. The platform does NOT need per-tenant key isolation at the S3 layer
   (tenant isolation is enforced at the application layer via
   `tenant_id` row scoping + RLS policies).
2. SSE-S3 has zero per-request KMS API call cost; SSE-KMS would add a
   `kms:Decrypt` call per S3 GET (priced per-call in AWS).
3. Compliance frameworks (SOC2, GDPR Art. 32) accept SSE-S3 as a valid
   "encryption at rest" control.

If a customer specifically requires CMK-level control over file-blob
encryption (e.g., compliance contract demanding tenant-controlled keys),
the addition path is documented in "Adding a customer-managed file
storage key" below.

## Verifying rotation is enabled

### Method 1 — `aws kms get-key-rotation-status`

```bash
# For the existing app-encryption key (replace {env} with prod / staging)
aws kms get-key-rotation-status \
  --key-id alias/meshant-app-encryption-{env} \
  --region us-east-1
```

Expected output:

```json
{
  "KeyRotationEnabled": true
}
```

If `KeyRotationEnabled` is `false`, run:

```bash
aws kms enable-key-rotation \
  --key-id alias/meshant-app-encryption-{env} \
  --region us-east-1
```

(The standing IaC contract should prevent this drift; if it happens,
investigate why the Terraform apply diverged from the desired state.)

### Method 2 — Terraform plan

```bash
cd infrastructure/terraform/environments/{env}
terraform plan -target=module.kms
```

A non-empty plan on the `enable_key_rotation` field is the DRIFT signal.

### Method 3 — CI test

The pytest at
[`tests/infrastructure/test_kms_rotation_policy.py`](../../tests/infrastructure/test_kms_rotation_policy.py)
parses `infrastructure/terraform/modules/kms/main.tf` and asserts every
`aws_kms_key` resource sets `enable_key_rotation = true`. The test runs
on every CI build; a future Terraform PR that disables rotation would
fail this test before merge.

## Monitoring rotation events

AWS KMS emits a CloudTrail event each time it rotates a key:

* **Event source**: `kms.amazonaws.com`
* **Event name**: `RotateKey` (the AUTOMATIC rotation; AWS-issued, not
  user-issued)
* **Resource ARN**: the CMK ARN being rotated

Recommended alarm: a CloudTrail metric filter on
`eventName = "RotateKey"` for our key ARNs, with a CloudWatch alarm that
fires if NO rotation event is observed within the last 380 days
(365-day cadence + 15-day grace for AWS scheduling jitter). The alarm
indicates rotation has stalled and requires investigation.

The alarm wiring is OUT OF SCOPE for 260.7.H (this runbook); it's
tracked as a future ops-hardening task.

## Manual rotation

**Use case**: an incident requires forcing rotation BEFORE the next
automatic 365-day cycle (e.g., suspected key compromise, key-policy
change, IAM role rotation).

### Step 1: Generate new key material

For symmetric CMKs with automatic rotation enabled, AWS KMS generates
new key material on the rotation cadence. The OLD key material is
retained for decryption of objects encrypted with the previous version
(AWS handles version selection transparently).

**To force a rotation outside the cadence:**

```bash
# Trigger a rotation NOW (does not wait for the 365-day cadence to elapse).
aws kms rotate-key-on-demand \
  --key-id alias/meshant-app-encryption-{env} \
  --region us-east-1
```

(Available in AWS provider 5.30+ and `aws kms rotate-key-on-demand`
CLI v2.18+. If unavailable, fall back to disable+re-enable rotation:
`aws kms disable-key-rotation` followed by `aws kms enable-key-rotation`
which schedules a new rotation cycle.)

### Step 2: Verify the rotation completed

```bash
aws kms list-key-rotations \
  --key-id alias/meshant-app-encryption-{env} \
  --region us-east-1
```

The output lists all rotation events (automatic + on-demand) with
timestamps. The most recent entry should be the rotation just
triggered.

### Step 3: Verify application can still decrypt OLD ciphertexts

The platform stores ciphertexts in the database (webhook secrets,
integration credentials). After rotation, AWS KMS retains all PRIOR
key material; `kms:Decrypt` calls on old ciphertexts continue to work
WITHOUT application changes.

To verify, run a smoke test that decrypts a known-old ciphertext:

```bash
# In the API service environment:
python manage.py shell -c "
from hub.apps.webhooks.models import Webhook
w = Webhook.objects.first()  # any pre-rotation webhook
print(w.decrypted_secret[:20] + '...')  # truncated for log safety
"
```

If decryption fails, investigate the KMS key state — the most likely
cause is an IAM role change unrelated to rotation. The application's
`decrypt_secret` helper (in
[`hub/apps/webhooks/encryption.py`](../../hub/apps/webhooks/encryption.py))
catches `kms:Decrypt` failures and surfaces them as `ValueError` with a
clear message.

## Adding a customer-managed file storage key

If a future requirement adds a CMK for S3 file-storage encryption
(replacing the current SSE-S3 / AES256), follow this pattern:

1. **Add the key resource** to the Terraform KMS module:

   ```hcl
   resource "aws_kms_key" "file_storage" {
     description              = "Meshant ${var.environment} - file storage S3 SSE-KMS"
     key_usage                = "ENCRYPT_DECRYPT"
     customer_master_key_spec = "SYMMETRIC_DEFAULT"

     enable_key_rotation     = true   # ← MUST be set per this runbook
     deletion_window_in_days = local.deletion_window

     policy = data.aws_iam_policy_document.file_storage_key.json

     tags = merge(local.common_tags, {
       Name = "meshant-${var.environment}-file-storage"
     })
   }

   resource "aws_kms_alias" "file_storage" {
     name          = "alias/meshant-file-storage-${var.environment}"
     target_key_id = aws_kms_key.file_storage.key_id
   }
   ```

2. **Update the S3 bucket SSE config** in
   `infrastructure/terraform/modules/s3-buckets/main.tf`:

   ```hcl
   resource "aws_s3_bucket_server_side_encryption_configuration" "files" {
     bucket = aws_s3_bucket.files.id
     rule {
       apply_server_side_encryption_by_default {
         sse_algorithm     = "aws:kms"
         kms_master_key_id = var.file_storage_kms_key_arn
       }
       bucket_key_enabled = true   # use bucket-level key to amortise per-request cost
     }
   }
   ```

3. **Verify the test still passes** —
   `test_kms_rotation_policy.py::test_all_platform_kms_keys_have_rotation_enabled`
   parses `enable_key_rotation` settings on EVERY `aws_kms_key` resource
   in the module. Adding a new key without `enable_key_rotation = true`
   would fail the test.

4. **Plan and apply** through the standard staging → prod promotion via
   GitHub Actions.

5. **Migrate existing data** — files encrypted under SSE-S3 do NOT
   automatically migrate to the new CMK. Either:
   * Accept the mixed state (new uploads use CMK, old uploads stay AES256).
   * Run an S3 batch operation to re-encrypt all objects with the CMK
     (large data egress + put cost; only do this for compliance
     hard-requirements).

## Audit / compliance trail

The runbook contract is exposed at three audit points:

1. **Terraform IaC** — `enable_key_rotation = true` is the source of
   truth. Compliance auditors can `terraform show` to verify state
   parity.
2. **CI test** — `test_kms_rotation_policy.py` fails CI on any
   regression that disables rotation in IaC.
3. **AWS Config rule** — `kms-cmk-not-scheduled-for-deletion` and
   `cmk-backing-key-rotation-enabled` (AWS-managed Config rules) flag
   non-compliant keys. Wiring these into the platform's compliance
   dashboard is OUT OF SCOPE for 260.7.H; tracked as a future
   ops-hardening task alongside the CloudTrail rotation alarm.

## Related runbooks

* [`destroy-staging.md`](./destroy-staging.md) — KMS keys are NOT
  destroyed by `terraform destroy` (they enter the deletion window
  per `deletion_window_in_days` — 7d staging, 30d prod). Re-creating
  staging within the deletion window will fail unless the key alias
  is reused.
* [`datasets-files-dr.md`](./datasets-files-dr.md) — disaster recovery
  for file storage. KMS rotation is orthogonal to DR (rotation does
  NOT change the key ARN or alias; backups and restores work
  transparently).

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
