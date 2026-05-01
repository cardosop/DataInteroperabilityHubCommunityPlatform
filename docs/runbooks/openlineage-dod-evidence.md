# OpenLineage F4 — DoD evidence procedures

**Phase:** 228 F4 (228.F4.DoD)
**Owner:** Data Platform Eng + SRE
**Last reviewed:** 2026-05-01

This runbook is the single source of truth for the four DoD items
that require an **operator action + verification** rather than an
automated CI gate. Each section below specifies (a) the action to
take, (b) the evidence to capture, (c) the location to store it.

The two CI-automated DoD items (`DoD.3 k6 SLO`, `DoD.6 round-trip`)
are gated by `.github/workflows/openlineage-f4-dod.yml` — they
produce CI artifacts that this runbook references but does not
duplicate.

## DoD.2 — Marquez deployed, network-policy verified

### Action

1. Cut a deploy from `main` to staging via the existing pipeline:
   `gh workflow run terraform.yml -f env=staging -f component=marquez`.
2. Confirm the pods land:
   ```bash
   kubectl get pods -n marquez -l app.kubernetes.io/name=marquez
   # expect 2/2 Ready
   ```
3. Confirm the NetworkPolicy is enforced. Run from a sidecar-less
   pod in a foreign namespace (the negative case from
   [openlineage-infra.md](../integrations/openlineage-infra.md)):
   ```bash
   kubectl run debug --rm -it --image=curlimages/curl --restart=Never \
       --namespace default -- \
       curl -sS --max-time 5 http://marquez.marquez.svc.cluster.local:5000/api/v1/namespaces
   # expect: connection refused / timeout / 503
   ```
4. Repeat from the Hub namespace (the positive case):
   ```bash
   kubectl exec -n hub-staging deploy/api -- \
       curl -sS http://marquez.marquez.svc.cluster.local:5000/api/v1/namespaces
   # expect: 200 + JSON body
   ```

### Evidence

- Output of steps 2-4, captured into
  `evidence/dod2-marquez-deployed-<YYYY-MM-DD>.txt`
- ArgoCD / Helm release URL in the rollout ticket.

## DoD.4 — DLQ replay runbook exercised in staging

### Action

1. Open Grafana → "OpenLineage DLQ depth" dashboard. Confirm the
   metric `openlineage_dlq_depth{permanently_failed="false"}` has a
   value > 0 from the soak window. If zero, fabricate one row:
   ```bash
   kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
   from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter
   from hub.apps.tenants.models import Tenant
   t = Tenant.objects.first()
   row = OpenLineageDeadLetter(
       tenant=t, event_id='dod4-test', target_url='http://nope.invalid',
       failure_reason='dod4_test', failure_detail='fabricated for runbook',
       attempts=5,
   )
   row.event_payload = {
       'eventType': 'COMPLETE', 'eventTime': '2026-05-01T00:00:00Z',
       'producer': 'https://meshant.com/', 'schemaURL': 'https://openlineage.io/spec/2-0-0/OpenLineage.json',
       'run': {'runId': 'dod4-test'}, 'job': {'namespace': 'dod4', 'name': 'fabricated'},
       'inputs': [], 'outputs': [],
   }
   row.save()
   print(row.id)
   "
   ```
2. Run the replay command, dry-run first:
   ```bash
   kubectl exec -n hub-staging deploy/api -- \
       python manage.py replay_openlineage_dlq --dry-run --max=10 | tee dod4-dryrun.json
   ```
3. Run the actual replay:
   ```bash
   kubectl exec -n hub-staging deploy/api -- \
       python manage.py replay_openlineage_dlq --max=10 | tee dod4-replay.json
   ```
4. Confirm the row's terminal state in the DB:
   ```bash
   kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
   from hub.apps.integrations.openlineage.models import OpenLineageDeadLetter
   row = OpenLineageDeadLetter.objects.get(event_id='dod4-test')
   print(dict(replay_attempts=row.replay_attempts, delivered=bool(row.delivered_at), permafail=row.permanently_failed))
   "
   ```

### Evidence

