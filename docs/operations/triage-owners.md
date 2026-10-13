# Triage owners (Phase U / decision 2)

Who acts when CI goes red, a gate trips, or staging pages. Failures must
never float: every class below maps to a bucket with an owner and a
48-hour triage SLA. The default owner for every bucket is `admin`; the
Delegate column is filled when a bucket is handed over (one-line commit).

| Bucket | Scope | Owner | SLA | Delegate |
|---|---|---|---|---|
| backend | `hub/`, migrations, `test-backend`, GATE-12/29 | `admin` | 48 h triage | — |
| frontend | `frontend/`, baseline checker, a11y, e2e batches | `admin` | 48 h triage | — |
| scripts/quality | `scripts/` gates (35/36/38/39/40/41), ratchets, TDD suites | `admin` | 48 h triage | — |
| docs/OSS | `docs/`, openspec, publish pipeline, public tree | `admin` | 48 h triage | — |
| ops / beta on-call | staging/prod infra, alerts, incident response (RB-* runbooks) | `admin` | respond per runbook | — |

Triage procedure: read the failing job's output → map to the playbook class
(`openspec/changes/preprod01/tasks.md`, Phase U, U.2) → fix at root or
annotate with `TICKET=<id> EXPIRES=<YYYY-MM-DD>` (GATE-40) → verify with
the local gate battery before the next push.
