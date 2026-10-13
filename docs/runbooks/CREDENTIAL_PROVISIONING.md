# Credential Provisioning — Live Connector Coverage

Runbook for acquiring the live/test credentials needed to un-skip the
marketplace connector tests (coverage-closure plan Phase 1). All keys go
into `.env.test` (gitignored — never commit values; print them to the
terminal only once, then paste).

After filling a key, verify with:

```bash
python scripts/verify_connector_creds.py            # all connectors
python scripts/verify_connector_creds.py snowflake  # one connector
```

and run the affected batch (`make test-batch-6-4` for marketplace
connectors). The tests activate automatically once the key is present —
W16 envpolicy makes CI **raise** instead of skip when a credential is
missing, so an empty key is loud, not silent.

---

## 1. Snowflake — `SNOWFLAKE_TOKEN` (Programmatic Access Token)

Already present: `SNOWFLAKE_ACCOUNT=WCGKMGD-XC16102`,
`SNOWFLAKE_USER=CARDOSOP`. Missing: the token.

Steps:
1. Log in at `https://app.snowflake.com` for account locator
   `WCGKMGD-XC16102` as `CARDOSOP`.
2. **Admin → Users & Roles → Users → CARDOSOP → Programmatic Access →
   Create token** (name it e.g. `datahub-test`, expiration 90 days).
3. Copy the token (shown once) into `.env.test`:
   `SNOWFLAKE_TOKEN=<token>`.
4. Optional for warehouse tests: set `SNOWFLAKE_WAREHOUSE=<wh>` if the
   default warehouse isn't wanted.
5. Verify: `python scripts/verify_connector_creds.py snowflake` then
   `make test-batch-6-4`.

## 2. Stripe (test mode) — `STRIPE_*`

Needed keys: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`,
`STRIPE_WEBHOOK_SECRET`, `STRIPE_MARKETPLACE_WEBHOOK_SECRET`.

Steps:
1. Sign up at `https://dashboard.stripe.com` (free) and switch the
   dashboard toggle to **Viewing test data**.
2. **Developers → API keys** → copy the publishable key
   (`pk_test_…`) and secret key (`sk_test_…`) into `.env.test`.
3. Webhook secrets — local testing uses the Stripe CLI (test-mode webhooks
   are forwarded to localhost):
   ```bash
   stripe listen --forward-to http://localhost:8001/api/v1/billing/stripe/webhook/
   ```
   The CLI prints a `whsec_…` secret → `STRIPE_WEBHOOK_SECRET`.
   Repeat the equivalent for the marketplace webhook route →
   `STRIPE_MARKETPLACE_WEBHOOK_SECRET`.
4. To exercise the billing-upgrade flow end-to-end, create a test-mode
   Customer in the Stripe dashboard and attach its `cus_…` id to the
   smoke admin (`e2e_admin@example.com`) `stripe_customer_id` — see
   `docs/raci/stripe-connect-mvp.md`.
5. Verify: `python scripts/verify_connector_creds.py stripe` and the
   `JOURNEY-TA-BILLING-UPGRADE` spec (f5) runs its Stripe assertions.

## 3. Azure Marketplace — `AZURE_MARKETPLACE_API_KEY`

The connector hits the Catalog API
(`https://catalogapi.azure.com`, API version `2025-05-01`) with an
`X-API-Key` header — an OAuth client secret is NOT used by this
connector (the `.env.test` `AZURE_CLIENT_ID/TENANT_ID/SECRET` entries
belong to other tooling).

Steps:
1. Sign in to **Microsoft Partner Center**
   (`https://partner.microsoft.com`) with the Microsoft account that owns
   the Marketplace publisher enrollment.
2. **Workspaces → Marketplace offers → Settings → Catalog API**
   (enable if not already) → copy the API key.
3. `.env.test`: `AZURE_MARKETPLACE_API_KEY=<key>` (alias
   `AZURE_CATALOG_API_KEY` also accepted).
4. Verify: `python scripts/verify_connector_creds.py azure`.

Note: the Catalog API requires a completed publisher enrollment; a bare
Microsoft account will get 401/403. If enrollment is not available,
record the decision in the coverage plan (mock-only for Azure) instead.

