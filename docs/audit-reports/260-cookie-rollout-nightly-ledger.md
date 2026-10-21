# Phase 260.B cookie rollout — 14-day nightly regression ledger

**Phase:** 260.B Acceptance #5
**Owner:** Auth Engineering Lead + SRE on-call
**Last reviewed:** 2026-05-05

## Purpose

Phase 260.B Acceptance #5 gates the production HttpOnly-cookie default-on
flip on 14 **consecutive** clean nightly CLI/SDK regression runs against
staging. This file is the authoritative ledger: each row is a nightly
run, each cell records the outcome.

The infrastructure that produces these rows is
[`.github/workflows/cli-sdk-nightly-regression.yml`](../../.github/workflows/cli-sdk-nightly-regression.yml).
That workflow runs at 03:30 UTC every night against the staging
deployment and posts a structured summary; this file is appended to by
the on-call engineer reviewing the workflow run each morning.

## Recording protocol

1. Each morning, the on-call (or release rotation) engineer opens the
   most recent workflow run from the GitHub Actions tab.
2. If the run is **green** (CLI + SDK + cookie smoke all `success`),
   append a new row to the table below with the run date, the run URL,
   and `green`.
3. If the run is **red** (any job failed), append a new row with `red`,
   the failing job name(s), and a 1-line root-cause hypothesis. **The
   countdown resets to 0** — the 14-day window restarts on the next
   green night.
4. Sundays / public holidays still count: the workflow runs unattended;
   record outcomes whenever the run completed.
5. Once 14 consecutive `green` rows are recorded, sign the closure block
   below and proceed to
   [docs/runbooks/260-cookie-rollout-production-flip.md](../runbooks/260-cookie-rollout-production-flip.md).

## Closure criteria

- 14 consecutive rows with outcome `green`.
- No row in those 14 days references an open auth/cookie/lockout
  regression in the failing-jobs column.
- SRE on-call attestation that staging has had no auth-related
  P1/P2 incidents in the same window (cross-checked against the
  incident tracker).

## Run ledger

| #  | Run date (UTC) | Workflow run | Outcome | Failing jobs / notes | Recorded by |
|----|----------------|--------------|---------|----------------------|-------------|
| 1  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 2  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 3  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 4  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 5  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 6  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 7  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 8  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 9  | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 10 | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 11 | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 12 | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 13 | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |
| 14 | _YYYY-MM-DD_   | _link_       | _green/red_ | _—_              | _name_      |

If a `red` row appears, **truncate the count to zero**, append a
`---` separator below the red row, and start the next row at 1 again.
Do not delete red rows — they are the audit trail of why the flip is
gated.

## Closure block

| Role | Name | Date | Attestation |
|---|---|---|---|
| Auth Engineering Lead | _to be filled_ | _YYYY-MM-DD_ | 14 consecutive green rows verified |
| SRE on-call lead | _to be filled_ | _YYYY-MM-DD_ | No auth-related P1/P2 in window |
| Engineering Manager | _to be filled_ | _YYYY-MM-DD_ | Production flip authorised |

Once all three signatures are in place, 260.B Acceptance #5 closes and
the production cookie flip per
[docs/runbooks/260-cookie-rollout-production-flip.md](../runbooks/260-cookie-rollout-production-flip.md)
is unblocked.
