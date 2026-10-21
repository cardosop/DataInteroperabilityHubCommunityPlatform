# Audit Tamper-Evidence Operations Runbook (Phase 234)

This runbook covers the on-call operational flow for the audit-trail
tamper-evidence stack delivered across Phase 234:

| Sub-phase | Mechanism                                                                              |
| --------- | -------------------------------------------------------------------------------------- |
| 234.1     | Per-tenant SHA-256 hash chain on `AuditEvent` (chain_sequence + prev_chain_hash + chain_hash) |
| 234.1.5   | Hourly Merkle snapshots signed + uploaded to S3 Object Lock                            |
| 234.1.8   | `GET /api/v1/audit/integrity/verify` endpoint                                          |
| 234.3     | `archive_old_audit_events` (3y default retention; per-event-type overrides from 234.5) |
| 234.4     | `audit_permanent_delete_sweep` (90-day grace after archive; GDPR-erasure tolerant)     |
| 234.6     | Postgres FTS on `details_json_tsvector`                                                |
| 234.7     | Observability — metrics, dashboard, alerts (this runbook)                              |

The on-call triage flows that follow assume you have:

- AWS CLI configured against the cluster's audit-merkle S3 bucket
- `kubectl` access to the namespace (e.g. `hub-staging` / `hub-prod`)
- Read access to the audit Grafana dashboard
  ([`monitoring/grafana/dashboards/audit-health.json`](../../monitoring/grafana/dashboards/audit-health.json))
- An on-call shell into a hub API pod (or `manage.py shell` access)

---

## Alert: `AuditChainBreakDetected`

**Severity:** critical (PagerDuty).
**Signal:** `audit_chain_break_total` incremented in the last 5 minutes.

This is the **load-bearing tamper-evidence signal**. There is no noise
floor — any positive value is a real detection from the verifier
(in-row or Merkle cross-check).

### Triage flow

1. **Read the alert labels.** `reason` is one of:
   - `chain_hash_mismatch` — a row's stored `chain_hash` does not
     match what we recompute from its on-disk content +
     `prev_chain_hash` + timestamp. **Content tamper**: the row was
     edited after insert.
   - `prev_link_mismatch` — two consecutive rows (no gap between
     them) where row N's `prev_chain_hash` ≠ row N−1's
     `chain_hash`. **Splice/insertion**: a row was inserted between
     two existing rows.
   - `snapshot_root_mismatch` — the per-window Merkle root recomputed
     from current rows does not match the signed root stored in
     `AuditMerkleSnapshot.root_hex`. **Full-chain rewrite forensic**:
     every in-row link is internally consistent but doesn't match
     the cryptographic anchor in S3 Object Lock.

2. **Find the affected row(s).** The verifier endpoint surfaces the
   mismatch list directly. Hit it as a `PLATFORM_ADMIN`:

   ```bash
   curl -s -H "Authorization: Bearer $PA_TOKEN" \
     "https://api.${ENV}meshant-internal.example.com/api/v1/audit/integrity/verify\
?tenant_id=${TENANT_ID}&include_snapshots=true" | jq .
   ```

   Response:

   ```json
   {
     "verified": false,
     "checked": 12345,
     "mismatches": [{"event_id": "...", "chain_sequence": 42, "reason": "..."}],
     "gaps": [],
     "snapshots_checked": 6,
     "snapshot_mismatches": []
   }
   ```

3. **Pull the offending row's history.** Using the `event_id` from
   step 2, query the meta-audit emitted alongside the alert:

   ```sql
   SELECT id, action, details_json, timestamp
     FROM audit_events
    WHERE action = 'AUDIT_INTEGRITY_MISMATCH'
      AND details_json -> 'mismatches' @> '[{"event_id":"<the-uuid>"}]'::jsonb
   ORDER BY timestamp DESC
    LIMIT 5;
   ```

