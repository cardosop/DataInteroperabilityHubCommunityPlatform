# Structureless Contracts — Phase 227 Runbook

> **Audience**: Platform operators, data-governance engineers, customer-success leads.
> **Phase**: 227 (Wave 0 → Wave 6).
> **Last updated**: 2026-04-30.
> **Owners**: Data Platform Eng + Customer Success.

This runbook covers the diagnosis, customer-coordination, and migration playbook for **structureless data contracts** — contracts whose normalized HubContract carries no models or schema fields. It backs Phase 227 in `openspec/changes/preprod01/`.

---

## TL;DR

A contract is **structureless** when its `hub_contract_json.models[*].fields[]` AND its `hub_contract_json.schema.fields[]` are both empty or missing. Two normalizer bugs (ODPS `outputPorts[]` walker missing, ODCS `properties[]` recursion missing) produced these on staging.

The fix ships in six waves. **You are in Wave 0** unless told otherwise — your job is diagnose, classify, notify.

```bash
# Three-step turn-key Wave 0 (preferred):

# 1. Capture: dated JSONL artefact in audit-reports/.
python manage.py wave0_capture_structureless

# 2. Summarize: markdown triage report (per-tenant, escalation list).
python manage.py wave0_summarize_structureless \
    --input audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl

# 3. Notify (dry-run first; then drop --dry-run).
python manage.py wave0_send_structureless_notifications \
    --input audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl \
    --deadline $(date -d '+14 days' +%Y-%m-%d) \
    --dry-run
```

Each command is a thin wrapper over the canonical predicate in [`hub/apps/contracts/structureless.py`](../../hub/apps/contracts/structureless.py) so the dry-run filter, the human-readable summary, and the customer notification all agree on what "structureless" means. Tests at `hub/apps/contracts/tests/test_wave0_*.py`.

---

## Definition

A normalized HubContract is **structureless** when **none** of the following carry data:

* `hub_contract_json.models[*].fields[]` — at least one model with at least one field
* `hub_contract_json.schema.fields[]` — top-level schema fields (legacy ODCS path)

Source of truth: [`hub/apps/contracts/structureless.py`](../../hub/apps/contracts/structureless.py) — `is_structureless()` and `classify_structureless_contract()`.

---

## Wave 0 — Pre-flight diagnosis

Wave 0 has four operator tasks. Each is rerunnable; running them on a staging-clone DB is preferred (production DB if no clone is available, but only the read-only diagnosis paths).

### 227.0.1 — Capture the structureless population

**Preferred (turn-key)**:

```bash
python manage.py wave0_capture_structureless
```

This command is a thin wrapper that creates `audit-reports/` if missing, names the file with today's date, and runs the dry-run + structureless filter underneath. It also warns on overwrite (re-running the same day is safe but explicit). Pass `--tenant-id <UUID>` to scope to a single tenant.

**Manual equivalent** (if you need a non-default directory or filename):

```bash
mkdir -p audit-reports
python manage.py renormalize_contracts \
    --spec-version 3.1.0 \
    --filter=structureless --dry-run --output=json \
    > audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl
```

**What it does** — selects every `Contract` whose `hub_contract_json` is null or has empty `models = []`, refines per-row using the canonical predicate (`is_structureless()`), and emits one JSONL row per match. The header lines (prefixed `#`) record the run parameters; the trailer line records the scanned and structureless counts.

**JSONL row shape** (sorted keys):

| field | type | description |
|---|---|---|
| `asset_id` | string \| null | Backing asset, if attached |
| `classification` | string | One of `pure_odps_with_outputports`, `odcs_no_schema_block`, `other` |
| `contract_id` | string | Contract UUID |
| `models_count` | int | Number of model entries (often 0 — but see classifier) |
| `original_format` | string | `JSON` or `YAML` |
| `schema_fields_count` | int | Length of `schema.fields[]` |
| `spec_type` | string | `ODCS` or `ODPS` |
| `spec_version` | string | e.g. `3.1.0` |
| `tenant_id` | string \| null | Owner tenant |

**Triage with `jq`**:

