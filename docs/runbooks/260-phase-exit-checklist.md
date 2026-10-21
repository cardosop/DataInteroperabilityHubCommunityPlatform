# Phase 260 sub-phase exit checklist

**Phase:** 260 (per-sub-phase — 260.DoD.3)
**Owner:** sub-phase implementer + EM + on-call SRE
**Last reviewed:** 2026-05-07

This is the canonical exit-checklist template every Phase 260 sub-phase
fills in before its DoD.3 line can be marked `[x]`. Copy this file to
`docs/audit-reports/260-<sub-phase>-exit-<YYYY-MM-DD>.md` (e.g.
`260-7J-exit-2026-05-12.md`), fill in the blanks, and link the
artifact in the sub-phase's R-block before requesting sign-off.

The exit-checklist exists because 260.DoD.3 lists ten distinct
post-deploy gates that must EACH be observed for ONE sub-phase. The
default failure mode is "we deployed, didn't see anything explode,
declared victory" — which silently skips the soak window, the canary
ramp, and the retro. This file pins the explicit observations
required at each gate. No mocks, no assumptions; every gate names a
concrete artifact (PR URL, run URL, commit, dashboard snapshot,
incident ID, retro doc) that an auditor can verify after the fact.

## How to use

1. **At sub-phase merge time** — the implementer fills in §1 (code
   merged), §2 (tests green), §3 (artifacts committed), §4 (alerts
   deployed), §5 (dashboards published), §6 (flag flip staging).
2. **Day +1 staging** — implementer + on-call SRE confirm §6 traffic
   metrics are sane.
3. **Day +7 staging soak** — on-call SRE attests §7 (no P1 incidents
   during the 7-day staging soak; the SLO escalation alerts from
   `monitoring/prometheus/alerts/datasets-files.yml` did not auto-page
   or auto-rollback).
4. **Prod canary** — SRE on-call ramps §8 (10% → 100%), confirms each
   ramp step held without regression.
5. **Post-launch retro** — EM + implementer + on-call SRE convene §9
   (retro doc), capture lessons, link from this checklist.
6. **DoD.3 closeout** — once §1-§9 are signed, mark `[x] 260.DoD.3 for
   <sub-phase>` in `openspec/changes/preprod01/tasks.md` (the DoD
   line itself remains a single checkbox; per-sub-phase fan-out is
   tracked in this artifact).

## Sub-phase identity

| Field | Value |
|---|---|
| Sub-phase | _e.g. 260.7.J — Multipart abort + resume tests_ |
| Phase 260 task IDs | _e.g. 260.7.J.1, 260.7.J.R, 260.7.J.R1_ |
| Spec scenarios pinned | _e.g. spec.md::"Bulk dataset purge batches orphan work"_ |
| Implementer | _GitHub username_ |
| EM sign-off | _GitHub username_ |
| On-call SRE | _GitHub username_ |

## §1. Code merged

- [ ] PR merged to `staging`. URL: _PR-XXXX_
- [ ] PR merged to `main`. URL: _PR-XXXX_ (or N/A if staging-only)
- [ ] Merge commit SHA: _commit-SHA_
- [ ] No `--no-verify` / hooks-skipped commits in the PR history
      (verified by `git log --format='%h %s' <range>`).

## §2. Tests green

- [ ] Backend pytest passes locally and in CI.
      Last CI run URL: _action-run-URL_
- [ ] Frontend `tsc` + `eslint` + Playwright passes.
      Last CI run URL: _action-run-URL_
- [ ] New file coverage ≥ 95% line coverage per 260.DoD.1.
      Coverage report URL or attached file: _link_
- [ ] At least one verification scenario from
      `openspec/changes/preprod01/specs/datasets-files/spec.md`
      exercised. Scenario name: _e.g. "Bulk dataset purge batches
      orphan work"_; pinning test:
      _e.g. `hub/apps/datasets/tests/test_orphan_file_cascade.py::test_bulk_dataset_delete_emits_single_orphan_audit`_.

## §3. Runbooks + artifacts committed

- [ ] Runbook(s) under `docs/runbooks/` updated for any new operational
      surfaces. Files: _list_
- [ ] CHANGELOG.md entry under the Phase 260 section
      ([CHANGELOG.md](../../CHANGELOG.md)). Bullet text: _quoted_
