# History-rewrite maintenance window (P2-2)

The force-push of the rewritten history to origin and everything that
follows it, executed as ONE window through
`scripts/run_history_rewrite_window.py` (the runner) — a one-shot
execution tool whose step ORDER machine-enforces the G12 contract:
origin push protection is enabled AFTER the force-push lands and the
post-push sweep is green, never before, never during.

## Preconditions (before the window opens)

1. **Rotations complete:** `python scripts/check_history_rotation_map.py`
   exits 0 (GATE-65 — every credential class carries dated dead-value
   evidence; the 3 U-console surfaces must be flipped to ROTATED).
2. **Rewrite inputs regenerated:** `make rewrite-inputs-build` produced
   `fragments.txt` + `replace.txt` (the P2-0 chain — the build refuses
   while any rotation is blocked).
3. **Rewritten mirror built:** the P2-1 `git filter-repo` run over the
   current refs, verified by
   `python scripts/verify_history_rewrite.py --repo <fresh-clone>
   --fragments <fragments> --gitleaks` (fsck clean, every fragment
   unreachable, the gitleaks-over-history pass green).
4. **Zero live pytest:** `python scripts/check_no_live_tests.py` exits
   0 (the runner re-runs it immediately before the push — the guard
   contract from the W0.3 window notice).
5. **Peers notified:** the ListAgents check with the outcome recorded
   in the maintenance-window notice (GATE-50's contract).

## The window (the runner does all of it)

```bash
python scripts/run_history_rewrite_window.py \
    --fragments <REWRITE_INPUTS_DIR>/fragments.txt \
    --mirror <P2-1-mirror.git> \
    --remote origin \
    --confirm-force-push
```

Ordered steps (any failure HALTS the run before the next destructive
step):

1. `zero-live-pytest` — the guard re-run.
2. `rotation-gate` — GATE-65 must be green.
3. `inputs-ready` — the fragments file exists and carries entries.
4. `mirror-ready` — the mirror is a git repository.
5. `pre-window-push-protection` — `check_push_protection.py check
   --remote origin --expect disabled`: an enabled origin blocks the
   rewritten push mid-flight (G12). If it reports enabled: STOP and
   resolve before the window.
6. `force-push` — `git push --force <mirror> origin refs/heads/*`.
7. `post-push-sweep` — `sweep_remote_fragments.py` clones a fresh
   mirror of the remote and runs `git log --all -S <fragment>` per
   fragment (fragments named by index only — values never printed).

**If the sweep finds a reachable fragment:** the window HALTS. The
object survives outside the pushed refs (dangling-object retention /
PR refs / caches). Open a GitHub support ticket asking for
dangling-object retention — cite the fragment indexes, never the
values — and do NOT enable push protection until the ticket resolves
or the sweep is green.

8. `refs-cleanup` — `cleanup_origin_refs.py --execute`: closes the
   open PRs (their heads still reference the old SHAs — server-side
   `refs/pull/*` survive mirror deletion, G4) and deletes the stale
   `dependabot/*` branches that fork the tainted lineage. The pushed
   heads (main, prepro01, staging, release/mvp-v1) are never touched
   (pinned).
9. `actions-review` — `review_actions_artifacts.py` plan: the
   workflow runs + artifacts classified into the value-carrier class
   (trace/network/junit/E2E recordings). Purge decisions:
   - carrier-class artifacts from pre-rewrite runs: delete via
     `gh api -X DELETE repos/OWNER/REPO/actions/artifacts/<id>` after
     recording names in the window record;
   - a suspect run's LOGS: `review_actions_artifacts.py --inspect-run
     <id> --out-dir <dir>` downloads and gitleaks-scans the log
     archive (findings named by rule/file, values never printed);
     flagged runs are deleted via
     `gh api -X DELETE repos/OWNER/REPO/actions/runs/<id>`.
10. `enable-push-protection` — `check_push_protection.py set --remote
    origin --state enabled` + `check --remote origin --expect
    enabled` (G12: origin AFTER, never during).

## Peer re-clone recipe (after the push)

1. Peers re-clone the repository (never fetch/merge the old SHAs
   back — pushing the OLD ancestry re-introduces the scrubbed
   history, stop-the-line).
2. The dev checkout: fetch the rewritten refs; rebase the unpushed
   local commits onto the rewritten `prepro01`.
3. Verify: `scripts/verify_history_rewrite.py --repo <clone>
   --fragments <fragments> --gitleaks` (or `make
   verify-history-rewrite`).

## Failure playbook

- Guard refuses → wait for the live run to finish; re-run the guard.
- GATE-65 red → the rotations are not complete; close them first.
- Pre-window check mismatch → resolve the enabled origin (GitHub
  settings) before re-running.
- Force-push rejected mid-flight → re-run the runner (the steps are
  idempotent; the pre-window check re-proves the state).
- Sweep finds fragments → the support-ticket path above.