4. **Cross-check the Merkle snapshot.** For a single-row mismatch
   inside a snapshot window, the signed root in S3 is the ground
   truth. The window the offending row belongs to:

   ```sql
   SELECT id, period_start, period_end, root_hex, signature_hex,
          s3_bucket, s3_key, s3_version_id
     FROM audit_merkle_snapshots
    WHERE tenant_id = '<tenant>'
      AND period_start <= '<row-timestamp>'
      AND period_end   >  '<row-timestamp>'
    LIMIT 1;
   ```

   Then download the proof JSON via S3:

   ```bash
   aws s3api get-object \
     --bucket meshant-${ENV}-audit-merkle-roots \
     --key "<the-s3_key>" \
     --version-id "<the-s3_version_id>" \
     /tmp/proof.json
   jq . /tmp/proof.json
   ```

   The proof JSON is signed; verify the signature locally before
   trusting any field on it.

5. **Containment.** Tamper-evidence is a *detection* system, not a
   prevention one — by the time you see the alert, the offending
   write already happened. Do NOT attempt to "fix" the row. The
   correct response is:
   - Capture the in-DB row state to a forensic snapshot
     (`pg_dump --table=audit_events --where='id IN (...)'`).
   - File a security incident ticket; loop in legal+DPO.
   - Quarantine the writer account (DB role, app pod, or API key)
     suspected of the write — pull `pg_stat_activity` + the closest
     surrounding audit rows for IP/actor correlation.

### Test: forge an audit row → verify endpoint detects it

This is the production smoke-test scenario from
[`tasks.md`](../../openspec/changes/preprod01/tasks.md) §234.DoD.5.

```bash
# 1. Get any tenant-scoped audit row id:
EVENT_ID=$(kubectl exec -it $POD -- python hub/manage.py shell -c "
from hub.apps.audit.models import AuditEvent
print(AuditEvent.all_objects.first().id)
")

# 2. Forge content by raw SQL (bypasses model save guard):
kubectl exec -it $POD -- python hub/manage.py dbshell -- -c "
UPDATE audit_events
   SET details_json = jsonb_set(details_json, '{forged}', 'true')
 WHERE id = '$EVENT_ID';
"

# 3. Within 1 hour the verifier endpoint should surface this row in
#    ``mismatches`` AND the AuditChainBreakDetected alert should fire.
curl -s -H "Authorization: Bearer $PA_TOKEN" \
  "https://api.${ENV}meshant-internal.example.com/api/v1/audit/integrity/verify" \
  | jq '.verified, .mismatches[0]'
# Expected:
#   false
#   {"event_id": "<EVENT_ID>", "reason": "chain_hash_mismatch", ...}
```

After the smoke test, restore the row (raw SQL again — the model
guard would block) and re-run the verifier to confirm clean state.

---

## Alert: `AuditMerkleSnapshotSlow`

**Severity:** warning.
**Signal:** `audit_merkle_snapshot_duration_seconds` p99 > 30s for 10m.

### Triage

1. **Confirm the slow surface.** The histogram covers
   hash-tree build + signing + S3 PUT. Hash + sign is sub-second
   for any plausible tenant volume, so a sustained p99 > 30s is
   almost always the S3 PUT.

2. **Check S3 latency.** AWS dashboard for the
   `meshant-${ENV}-audit-merkle-roots` bucket → `PutObject` p99.
   If elevated there too, this is an S3 incident — accept the
   alert until AWS recovers.

3. **Check IAM throttle.** If S3 p99 is normal but ours is high,
   look for `403 SlowDown` in the API pod logs.

4. **Re-snap an affected window.** Once the upstream recovers,
   any window where the upload failed but the DB row was reserved
   can be re-uploaded via:

   ```bash
   kubectl exec -it $POD -- python hub/manage.py \
     audit_merkle_snapshot_sweep --tenant-id <uuid> --skip-job-row
   ```

   The snapshot pipeline is idempotent — the existing DB row is
   re-used and only the missing S3 PUT is retried.

### Merkle snapshot slow {#merkle-snapshot-slow}

Cross-reference to the alert above; this anchor is what the alert
`runbook` label points at.

---

## Alert: `AuditSearchSlow`

**Severity:** warning.
**Signal:** `audit_search_query_duration_seconds` p95 > 5s for 5m.

See [`docs/runbooks/audit-search-rollout.md`](audit-search-rollout.md)
for the full GIN-index health triage (the search subsystem has its
own runbook because the rollout itself is a multi-deploy operation).

