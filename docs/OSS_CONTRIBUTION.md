# Contributing to the OSS Core

This repository is the **public core** of the Meshant Data Interoperability
Hub. The paid commercial layer (marketplace, billing, semantic, BaaS, and
the rest of `hub/apps/manifest.py`'s `PAID_APPS`) is **not in this repo** —
it lives in the private repository and is published here as a sanitized
snapshot (see `docs/runbooks/PUBLISH_AND_OPERATIONS.md`).

## Merge-back workflow (public PR → private review → publish)

1. **Public PR.** Open a PR against `mirror/public-core`. CI runs the core
   gates automatically: GATE-29 (core never imports paid), the guard gate,
   the boundary script suites, the core boot smoke, compose overlay parity,
   DCO, and gitleaks.
2. **Private review.** A maintainer imports the change into the private
   repository (where the paid layer exists) and runs:
   * `make publish-check` — boundary + guards + openspec structural gate +
     gitleaks + publish-tree parity
   * the **full-mode** CI suite (paid apps installed) — a core change that
     is green in public CI can still break the paid deployment
3. **Merge + publish.** After both pass, the change merges in the private
   repo and ships with the next `scripts/publish_public.sh` run (the sync
   commit is a full snapshot — see the revert path in
   `docs/runbooks/PUBLISH_AND_OPERATIONS.md`).

## Reviewer checklist — the shared contracts

A core change MUST NOT silently break the paid layer. Reviewers verify:

| # | Contract | Machine-enforced by | What to check |
|---|---|---|---|
| 1 | **`commercial_hooks` signatures** | `tests/unit/test_commercial_hooks_api_contract.py` | No rename/arity/registry-key change without updating `HOOK_API_CONTRACT` in `hub/apps/core/commercial_hooks.py` |
| 2 | **`/capabilities/` wire keys** | `hub/apps/api/tests/test_capabilities.py` | The wire must emit exactly the frontend-consumed keys; the backend suite parses the SPA's `RUNTIME_CAPABILITY_KEYS` from source |
| 3 | **`locked_contract_version` call sites** | `hub/apps/contracts/tests/test_version_allocation_race.py`, `hub/apps/contracts/tests/test_odps_twin_idempotency_race.py` | Every same-asset contract/twin create allocates INSIDE the asset-row lock |
| 4 | **Frontend paid-surface gating** | `frontend/src/app/routes/paidRouteDrift.test.tsx` | Routes/nav must stay capability-gated; a new paid route needs its `PAID_ROUTE_CAPABILITIES` entry |
| 5 | **Guard baseline** | `scripts/check_core_boundary.py` (`--check-guards --check-guard-growth`) | Allowlisted paid imports keep their guards; the baseline only shrinks (net accounting) |
| 6 | **Response shapes** | `frontend/src/shared/utils/paginated.ts` pins | Paginated envelopes normalize at the service/hook boundary — no raw `.results.map` on unnormalized payloads |
| 7 | **Claims must cite a test or gate (P4)** | `scripts/tests/test_w128_doc_claim_veracity.py`, `scripts/tests/test_w93_community_and_veracity.py` | Every doc/contract claim about machinery (make targets, compose ports, docstring importers, idempotency contracts, workflow counts) must cite a test or gate that proves it — a claim with no pin is a bug, not prose |

Runbook links: `docs/runbooks/HOST_SIDE_VERIFICATION.md` (local env),
`docs/runbooks/PUBLISH_AND_OPERATIONS.md` (publish + rollback).