- `dod4-dryrun.json` + `dod4-replay.json` outputs.
- Terminal state from step 4.
- Stored at `evidence/dod4-dlq-replay-<YYYY-MM-DD>/`.

## DoD.5 — SECURITY.md updated

This DoD item is **always met by code** — `SECURITY.md` lists every
F4 endpoint under "in-scope" + carries the disclosure email +
references the encryption + key-rotation policy. Validation is by
PR review on any change to the file. There is no operational
evidence to capture beyond the PR itself.

## DoD.7 — Flag ON in staging ≥7 days, zero P1

### Action

1. Flip the staging flag ON via the existing capability-flag knob:
   ```bash
   kubectl exec -n hub-staging deploy/api -- python manage.py shell -c "
   from django.conf import settings
   settings.CAPABILITY_FLAGS['lineage.openlineage_export'] = True
   "
   ```
   (Or, the durable knob: set `CAPABILITY_FLAGS_lineage_openlineage_export=true`
   via the staging Helm values + bounce the deploy.)
2. Record the timestamp the flag was flipped:
   `evidence/dod7-soak-start.txt`
3. After **7 calendar days** with the flag ON, query the staging
   incident tracker for any P1 incidents tagged `lineage` or
   `openlineage`:
   ```bash
   gh issue list --label P1,lineage --state all \
       --search "created:>=$(cat evidence/dod7-soak-start.txt)" \
       --json number,title,createdAt,state | tee dod7-p1-list.json
   ```
4. Pass criterion: `dod7-p1-list.json` is `[]` (empty list).
5. Also confirm the canonical metrics show traffic the whole window:
   ```bash
   # Prometheus query — expect non-zero outbound success rate the whole window.
   curl -sS "https://prometheus.staging/api/v1/query_range?query=rate(openlineage_outbound_total%7Bresult%3D%22success%22%7D%5B5m%5D)&start=$(cat evidence/dod7-soak-start.txt)&end=$(date -Iseconds)&step=300" \
       > evidence/dod7-outbound-rate.json
   ```

### Evidence

- `evidence/dod7-soak-start.txt` (epoch).
- `dod7-p1-list.json` (must be `[]`).
- `dod7-outbound-rate.json` (Prometheus screenshot/JSON).

If `dod7-p1-list.json` is non-empty, the soak window resets;
remediate the P1 + restart from step 2.

## DoD.8 — Production rollout 10% → 100%

The rollout uses the existing CAPABILITY_FLAGS Helm values + a
phased Helm rollout. Per project rule we do NOT run Terraform/Helm
locally; the rollout is driven through `gh workflow run deploy.yml`.

### Phase 1 — 10%

1. Update `helm/values-prod.yaml`:
   ```yaml
   api:
     env:
       CAPABILITY_FLAGS_OPENLINEAGE_PERCENT: '10'  # 10% of tenants
   ```
2. Push to `release/f4-rollout-10pct` branch + open a PR.
3. After PR merges + Argo syncs, monitor for 24 h:
   - Grafana → OpenLineage adapter outcomes — `result=dlq` rate
     SHALL be < 0.1% of `result=success`.
   - DLQ depth gauge `openlineage_dlq_depth{permanently_failed="false"}`
     SHALL be < 100 at any sample.
   - `openlineage_inbound_total{result="auth_failed"}` /
     `openlineage_inbound_total{result="accepted"}` ratio < 1%.

### Phase 2 — 50% (after Phase 1 24 h clean)

Same procedure, change percent to `50`. Soak 24 h.

### Phase 3 — 100% (after Phase 2 24 h clean)

Set percent to `100`. Update `docs/integrations/openlineage.md`
front-matter to mark the feature GA.

### Evidence

For each phase, store under `evidence/dod8-rollout-<phase>/`:

- `helm-diff.txt` — the values diff that drove the phase.
- `argocd-sync.txt` — sync confirmation.
- `metrics-screenshot.png` — Grafana dashboard at the 24 h mark.
- `incidents.json` — any P1 / P2 issues opened during the phase.

## Closeout

When all eight DoD items have evidence files in `evidence/`,
update `openspec/changes/preprod01/tasks.md` to mark each item
`[x]` with a path-to-evidence reference, then ship the rollout
announcement.