## 4. Dados.gov.br — `DADOS_GOV_BR_API_KEY` (JWT)

The connector authenticates to `https://dados.gov.br` with a JWT
(`CKAN_DADOS_GOV_BR_API_KEY` is the backward-compatible alias).

Steps:
1. Register at `https://dados.gov.br` (Brazilian open-data portal).
2. Request an API token: profile area (CKAN-style portal) → **API
   token** tab → copy the issued JWT.
   (If the portal UI no longer exposes it, request via the portal's
   support channel — the API key is issued as a JWT by the portal
   operator.)
3. `.env.test`: `DADOS_GOV_BR_API_KEY=<jwt>`.
4. Verify: `python scripts/verify_connector_creds.py dados`.

## 5. CKAN (already live, needs re-mint after DB re-init)

Not a new credential — but after any CKAN DB re-init the token in
`.env.test` is dead. Re-mint idempotently:

```bash
docker exec hub-test-ckan-app ckan -c /srv/app/ckan.ini user token add admin seed_token
# → write the printed JWT into .env.test: CKAN_TEST_API_KEY=<jwt>
```

(To be automated by `scripts/ensure_ckan_test_token.sh` in Phase 1.1.)

---

## 6. Pilot customer account — Databricks + AWS + dlt (pilot-readiness 2.2)

The FIRST COMPANY PILOT runs on the customer's own estate. Five surfaces
must be acquired and verified — every key goes into `.env.test` (or the
`databricks-pilot` GitHub Environment for the nightly job), NEVER into
the repo. The verifier is `scripts/verify_pilot_creds.py` — it probes
each surface LIVE and never prints a secret.

**THE FIRST-QUERY RULE: budget caps are set and VERIFIED before any
query runs.** `make verify-pilot-creds-gate`
(`verify_pilot_creds.py --strict --require-budgets`) refuses to pass
until the budget probe is green; the nightly workflow runs the gate
before the live suites, so the warehouse-starting tests cannot be
reached without verified caps. Do not run 2.3's live suites until the
gate passes.

### 6.1 Databricks workspace — host + PAT (or M2M SP)

1. In the customer's workspace: **Settings → Developer → Access
   tokens → Manage → Generate new token** (name it e.g.
   `datahub-pilot`, lifetime = pilot duration). Store:
   - `DATABRICKS_PILOT_HOST=<workspace host>` (e.g.
     `dbc-xxx.cloud.databricks.com` — bare host, no scheme)
   - `DATABRICKS_PILOT_TOKEN=<token>`
2. **M2M alternative (preferred for the nightly job):** account admin
   console → **User management → Service principals → Add service
   principal** → grant workspace access → **OAuth secrets** → copy
   `client_id` + `client_secret`. Store `DATABRICKS_PILOT_CLIENT_ID` /
   `DATABRICKS_PILOT_CLIENT_SECRET`. The verifier performs the real
   `client_credentials` exchange (`/oidc/v1/token`, scope=all-apis)
   and prefers the PAT when both are set.
3. **One SQL warehouse:** workspace → **Compute → SQL warehouses** →
   create or pick a warehouse → copy its id:
   `DATABRICKS_PILOT_WAREHOUSE_ID=<id>` (optional:
   `DATABRICKS_PILOT_HTTP_PATH=/sql/1.0/warehouses/<id>` — when set it
   must name the SAME warehouse id).
4. The verifier's `warehouse` probe reads the warehouse STATE only
   (RUNNING/STOPPED) and never starts compute — compute starts in 2.3
   after the budget caps are verified.

### 6.2 AWS keys

Create an IAM user with programmatic access (or a role the pilot
workloads assume) and attach only what the pilot needs:

