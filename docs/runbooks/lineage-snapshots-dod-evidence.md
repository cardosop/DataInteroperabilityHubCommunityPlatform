# Lineage snapshots (F5) — DoD evidence procedures

**Phase:** 228 F5 (228.F5.DoD)
**Owner:** Data Platform Eng + SRE
**Last reviewed:** 2026-05-01

This runbook covers the four DoD items that need operator action +
verification rather than an automated gate. The two CI-automatable
items (DoD.2 capacity test + DoD.4 a11y) are run by
`.github/workflows/lineage-snapshots-f5-dod.yml`.

## DoD.2 — Capacity test green; 3-year storage projection within RDS budget

### Action

The capacity simulation runs as a quarterly cron AND on every CI
trigger (against the staging RDS read replica). To run on demand:

```bash
# Pure-math projection — safe on prod (read-only).
kubectl exec -n hub-staging deploy/api -- \
    python tests/load/lineage_history_growth.py \
    --mode=projection
```

### Pass criteria

The script outputs JSON with `overall_ok: true`. This requires:

- `growth_factor_90d ≤ 1.5` (REQ-LIN-F5-005 invariant), AND
- `rds_3y_budget.within_budget == true` (3y projection fits the
  documented `db.r6g.large` 200 GB budget at < 95% utilization).

The script exits 0 on pass, 2 on fail. The CI gate fails the
quarterly check on exit 2.

### Evidence

Output JSON archived as a CI artifact (`f5-dod2-capacity-<run-id>.json`)
+ pasted into the quarterly capacity-review issue.

## DoD.4 — Diff view a11y verified

### Action

Two layers, both automated:

1. **axe-core scan** in [lineage-time-travel.spec.ts](../../frontend/e2e/features/lineage-time-travel.spec.ts)
   targets `[data-testid="lineage-diff-view"]` with WCAG 2 A + AA tags.
2. **Achromatopsia simulation** — manual quarterly review via Chrome
   DevTools "Emulate vision deficiency" → "Achromatopsia". Diff
   buckets must remain distinguishable via icon glyph + label
   (color-blind safe per REQ-LIN-X-002).

### Pass criteria

- E2E suite reports `violations.length === 0` on the diff view scope.
- Manual achromatopsia review captures a screenshot showing each
  bucket distinguishable without color.

### Evidence

- E2E artifact: `playwright-report/.../axe-violations.json`.
- Achromatopsia screenshot: `evidence/dod4-achromatopsia-<YYYY-MM-DD>.png`.

## DoD.5 — Flag ON in staging ≥7 days, zero P1

### Action

1. Flip `lineage.snapshots` ON in staging:
   ```bash
   kubectl set env -n hub-staging deploy/api \
       CAPABILITY_FLAGS_lineage_snapshots=true
   ```
   (Or, durable knob: set in `helm/values-staging.yaml` +
   `gh workflow run deploy.yml -f env=staging`.)
2. Record the flip time:
   `evidence/dod5-soak-start.txt`.
3. After **7 calendar days**, query the incident tracker:
   ```bash
   gh issue list --label P1,lineage --state all \
       --search "created:>=$(cat evidence/dod5-soak-start.txt)" \
       --json number,title,createdAt | tee evidence/dod5-p1-list.json
   ```
4. Pass: `evidence/dod5-p1-list.json` is `[]`.
5. Confirm traffic was non-zero throughout the window:
   ```bash
   curl -sS "https://prometheus.staging/api/v1/query_range?query=rate(lineage_time_travel_queries_total%5B5m%5D)&start=$(cat evidence/dod5-soak-start.txt)&end=$(date -Iseconds)&step=300" \
       > evidence/dod5-traffic.json
   ```

### If non-empty

Each P1 issue resets the soak window — fix the root cause + restart
from step 2. The window is intentionally strict so a 6-day clean
followed by a P1 doesn't pass.

## DoD.6 — Production rollout 10% → 100%

The flag has no per-tenant percentage knob (it's binary on the
deployment), so we phase the rollout via Helm value flips paired
with deploy-time canary cohorts.

### Phase 1 — 10% canary

1. Deploy with `CAPABILITY_FLAGS_lineage_snapshots=true` ONLY for
   the canary cohort (5 internal tenants).
2. 24 h soak. Watch:
   - `lineage_time_travel_queries_total{type="as_of|version"}` increases.
   - `LINEAGE_SNAPSHOT_QUERIED` audit emission rate ≈ point-in-time
     query rate.
   - Error budget on `/lineage/visualization/` stays < 0.1%.
   - Error budget on `/lineage/diff/` stays < 0.1%.

### Phase 2 — 50% rollout

After 24 h clean: extend the cohort to 50% of tenants.

### Phase 3 — 100% GA

After 48 h clean on 50%: enable globally. Update front-matter on
[docs/architecture/lineage-archive-op3.md](../architecture/lineage-archive-op3.md)
to mark F5 as GA.

### Rollback

If any phase trips a stop-condition, flip the flag OFF for that
cohort (`CAPABILITY_FLAGS_lineage_snapshots=false`). The backend
silently ignores `?as_of=`/`?version=` when the flag is off (per
REQ-LIN-F5-001 spec rule), so existing graph queries continue
without any user-facing breakage.

### Evidence per phase

Stored at `evidence/dod6-phase{1,2,3}/`:

- `helm-diff.txt` — values diff that drove the phase.
- `argocd-sync.txt` — sync confirmation.
- `metrics-screenshot.png` — Grafana at the soak end.
- `incidents.json` — P1/P2 issues opened during the phase.
- `audit-counts.json` — count of `LINEAGE_SNAPSHOT_QUERIED` rows
  emitted per tenant during the phase (proves real usage, not just
  flag-flipped).

## Closeout

When all six DoD items have evidence files, update
`openspec/changes/preprod01/tasks.md` to mark each item `[x]` with
the path-to-evidence reference.