```bash
# How many of each classification?
jq -c 'select(.contract_id) | .classification' \
    audit-reports/structureless-pre-rollout-*.jsonl \
    | sort | uniq -c

# Which tenants are affected?
jq -c 'select(.contract_id) | .tenant_id' \
    audit-reports/structureless-pre-rollout-*.jsonl \
    | sort | uniq -c | sort -rn

# All ODCS-no-schema contracts in tenant T:
jq -c 'select(.classification=="odcs_no_schema_block" and .tenant_id=="T")' \
    audit-reports/structureless-pre-rollout-*.jsonl
```

### 227.0.2 — Classify the report

**Preferred (turn-key markdown summary)**:

```bash
python manage.py wave0_summarize_structureless \
    --input audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl \
    --output audit-reports/structureless-summary-$(date +%Y-%m-%d).md
```

The summarizer joins each JSONL row with `Tenant.name` so PMs/CSMs see the owner directly, produces per-classification + per-spec-type breakdowns, ranks tenants by contract-count desc, and **explicitly lists tenants without a TENANT_ADMIN** so you can escalate per §227.0.3 BEFORE running the dispatcher. Output is markdown — paste into the per-tenant CS ticket.

The classifier embedded in `--output=json` already assigns one of three causes to each row. Operator action depends on the class:

| Classification | Cause | Wave-3 self-heal? | Owner |
|---|---|---|---|
| `pure_odps_with_outputports` | ODPS contract whose `outputPorts[]` are present in `original_raw` but the normalizer dropped them. | **YES** — Wave 3 re-normalize will pick up the structure once Phase 227.L1 ports helper ships. | Platform Eng (no customer action) |
| `odcs_no_schema_block` | ODCS contract whose `original_raw` has no `schema:` block, or whose schema lacks resolvable fields. | **NO** — customer must add structure via the Schema editor. | Customer (with T-14 heads-up) |
| `other` | Anything else — likely malformed payload, unsupported spec, or pre-cutover legacy data. | **NO** — operator investigation. | Platform Eng |

Cross-reference the JSONL with tenant ownership data (PMs/CSMs) using the tenant-id column. Flag any row with no tenant_id for direct platform investigation.

### 227.0.3 — Send T-14 heads-up notifications

For tenants with rows of class `odcs_no_schema_block` or `other`, send the **`asset.contract_structureless_pending`** notification at T-14 (14 calendar days before Wave 5 cutover).

**Preferred (turn-key, batch dispatcher)**:

```bash
# 1. Dry-run first — shows the per-tenant fan-out plan, sends nothing.
python manage.py wave0_send_structureless_notifications \
    --input audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl \
    --deadline $(date -d '+14 days' +%Y-%m-%d) \
    --dry-run

# 2. After reviewing dry-run output, drop --dry-run + capture audit trail.
python manage.py wave0_send_structureless_notifications \
    --input audit-reports/structureless-pre-rollout-$(date +%Y-%m-%d).jsonl \
    --deadline $(date -d '+14 days' +%Y-%m-%d) \
    --audit-output audit-reports/structureless-notifications-$(date +%Y-%m-%d).jsonl
```

The dispatcher:

* Groups JSONL rows by tenant.
* **Drift-guards** every contract: re-loads from DB and excludes rows that are no longer structureless (per the canonical predicate). Customers must not receive a notification listing already-remediated contracts.
* **Skips no-admin tenants with a warning** — does not crash. Escalate per the §"What if a tenant has no TENANT_ADMIN?" section below.
* Validates `--deadline` is ISO date AND in the future.
* Writes a per-dispatch audit JSONL when `--audit-output` is given (one row per email: `tenant_id`, `to_email`, `email_type`, `deadline`, `contract_count`, `dispatched_at`).
* Supports `--tenant-id` to scope to a single tenant (re-running for one tenant after an escalation fix).

**Direct API access** (for one-off or scripted callers):