- `s3:ListBucket`, `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
  scoped to the dlt destination bucket (the verifier proves all three
  with a write/delete roundtrip);
- Athena permissions if the pilot uses Athena (2.3);
- `sts:GetCallerIdentity` comes free — it is the account-identity
  check the verifier reports as `account=<id>`.

Store `AWS_PILOT_ACCESS_KEY_ID` / `AWS_PILOT_SECRET_ACCESS_KEY`
(+ optional `AWS_PILOT_REGION`, default `us-east-1`).

### 6.3 dlt destination

**P1 dev estate (current, 2026-10-05):** the destination is the test
stack's MinIO (`s3://hub-files/`), configured in `.env.test` as
`DLT_PILOT_BUCKET_URL` plus the S3-ONLY overrides — MinIO needs its
OWN credential pair (`AWS_PILOT_S3_ACCESS_KEY_ID/SECRET`, the Athena
identity pair is rejected with `InvalidAccessKeyId`), its own endpoint
(`AWS_PILOT_S3_ENDPOINT_URL=http://localhost:9010`), and its own
region (`AWS_PILOT_S3_REGION`, default `us-east-1` — inheriting
`AWS_PILOT_REGION=eu-central-1` breaks the signature). All three were
live-failure root causes, fixed and pinned (63 contract tests). The
verifier proves a write/delete roundtrip on every gate run.

**Customer AWS bucket (upgrade path):** create the destination bucket
(e.g. `datahub-pilot-dlt-<account-id>`,
with versioning enabled — see the Week-1 backup work) and a prefix for
the pilot tenant:

- `DLT_PILOT_BUCKET_URL=s3://datahub-pilot-dlt-<account-id>/dlt-staging`

The verifier writes and deletes a probe object under
`.datahub-pilot-probe/` in that prefix — the bucket must actually
RECEIVE data, not just exist. (`file://` paths get a local
write/delete check; other schemes FAIL honestly — only s3:// and
file:// are probed.)

**Live finding (2026-10-05):** the pilot AWS pairs (both resolve to
`arn:aws:iam::<account-id>:user/<pilot-iam-user>`) can LIST
the account's buckets but are DENIED direct writes to all three
(bucket names redacted — C1, the identifiers live only in the
gitignored `.env.test`) and cannot create buckets either. A
list-only probe would have missed this — the roundtrip probe caught
it. The fix (console action) is a new bucket plus a bucket policy
granting that user the write path (fill the placeholders with the
real console values):

```bash
aws s3api create-bucket --bucket datahub-pilot-dlt-<account-id> \
  --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1
aws s3api put-bucket-policy --bucket datahub-pilot-dlt-<account-id> --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PilotDltList",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::<account-id>:user/<pilot-iam-user>"},
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::datahub-pilot-dlt-<account-id>"
    },
    {
      "Sid": "PilotDltObjects",
      "Effect": "Allow",
      "Principal": {"AWS": "arn:aws:iam::<account-id>:user/<pilot-iam-user>"},
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::datahub-pilot-dlt-<account-id>/*"
    }
  ]
}'
```

then `.env.test`: `DLT_PILOT_BUCKET_URL=s3://datahub-pilot-dlt-<account-id>/`
and re-run `python scripts/verify_pilot_creds.py dlt` → the existing
keys must now PASS the roundtrip (PASS proves the policy landed).

### 6.4 Budget caps — BEFORE the first query

**Two account classes (STOP-THE-LINE re-scope, 2026-10-05):**

- **Paid account** (account console exists): follow the steps below —
  the guardrail verifies REAL caps and PASS is mandatory.
- **Free-edition account** (P1 dev — no account console, no billing,
  no budget API surface; the probe detects the absent surfaces by
  evidence): declare the re-scope in `.env.test`:
  `PILOT_BUDGET_CAPS_RESCOPE=free-edition-no-billing` → the guardrail
  reports `RESCOPE` on every run (never a silent skip, never a faked
  PASS). When the account becomes paid: remove that line, provide the
  account credentials below, and the same gate verifies real caps.

1. Account console (accounts.cloud.databricks.com) → **Settings →
   Budget policies** → create a policy with a monthly cap; bind it
   **account-wide** or to the pilot workspace only. (If the account
   offers Budgets & Alerts instead of Budget Policies, set both: the
   cap policy is what the guardrail verifies.)

   **Account-level SP — the exact console path (2026-10-05):**
   1. Sign in at accounts.cloud.databricks.com with the ACCOUNT
      owner/admin login (not the workspace login).
   2. **User management → Service principals → Add service
      principal** (name it e.g. `datahub-pilot-guardrail`).
   3. **User management → Groups → account admins → Add members**
      → add the new SP. The budget-policies API is account-admin-only —
      without this the probe gets 401 even with a valid token.
   4. Open the SP → **OAuth secrets → Generate secret** → copy
      `client_id` (applicationId UUID) + `client_secret` (shown once).
   5. The account UUID: the browser URL after sign-in
      (`accounts.cloud.databricks.com/o/<uuid>/…`) — the 36-char
      segment after `/o/`.
2. The guardrail probe needs ACCOUNT-level credentials (workspace
   PATs do not work on the account API):
   - `DATABRICKS_ACCOUNT_ID=<account uuid>`
   - account M2M service principal:
     `DATABRICKS_ACCOUNT_CLIENT_ID` / `DATABRICKS_ACCOUNT_CLIENT_SECRET`
     — or account username/password:
     `DATABRICKS_ACCOUNT_USERNAME` / `DATABRICKS_ACCOUNT_PASSWORD`
   **Live evidence (2026-10-05):** the WORKSPACE M2M SP against the
   account token endpoint (`accounts.cloud.databricks.com/oidc/v1/token`)
   returns HTTP 400 — workspace principals cannot authenticate the
   account API; an ACCOUNT-level principal (or account credentials)
   is mandatory for this probe. **Discriminator (same-day follow-up):**
   an SP created in the WORKSPACE console authenticates the workspace
   token endpoint (HTTP 200) but the account endpoint rejects it
   (HTTP 400) — the SP must be created in the ACCOUNT console
   (accounts.cloud.databricks.com → User management → Service
   principals → Add service principal) and its OAuth secret generated
   THERE (workspace-console-issued secrets for the same SP are also
   rejected). The verifier's budgets probe now appends exactly this
   hint on an account-exchange 400. Also: `DATABRICKS_ACCOUNT_ID` is
   the account's 36-char UUID (account console URL after sign-in, or
   Settings → Account info) — an account NAME will not work.