- [ ] Feature flag added (default OFF where applicable). Flag name:
      _e.g. `files_enabled`_; default: OFF / ON; rationale: _why_
      (or N/A — explain why no flag).

## §4. Alert rules deployed

- [ ] Alert YAML under `monitoring/prometheus/alerts/` updated /
      created. File: _path_
- [ ] Alert rule deployed to staging Prometheus.
      `kubectl get prometheusrule -n hub-staging` listing this rule by
      name: _name_
- [ ] Alert was synthetically fired in staging (probe-induced) at
      least once to verify Alertmanager routing works end-to-end.
      Synthetic fire timestamp: _ISO-8601_; Alertmanager UI screenshot
      or link: _link_
- [ ] If the rule has `auto_rollback: "true"`: `dry_run: true`
      rehearsal of `auto-rollback-datasets-files.yml` succeeded at
      least once. Workflow run URL: _link_

## §5. Dashboard published

- [ ] Grafana dashboard updated /
      [datasets-files.json](../../monitoring/grafana/dashboards/datasets-files.json)
      includes panels for any new metric this sub-phase emits.
      Panel titles added: _list_
- [ ] Dashboard imports cleanly into the staging Grafana instance.
      Import timestamp: _ISO-8601_; dashboard URL: _meshant-internal.example.com/d/datasets-files_
- [ ] At least one panel shows post-deploy real data (not just an
      empty placeholder query). Screenshot or link: _link_

## §6. Flag flipped staging

- [ ] Feature flag flipped to ON for at least one staging tenant.
      Tenant ID: _UUID_; flip timestamp: _ISO-8601_
- [ ] Smoke tests against staging green within the hour after the
      flip. Most-recent run URL: _link_ (the deploy workflow's `smoke`
      job covers this — see [.github/workflows/deploy.yml](../../.github/workflows/deploy.yml)).
- [ ] No anomalies in error-rate / latency / quota metrics in the 1 h
      after flip (compare panel snapshot pre-flip vs post-flip).

## §7. Soak ≥ 7 days, no P1 incidents

- [ ] 7-day staging soak window: from _ISO-8601_ to _ISO-8601_.
- [ ] During the soak, ZERO P1 incidents touching the sub-phase's
      surface area. (P2 / P3 are non-blocking but should be linked.)
      P2 / P3 incidents during soak: _list of incident IDs_
- [ ] None of the sub-phase's alerts auto-paged on-call during soak
      (or if they did: incident ID + post-mortem link).
- [ ] None of the sub-phase's alerts auto-rolled-back during soak
      (or if they did: rollback workflow run URL + post-mortem link).

## §8. Prod canary 10% → 100%

- [ ] 10% canary ramp: from _ISO-8601_ to _ISO-8601_; tenants /
      traffic share: _description_; rollback criteria: _description_.
- [ ] 25% ramp: from _ISO-8601_ to _ISO-8601_; held without
      regression.
- [ ] 50% ramp: from _ISO-8601_ to _ISO-8601_; held without
      regression.
- [ ] 100% ramp: from _ISO-8601_; observed for at least 24 h.
- [ ] No P1 incidents during the canary ramp.

## §9. Post-launch retro held

- [ ] Retro meeting held at _ISO-8601_; attendees: _list_.
- [ ] Retro doc committed at
      _docs/audit-reports/260-<sub-phase>-retro-<YYYY-MM-DD>.md_.
- [ ] Lessons captured in the sub-phase's R-block in
      [openspec/changes/preprod01/tasks.md](../../openspec/changes/preprod01/tasks.md)
      OR in `MEMORY.md` if cross-phase. Link: _line range or memory
      file_.

## Sign-off

| Role | Name | Date | Notes |
|---|---|---|---|
| Implementer | _username_ | _YYYY-MM-DD_ | |
| EM | _username_ | _YYYY-MM-DD_ | |
| On-call SRE (soak attestation) | _username_ | _YYYY-MM-DD_ | |
| Datasets-Files Engineering Lead | _username_ | _YYYY-MM-DD_ | |

Once all four signatures land, mark `[x]` for the sub-phase under
`260.DoD.3` in `openspec/changes/preprod01/tasks.md` and link this
file from the sub-phase's R-block.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