```python
from datetime import datetime, timezone, timedelta
from hub.apps.contracts.models import Contract
from hub.apps.contracts.notifications.structureless import (
    send_structureless_contract_pending_notification,
)
from hub.apps.tenants.models import Tenant

tenant = Tenant.objects.get(id="<TENANT_UUID>")
contracts = list(Contract.objects.filter(
    tenant=tenant,
    id__in=[<list of contract UUIDs from JSONL>],
))
deadline = datetime.now(timezone.utc) + timedelta(days=14)

dispatched = send_structureless_contract_pending_notification(
    tenant=tenant,
    structureless_contracts=contracts,
    deadline=deadline,
)
print(f"Dispatched {len(dispatched)} emails to TENANT_ADMINs")
```

The helper:

* Looks up TENANT_ADMINs via `hub.apps.users.services.get_tenant_admin_users()`.
* Renders the email template `notifications/emails/asset_contract_structureless_pending.html`.
* Enqueues one async send per admin via `send_email_async`.
* Is **fail-soft per recipient** — a single bad email doesn't stop the others.
* **Raises `NoTenantAdminsError`** when no admin exists; investigate and re-grant the role rather than continue.

#### What if a tenant has no TENANT_ADMIN?

1. Stop. Do NOT run the helper for that tenant — it will raise.
2. Identify a contact via the customer-success channel.
3. Re-grant the `TENANT_ADMIN` role via `python manage.py shell`:

   ```python
   from hub.apps.users.models import Role, UserRole
   from hub.apps.users.services import User
   role, _ = Role.objects.get_or_create(tenant_id="<TENANT_UUID>", name="TENANT_ADMIN")
   user = User.objects.get(email="customer-contact@example.com")
   UserRole.objects.get_or_create(user=user, tenant_id="<TENANT_UUID>", role=role)
   ```

4. Re-run the notification helper.
5. Record the manual role grant in the customer-success ticket.

#### Verifying delivery

```sql
-- Email deliveries by type, last 24h:
SELECT email_type, status, COUNT(*)
FROM email_delivery
WHERE email_type = 'ASSET_CONTRACT_STRUCTURELESS_PENDING'
  AND created_at >= NOW() - INTERVAL '24 hours'
GROUP BY email_type, status;
```

Expected: one row per admin per tenant per day, in `SENT` or `DELIVERED` status. Anything in `FAILED` / `DEFERRED` after 30 minutes warrants investigation.

### 227.0.4 — Runbook (this file)

This file. Keep it in sync with the actual command flags + helper signatures. PR review checklist for Wave 0 changes:

- [ ] Did command flags change? Update §227.0.1 examples.
- [ ] Did the JSONL row shape change? Update the table.
- [ ] Did notification helper signature change? Update §227.0.3.
- [ ] Did classification taxonomy change? Update §227.0.2 table.

---

## Customer-coordination playbook

Once T-14 notifications are out, run this two-week soak loop:

| Day | Action | Owner |
|---|---|---|
| T-14 | Send notifications via 227.0.3 helper. Open per-tenant CS tickets. | Platform Eng |
| T-10 | First reminder if no Schema-editor activity logged for the tenant's listed contracts. | CS lead |
| T-7 | Second reminder; offer a CS-pairing call. | CS lead |
| T-3 | Final notice; cite the auto-revert consequence explicitly. | CS lead |
| T-0 | Wave 4 per-tenant validation gate enabled. Wave 5 cutover follows after 30-day clean per-tenant rollout. | Platform Eng |

Reminders use the same template; bump the `deadline` parameter to the tenant's actual remaining window.

---

## Wave 3 — Self-heal pass (post 227.L6 ship)

Once Phase 227.L1 (ODPS outputPorts walker) and L2 (ODCS recursive walker) ship, the `pure_odps_with_outputports` cohort can be self-healed in bulk via the extended `renormalize_contracts --apply` command.

### Resumable, checkpointed self-heal

```bash
python /app/hub/manage.py renormalize_contracts \
    --spec-version=3.1.0 \
    --filter=structureless \
    --apply \
    --tenant-id=<TENANT_UUID> \
    --checkpoint-table=wave3-self-heal-${TENANT_UUID}-$(date +%F) \
    --silent-events \
    --output=json \
    | tee /tmp/self-heal-${TENANT_UUID}-$(date +%F).jsonl
```