### Audit FTS slow {#audit-fts-slow}

Cross-reference target for the alert.

The TL;DR triage:

1. `pg_stat_user_indexes` — confirm `audit_events_details_tsv_gin`
   is still being used.
2. `\di+ audit_events_details_tsv_gin` — index size growth >2× the
   baseline → schedule
   `REINDEX INDEX CONCURRENTLY audit_events_details_tsv_gin`.
3. `pg_stat_activity` for long-running queries with
   `details_json_tsvector` in the text — a single tenant may be
   dominating.

---

## Alert: `AuditRetentionPurgeBatchUnusuallyLarge`

**Severity:** warning.
**Signal:** > 100k rows purged in a single hour for one tenant.

### Retention batch unusually large {#retention-batch-unusually-large}

Cross-reference target for the alert.

### Triage

1. **Verify the policy.** Pull the
   `AuditEventRetentionPolicy` rows for the tenant:

   ```sql
   SELECT id, event_type, retention_days, regulation_keys, enabled, updated_at
     FROM audit_event_retention_policies
    WHERE tenant_id = '<uuid>';
   ```

   A row with `updated_at` close to the alert timestamp + a
   shortened `retention_days` correlates the alert to a deliberate
   policy change (CCPA override applied retroactively, etc.).

2. **Check the AUDIT_RETENTION_PURGED meta-audit.** It carries
   the deleted-id sample for forensic reconciliation:

   ```sql
   SELECT details_json
     FROM audit_events
    WHERE action = 'AUDIT_RETENTION_PURGED'
      AND tenant_id = '<uuid>'
    ORDER BY timestamp DESC
    LIMIT 1;
   ```

3. **Confirm with the tenant.** Large purges are usually
   policy-driven — but a malicious admin or compromised TENANT_ADMIN
   could have flipped a policy to mass-delete history. If the policy
   change wasn't expected, treat as a tamper incident and follow the
   `AuditChainBreakDetected` containment steps.

---

## Alert: `AuditRetentionSweepStalled`

**Severity:** critical (PagerDuty).
**Signal:** no purge observations for >36h.

### Retention sweep stalled {#retention-sweep-stalled}

Cross-reference target for the alert.

### Triage

1. **Kubernetes CronJob status.**

   ```bash
   kubectl get cronjobs -n hub-${ENV} audit-permanent-delete-daily
   kubectl get jobs -n hub-${ENV} -l job-name~="audit-permanent-delete-daily-*" \
     --sort-by=.metadata.creationTimestamp | tail -5
   kubectl logs -n hub-${ENV} job/<latest> --tail=200
   ```

2. **Job row table.** Even when the CronJob ran, the work-function
   may have raised before any deletions happened:

   ```sql
   SELECT id, status, started_at, completed_at, error_message
     FROM jobs
    WHERE type = 'AUDIT_PERMANENT_DELETE_SWEEP'
    ORDER BY started_at DESC
    LIMIT 10;
   ```

3. **Force-run.** Once the bug is fixed (or as a stop-gap), trigger
   the sweep manually:

   ```bash
   kubectl exec -it $POD -- python hub/manage.py \
     audit_permanent_delete_sweep --dry-run --skip-job-row
   # Then without --dry-run if the dry-run looks right.
   ```

   The 90-day grace window means a few days of catch-up is safe;
   the regulatory exposure compounds beyond ~7 days though, so
   move on this within one business day even if it took a week to
   detect.

---

## On-call quick reference

| Symptom                           | Alert                                    | Severity | Page? |
| --------------------------------- | ---------------------------------------- | -------- | ----- |
| Chain hash mismatch               | `AuditChainBreakDetected`                | critical | yes   |
| Snapshot root mismatch            | `AuditChainBreakDetected` (reason)       | critical | yes   |
| Merkle snapshot pipeline slow     | `AuditMerkleSnapshotSlow`                | warning  | no    |
| FTS search slow                   | `AuditSearchSlow`                        | warning  | no    |
| Retention sweep stopped running   | `AuditRetentionSweepStalled`             | critical | yes   |
| Retention purge unusually large   | `AuditRetentionPurgeBatchUnusuallyLarge` | warning  | no    |

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