3. Verify with `python scripts/verify_pilot_creds.py budgets` — PASS
   requires ≥1 policy that is account-wide or bound to the pilot
   workspace (`DATABRICKS_PILOT_WORKSPACE_ID` when binding is used).
   Empty policy list, policies bound elsewhere, or an unavailable API
   surface all FAIL the guardrail.

### 6.5 Verify

```bash
make verify-pilot-creds            # advisory — SKIPs exit 0
make verify-pilot-creds-gate       # --strict --require-budgets — the first-query gate
```

The probes also FAIL fast on **wiring mismatches**: if the live
suites' vars (`DATABRICKS_HOST`, `DATABRICKS_SANDBOX_WAREHOUSE_ID`,
`DATABRICKS_PILOT_HTTP_PATH`) point at a different workspace or
warehouse than the pilot vars, the suites would run against the wrong
account — the verifier refuses before any request. When the pilot
credentials land, export them to those generic names for the 2.3
suite runs (the nightly workflow maps them automatically).

---

## Verification matrix

| Connector | Key(s) | Probe |
|---|---|---|
| Snowflake | SNOWFLAKE_TOKEN | `verify_connector_creds.py snowflake` |
| Stripe | STRIPE_* (test mode) | `verify_connector_creds.py stripe` |
| Azure | AZURE_MARKETPLACE_API_KEY | `verify_connector_creds.py azure` |
| Dados | DADOS_GOV_BR_API_KEY | `verify_connector_creds.py dados` |
| CKAN | CKAN_TEST_API_KEY | `verify_connector_creds.py ckan` |
| Pilot account | `DATABRICKS_PILOT_*`, `DATABRICKS_ACCOUNT_*`, `AWS_PILOT_*`, `DLT_PILOT_BUCKET_URL` | `verify_pilot_creds.py` |

All probes print PASS / FAIL(status) / SKIP(missing key) and never echo
secret values.

---

## 7. Rotation (oss-release-remediation W0.5)

The W0.2 full-history scan found live credential classes in git history.
W0.5 rotates every surface. The D/O rotations are executed (SECRET_KEY,
staging passwords, TLS) — this section covers the **U-gated console
steps**. Each step: perform the console action, update the env file
(never paste a value into a commit message), then run the verify +
dead-check commands. Key names and file paths only — no values are ever
printed by the tooling.