| Flag | Purpose |
| ---- | ------- |
| `--apply` | Switches from diagnosis to action — feeds each candidate back through `NormalizationService.normalize_contract`. |
| `--checkpoint-table=<name>` | Per-contract progress in `MigrationCheckpoint` rows partitioned by name. Re-runs with the same name skip already-done contracts (resume after a kill). |
| `--silent-events` | Suppresses per-contract `contract.updated` webhook events; emits a single `CONTRACT_BATCH_RENORMALIZED` audit event with summary counts at the end. Use for runs touching >100 contracts. (See §"Wave 3 outputs" below for the per-batch-per-tenant `contract.batch_renormalized` webhook event that fires regardless of this flag — that's the rollup signal subscribers should subscribe to instead of the per-row stream.) |
| `--output=json` | One JSONL row per processed contract on stdout: `{contract_id, result: healed/residual/failed, asset_id, run_id}`. |
| `--apply-asset-revert` | **Wave 5 only** — see §"Wave 5 — Asset auto-revert" below. |

The summary line at the end of stdout (Phase 227 W3.5):

```text
# {"run_id": "renorm-...", "total_candidates": N, "processed": N,
#   "healed": <count>, "residual": <still_structureless>,
#   "failed": <raised>, "reverted_asset_ids": [...],
#   "per_tenant": {"<tenant_uuid>": {"processed": N, "healed": N,
#                                     "residual": N, "failed": N},
#                   ...},
#   "residue_tenants": ["<tenant_uuid>", ...]}
```

### Wave 3 outputs (subscribers + ops)

The apply path emits these signals — separate from the per-contract
stream — so downstream systems can react to bulk operations without
the per-row storm:

| Signal | Where | When | Payload |
| ------ | ----- | ---- | ------- |
| `CONTRACT_BATCH_RENORMALIZED` audit event | `audit_events` table | Once per run, end of run, when `--silent-events` is set AND `processed > 0`. | Run-level totals + reverted_asset_ids |
| `contract.batch_renormalized` webhook event | Subscribers' webhook URLs | **Once per batch per affected tenant**, regardless of `--silent-events`. Skipped for tenants with no `ACTIVE` webhook subscribed to the event type. | `data: {run_id, tenant_id, processed, healed, residual, failed}`; `resource_type="TENANT"`; `resource_id=<tenant_uuid>` |
| `per_tenant` summary block | stdout JSON summary | End of run. | `{<tenant_uuid>: {processed, healed, residual, failed}}` aggregated across batches |
| `residue_tenants` list | stdout JSON summary | End of run. | Sorted list of `tenant_uuid`s where `residual + failed > 0`. Drives Wave-4 follow-up email scoping. |

Subscribers wanting the per-batch summary subscribe to
`contract.batch_renormalized`. The legacy `contract.updated` event is
suppressed by `--silent-events` to avoid the per-row storm; without
`--silent-events` it still fires per healed row.

#### Driving Wave 4 follow-up emails from `residue_tenants`

```bash
jq -r '.residue_tenants[]' /tmp/self-heal-${TENANT_UUID}-$(date +%F).jsonl \
    | xargs -I{} python /app/hub/manage.py wave4_send_residue_email --tenant-id={}
```

(The `wave4_send_residue_email` driver lands in Wave 4 — the
`residue_tenants` field is the input contract.)

**Resume after kill** — re-running with the same `--checkpoint-table` name skips contracts already marked `done` or `failed`. To force a retry of a `failed` row, delete the checkpoint:

```python
from hub.apps.contracts.models import MigrationCheckpoint
MigrationCheckpoint.objects.filter(
    migration_name="wave3-self-heal-...",
    contract_id="<UUID>",
).delete()
```

### Concurrent runners

The command uses `Contract.objects.select_for_update(skip_locked=True)` per batch — concurrent runners (e.g., parallel RQ workers with the same checkpoint name) silently skip locked rows and pick the next batch. Safe to run multiple workers simultaneously.

### Daily backlog gauge

```bash
python /app/hub/manage.py renormalize_contracts \
    --spec-version=3.1.0 \
    --filter=structureless \
    --dry-run \
    --output=count \
    --tenant-id=<TENANT_UUID>
```

Emits a single integer to stdout (the count of structureless contracts) — pipe to a Prometheus pushgateway script that updates the `contract_structureless_backlog{tenant_id}` gauge. The gauge drives the Grafana dashboard's backlog stat panel.

---

## Wave 5 — Asset auto-revert

For tenants who fail to remediate by T+44, demote ACTIVE assets backed by still-structureless contracts to DRAFT. Each demotion emits `ASSET_AUTO_REVERTED_STRUCTURELESS` audit events recording the prior status.

```bash
python /app/hub/manage.py renormalize_contracts \
    --spec-version=3.1.0 \
    --filter=structureless \
    --apply --apply-asset-revert \
    --tenant-id=<TENANT_UUID> \
    --checkpoint-table=wave5-auto-revert-${TENANT_UUID}-$(date +%F) \
    --silent-events \
    --output=json
```

`--apply-asset-revert` implies `--apply`. Only assets whose currently-active contract REMAINS structureless after re-normalisation are demoted; self-heal successes pass through untouched.

### Rollback (if Wave 5 was applied prematurely)

The L6.4 reverse migration restores assets from the audit-event log:

```bash
python /app/hub/manage.py migrate \
    contracts 0024_unrevert_structureless_assets
```

This reads each `ASSET_AUTO_REVERTED_STRUCTURELESS` event and restores `asset.status = previous_status`. Idempotent — re-running on already-restored assets is a no-op. Emits a paired `ASSET_RESTORED_STRUCTURELESS` event for traceability.

To re-apply the demotion (forward migration → reverse → forward identity round-trip):

```bash
python /app/hub/manage.py migrate contracts 0023_migration_checkpoint
python /app/hub/manage.py migrate contracts 0024_unrevert_structureless_assets
```

---

## Telemetry (Phase 227 L7)

| Signal | Source | What it tells you |
| ------ | ------ | ----------------- |
| `contract_validation_failed_total{code,subcode,spec_type}` | Prometheus | Live rejection rate at the API edge. Spike = customer learned about the gate the hard way; engage support. |
| `contract_structureless_total{spec_type,source}` | Prometheus | Where rejections originate: `creation` (POST), `update` (PATCH), `migration` (`--apply` pass). |
| `contract_structureless_backlog{tenant_id}` | Prometheus (daily cron) | Per-tenant outstanding count. Should drain to 0 by T+30. |
| `contract_normalization_models_count{spec_type}` | Prometheus | Histogram of `len(models)` per successful normalisation — distribution analysis. |
| `contracts_renormalize_batch_duration_seconds{spec_type,outcome}` | Prometheus | `--apply` batch durations + outcome (`healed/residual/mixed/failed`). |
| `audit_events_total{action="ASSET_AUTO_REVERTED_STRUCTURELESS"}` | Prometheus | Wave 5 demotion rate. Should be 0 in steady state. |
| `CONTRACT_STRUCTURELESS_REJECTED` audit events | `audit_events` table | Per-rejection record with subcode + spec_type. Use for compliance reporting. |
| `structural_floor_violation` structlog event | Loki/stdout | WARN-level structured log on every rejection. Carries `contract_id`, `spec_type`, `tenant_id`, `subcode` per spec. |

The **Phase 227 — Structureless Contract Rollout** Grafana dashboard ([`monitoring/grafana/dashboards/structureless-contract-rollout.json`](../../monitoring/grafana/dashboards/structureless-contract-rollout.json)) surfaces all of the above with `tenant_id` and `spec_type` template filters.

---

## Wave-by-wave timeline (Phase 227 doctrine)

| Wave | Action | Timing |
|---|---|---|
| **Wave 0** | Pre-flight diagnosis (this runbook) | T-14 from Wave 1 |
| **Wave 1** | Ship normalizer fixes + Schema editor (gated to internal users) | 2 weeks |
| **Wave 2** | Open Schema editor to all customers; 7-day soak | 1 week |
| **Wave 3** | Self-healing migration — re-normalize structureless contracts | 1 week |
| **Wave 4** | Per-tenant validation gate enable | 1 week per cohort |
| **Wave 5** | Asset auto-revert for residue (only contracts still structureless) | 1 week |
| **Wave 6** | Cleanup — remove feature flags, deprecation telemetry | parallel with W5 |

Reference: `openspec/changes/preprod01/proposal.md` Phase 227 — Six-Wave Rollout.

---

## Verification

Before declaring Wave 0 complete, confirm:

- [ ] Latest dry-run JSONL has zero `pure_odps_with_outputports` rows (Wave 1 deploy completed).
- [ ] Every tenant with `odcs_no_schema_block` or `other` rows has received the T-14 notification.
- [ ] Per-tenant CS tickets exist for every notified tenant.
- [ ] No tenant in the JSONL is missing a TENANT_ADMIN (escalate per §227.0.3).
- [ ] `audit-reports/structureless-pre-rollout-*.jsonl` is checked in to the run-evidence S3 bucket OR the operator's local archive (see runbook of `audit-reports/`).

---

## Failure modes

| Symptom | Root cause | Fix |
|---|---|---|
| Command exits non-zero with `Only --spec-version 3.1.0 is supported` | Wrong spec version flag. | Use `--spec-version 3.1.0`. |
| JSONL has zero rows on a tenant the user expected to see | Their contracts have non-empty `models[]` but missing field detail; predicate refines per-row. | Review `--filter=structureless --dry-run` against the actual `hub_contract_json` payload via a one-off shell. |
| Notification helper raises `NoTenantAdminsError` | Tenant has no admin. | Re-grant role per §227.0.3. |
| Email delivery in `FAILED` after 30 min | SES bounce / SendGrid suppression list hit. | Check `EmailDelivery.error_message`; coordinate with CS to update admin email. |
| Classification = `other` for many rows | Likely malformed payload or unsupported spec. | Per-row investigation; do NOT auto-batch into Wave 3. |

---

## Code references

| Concern | File |
|---|---|
| Predicate + classifier | [hub/apps/contracts/structureless.py](../../hub/apps/contracts/structureless.py) |
| Diagnosis command (raw) | [hub/apps/contracts/management/commands/renormalize_contracts.py](../../hub/apps/contracts/management/commands/renormalize_contracts.py) |
| **Capture wrapper (227.0.1)** | [hub/apps/contracts/management/commands/wave0_capture_structureless.py](../../hub/apps/contracts/management/commands/wave0_capture_structureless.py) |
| **Summarizer (227.0.2)** | [hub/apps/contracts/management/commands/wave0_summarize_structureless.py](../../hub/apps/contracts/management/commands/wave0_summarize_structureless.py) |
| **Batch dispatcher (227.0.3)** | [hub/apps/contracts/management/commands/wave0_send_structureless_notifications.py](../../hub/apps/contracts/management/commands/wave0_send_structureless_notifications.py) |
| Notification helper | [hub/apps/contracts/notifications/structureless.py](../../hub/apps/contracts/notifications/structureless.py) |
| Email template | [hub/apps/notifications/templates/notifications/emails/asset_contract_structureless_pending.html](../../hub/apps/notifications/templates/notifications/emails/asset_contract_structureless_pending.html) |
| Tenant-admin lookup | [hub/apps/users/services.py](../../hub/apps/users/services.py) — `get_tenant_admin_users()` |
| Email type registration | [hub/apps/notifications/models.py](../../hub/apps/notifications/models.py) — `EmailType.ASSET_CONTRACT_STRUCTURELESS_PENDING` |
| OpenSpec proposal | [openspec/changes/preprod01/proposal.md](../../openspec/changes/preprod01/proposal.md) Phase 227 |
| OpenSpec tasks | [openspec/changes/preprod01/tasks.md](../../openspec/changes/preprod01/tasks.md) §227.0 |
| Tests | `hub/apps/contracts/tests/test_structureless.py`, `test_renormalize_structureless_filter.py`, `test_structureless_notification.py`, `test_wave0_capture_command.py`, `test_wave0_summarize_command.py`, `test_wave0_notify_command.py` |
