# Asset-creation auto-rollback runbook

**Phase:** 250.DoD.4
**Owner:** Asset-Creation Engineering Manager + SRE on-call
**Last reviewed:** 2026-05-04

## Purpose

Phase 250.DoD.4 mandates an SLO-miss escalation policy:

| Threshold | Duration | Action |
|---|---|---|
| P95 > 2× SLO (= 60 s) | 15 min | Auto-page on-call |
| P95 > 3× SLO (= 90 s) | 30 min | Auto-rollback via `helm rollback` |

This runbook documents the wiring that makes those actions automatic, the
silence procedure that lets a human override the rollback, and the drill
schedule that confirms the path is live.

## Architecture

```
Prometheus rule (monitoring/prometheus/alerts/asset-creation.yml)
    AssetWorkflowDurationP95TwoXSLO        labels: severity=page,    team=asset-creation-eng
    AssetWorkflowDurationP95ThreeXSLOAutoRollback  labels: severity=critical, auto_rollback="true"
        |
        v
Alertmanager (monitoring/alertmanager/alertmanager.yml)
    route auto_rollback=true   -> receiver: asset-creation-auto-rollback
    route severity=page        -> receiver: asset-creation-page-oncall
        |
        v
asset-creation-auto-rollback receiver (webhook)
    -> POST https://api.github.com/repos/<org>/<repo>/dispatches
       event_type=auto-rollback-asset-creation
       client_payload={environment, alertname, reason}
        |
        v
GitHub Actions workflow .github/workflows/auto-rollback-asset-creation.yml
    -> resolve previous helm revision
    -> helm rollback hub <prev-rev>
    -> Slack #incidents notification
```

## Pre-deployment checklist

- [ ] Prometheus rule file `monitoring/prometheus/alerts/asset-creation.yml`
      contains `AssetWorkflowDurationP95TwoXSLO` and
      `AssetWorkflowDurationP95ThreeXSLOAutoRollback` (already merged).
- [ ] Alertmanager `monitoring/alertmanager/alertmanager.yml` has the
      `asset-creation-auto-rollback` and `asset-creation-page-oncall`
      receivers and the matching routes (already merged).
- [ ] GitHub Actions workflow
      `.github/workflows/auto-rollback-asset-creation.yml` exists
      (already merged).
- [ ] GitHub Secrets configured:
      - `AWS_DEPLOY_ROLE_ARN` — IAM role the runner assumes via OIDC.
      - `SLACK_WEBHOOK_URL_INCIDENTS` — incident channel webhook.
- [ ] GitHub Variables configured per Environment:
      - `STAGING_HELM_RELEASE`, `STAGING_K8S_NAMESPACE`
      - `HELM_RELEASE`, `K8S_NAMESPACE`
- [ ] Alertmanager has access to a fine-grained PAT or GitHub App token
      with `actions:write` on this repo, mounted as a sealed secret at
      `/etc/alertmanager/secrets/auto-rollback-token`.
- [ ] Alertmanager has access to the PagerDuty events-v2 routing key,
      mounted at `/etc/alertmanager/secrets/pagerduty-routing-key`.
- [ ] Alertmanager environment exposes
      `ASSET_CREATION_AUTO_ROLLBACK_WEBHOOK_URL=https://api.github.com/repos/<org>/<repo>/dispatches`.

## Drill procedure (must run before flipping production)

The DoD requires the path to be **live**, not just **wired**. To confirm
liveness before relying on it, the team must run the drill twice — once
in staging, once in production — and capture the run URLs in the closeout
audit report.

### Staging drill

1. Pick a low-traffic window (e.g. weekday 14:00 UTC).
2. Manually trigger the workflow with `dry_run=true`:

   ```bash
   gh workflow run auto-rollback-asset-creation.yml \
     --ref main \
     -f environment=staging \
     -f reason="Phase 250.DoD.4 staging drill ($(date -u +%FT%TZ))" \
     -f dry_run=true
   ```

3. Confirm the run resolved a previous revision (look for
   `previous-revision=<n>` in the step output).
4. Confirm Slack `#incidents` received a `dry-run=true` notification.

### Production drill (rehearsal — flag-gated)

1. Schedule a maintenance window with EM + SRE present.
2. Run the workflow with `dry_run=true` against production:

   ```bash
   gh workflow run auto-rollback-asset-creation.yml \
     --ref main \
     -f environment=production \
     -f reason="Phase 250.DoD.4 prod drill ($(date -u +%FT%TZ))" \
     -f dry_run=true
   ```

3. Capture the run URL and previous-revision in the audit report.
4. Verify PagerDuty's test routing key fires in parallel via Alertmanager
   amtool (the page-on-call route).
5. **Do NOT** flip `dry_run=false` in this drill — that's reserved for
   the real rollback. The wiring is proven by a successful dry-run plus
   the in-anger drill done in staging.

### Live-fire path (Phase 250.DoD.4 closeout)

After both drills pass and sign-off is on the audit report, the path is
considered **live**: any subsequent firing of
`AssetWorkflowDurationP95ThreeXSLOAutoRollback` will trigger a real
rollback. There is no separate flag to flip.

## Override procedure (humans always win)

If the on-call wants to **prevent** the auto-rollback after the page
fires (e.g. they've identified the regression and have a hot-fix in
flight), they MUST silence the alert in Alertmanager **before** the
30-minute auto-rollback threshold:

```bash
amtool silence add \
  alertname=AssetWorkflowDurationP95ThreeXSLOAutoRollback \
  --duration=2h \
  --comment "Manual override — hot-fix #<incident-id> in flight"
```

Or via the Alertmanager UI: filter by `auto_rollback="true"`, click
"Silence", set the duration ≥ 2 h, document the reason.

The page-on-call alert continues to fire while the silence is active —
the silence only suppresses the rollback dispatch.

## Failure modes & escalation

| Symptom | First action | Escalation |
|---|---|---|
| Auto-rollback workflow fails to resolve previous revision | Fall back to `helm rollback hub <known-good-rev>` manually | EM + SRE on-call |
| Helm rollback itself fails (release stuck in `pending-upgrade`) | Run `helm rollback --force` per `docs/runbooks/asset-fail-closed-rollback.md` | EM + SRE on-call |
| Slack notification missing after rollback | Check `SLACK_WEBHOOK_URL_INCIDENTS` secret + workflow logs | EM |
| Alertmanager webhook 401/403 | Rotate the `auto-rollback-token` PAT and reseal | SRE on-call |
| 2 unrelated rollbacks in 30 min | The `repeat_interval=30m` routes one alert per 30 min; if more occur, escalate to a real incident | EM + Director |

## Sign-off

| Role | Name | Date | Drill artifacts |
|---|---|---|---|
| Asset-Creation EM | _to be filled_ | _YYYY-MM-DD_ | _GH run URL_ |
| SRE on-call lead | _to be filled_ | _YYYY-MM-DD_ | _GH run URL_ |
| Engineering Director (production drill) | _to be filled_ | _YYYY-MM-DD_ | _GH run URL_ |

250.DoD.4 closes once the staging + production drills are signed off
above and the entries land in
`docs/raci/asset-creation-hardening-signoffs.md`.