**Window rule:** re-run `python scripts/check_no_live_tests.py`
(guard exit=0) immediately before each console session.

### 7.1 GCP SA key (console)

1. GCP console → IAM & Admin → Service Accounts → the marketplace SA →
   Keys → **Add key** (JSON type). Download the new key.
2. **Delete** the old key ID in the same Keys list.
3. Update `.env.test`: `GCP_CREDENTIALS_JSON` AND
   `GCP_SERVICE_ACCOUNT_JSON` — both must carry the same new JSON (the
   gcp probe fails loudly on a mismatch).

```bash
set -a; source .env.test; set +a
python scripts/verify_connector_creds.py gcp --strict   # expect PASS
python scripts/verify_old_creds_dead.py                 # gcp row: PASS (invalid_grant)
```

### 7.2 AWS pair (console)

1. AWS console → IAM → the pilot/test user → Security credentials →
   **Create access key**.
2. **Deactivate + delete** the old pair.
3. The old pair was ALSO the local MinIO root pair (the identity pairing
   was the leak). The new IAM pair must NOT go into `.env.test`'s
   `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` — those get fresh
   LOCAL-ONLY random values (MinIO has no AWS relation); `AWS_PILOT_S3_*`
   follow. The new IAM pair goes where real AWS is used (`.env.staging`,
   or the pilot vars if that is the rotated account).
4. After the env updates, the guarded MinIO re-init (destructive — the
   window rule + the pre-wipe peer notice):

```bash
python scripts/verify_pilot_creds.py --strict          # aws row: PASS
python scripts/verify_old_creds_dead.py                # aws rows: PASS (STS InvalidClientTokenId-class)
make test-stack-reinit                                 # MinIO volume wipe + CKAN re-mint + strict post-flight
```

### 7.3 Azure SP secret (console)

1. Azure portal → Microsoft Entra ID → App registrations → the
   marketplace SP → **Certificates & secrets → New client secret**.
2. Delete the old secret.
3. Update `.env.test`: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
   `AZURE_CLIENT_SECRET`.

```bash
set -a; source .env.test; set +a
python scripts/verify_connector_creds.py azure-sp --strict   # expect PASS
python scripts/verify_old_creds_dead.py                      # azure row: PASS (invalid_client)
```

### 7.4 Databricks PAT (console)

1. Databricks workspace → User Settings → Developer → Access tokens →
   **Generate new token**.
2. **Revoke** the old token.
3. Update `.env.test`: `DATABRICKS_TOKEN` (and `DATABRICKS_PILOT_TOKEN`
   if the rotated one is the pilot workspace's).

```bash
set -a; source .env.test; set +a
python scripts/verify_connector_creds.py databricks --strict   # expect PASS
python scripts/verify_old_creds_dead.py                        # databricks rows: PASS (403/401)
```

### 7.5 Snowflake PAT (console)

1. Snowflake console → Admin → Users & Roles → the user →
   **Programmatic Access → Create token** (fresh, re-provisioned per the
   W0.5 decision).
2. **Revoke** the old token(s).
3. Update `.env.test`: `SNOWFLAKE_TOKEN`.

```bash
set -a; source .env.test; set +a
python scripts/verify_connector_creds.py snowflake --strict   # expect PASS (SELECT 1)
python scripts/verify_old_creds_dead.py                       # snowflake row: PASS (auth-class failure)
```

### 7.6 Stripe test key (console)

1. Stripe dashboard (Viewing test data) → Developers → API keys →
   **Roll key** for the secret key (and the publishable key).
2. Update `.env.test`: `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`
   (+ webhook secrets if rolled). The compose defaults are already
   env-only — no tracked-tree edit is needed.

```bash
set -a; source .env.test; set +a
python scripts/verify_stripe_test_keys.py --strict   # expect PASS
python scripts/verify_old_creds_dead.py              # stripe rows: PASS (HTTP 401)
```

### 7.7 Close-out

After all six surfaces: `make verify-pilot-creds-gate` exit 0, every
record row flipped `ROTATED`, GATE-51 green, the falsifiability harness
biting on both gate-51 weakenings, and the W0.5 checkbox in
`openspec/changes/oss-release-remediation/tasks.md` ticked.
