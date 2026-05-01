# Marquez outage runbook

**Phase:** 228 F4 (228.F4.25)
**Owner:** Data Platform Eng + SRE
**Severity:** P1 (Marquez unreachable >5 min) / P0 (Marquez data loss)
**Last reviewed:** 2026-04-30

## Detection

Marquez is the OP-1 (sole official producer) for Phase 228 OpenLineage. Outage signals:

1. `LineageQueryHighP99Latency` alert (p99 > 1s sustained 5m).
2. DLQ pending count climbs sharply (see `openlineage-dlq-replay.md`).
3. Customer reports "Marquez UI down" or "lineage events not appearing".
4. Direct probe fails: `curl https://marquez.example.com/api/v1/namespaces`.

## Triage

### Step 1 — Verify the outage is Marquez, not us

```bash
# From a Hub pod:
kubectl exec -n hub-staging deploy/api -- curl -sS \
  -o /dev/null -w '%{http_code}\n' \
  http://marquez.marquez.svc.cluster.local:5000/api/v1/namespaces

# Expected: 200. Anything else → Marquez issue.
```

If Hub pod can't resolve Marquez, the issue is networking (VPC peering, NetworkPolicy, mTLS cert). See "Network mitigations" below.

If Hub resolves Marquez but gets 5xx, the issue is Marquez itself.

### Step 2 — Check Marquez pod state

```bash
kubectl -n marquez get pods
kubectl -n marquez describe pod <marquez-pod>
kubectl -n marquez logs <marquez-pod> --tail=200
```

Common patterns:

- **OOMKilled** — bump memory in the Helm values (see `marquez-upgrade.md` for the chart).
- **CrashLoopBackOff after a Marquez release** — pin the previous chart version + redeploy.
- **DB connection pool exhausted** — Marquez's RDS Postgres needs a `max_connections` bump or a connection-pooler (PgBouncer).

### Step 3 — Stop the bleeding

While Marquez is down, the Hub adapter dead-letters events. To
prevent the DLQ from saturating:

```bash
# Disable the OpenLineage capability flag — server-side gate that
# returns 404 from /events/ and /keys/ endpoints + skips outbound
# adapter dispatch from the contract-save signal.
kubectl -n hub-staging set env deploy/api \
    CAPABILITY_FLAGS='{"lineage.openlineage_export": false}'
```

Once Marquez is healthy, re-enable + replay:

```bash
kubectl -n hub-staging unset env deploy/api CAPABILITY_FLAGS
python /app/hub/manage.py replay_openlineage_dlq --max=10000
```

## Recovery

### Restore from PITR

If Marquez data is lost (RDS issue) but pods are healthy:

1. Open the Marquez RDS Postgres in the AWS console.
2. Restore from the latest PITR snapshot per the platform DR runbook (`destroy-staging.md` § "RDS PITR").
3. Update Marquez's `DATABASE_URL` to point at the restored instance.
4. Wait for the restore-cluster reconcile.
5. Run `python /app/hub/manage.py replay_openlineage_dlq --max=100000` to refill from the Hub-side DLQ.

### Network mitigations

If Hub ↔ Marquez fails at network layer:

- **NetworkPolicy** — ensure `helm/templates/network-policy-marquez.yaml` allows the `hub-api` namespace.
- **mTLS** — verify the cert in `meshant/staging/openlineage/mtls_cert` is valid (90-day rotation per 228.F4.14).
- **DNS** — `kubectl exec` from a Hub pod and `nslookup marquez.marquez.svc.cluster.local`.

## Escalation

| State | Severity | Action |
|---|---|---|
| Marquez 5xx for <5 min | P3 | Watch DLQ growth. |
| Marquez unreachable 5–30 min | P1 | Page on-call; disable capability flag if DLQ is filling fast. |
| Marquez data loss / corruption | P0 | PITR restore + replay. Notify customer-success. |

## Related

- [DLQ replay runbook](openlineage-dlq-replay.md)
- [Quarterly Marquez upgrade](marquez-upgrade.md)
- [OpenLineage integration doc](../integrations/openlineage.md)
- Helm chart: `helm/templates/openlineage-adapter.yaml`
