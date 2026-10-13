# RB-SEC-003 — Databricks Egress + Credential Rotation Runbook

**Owner**: Platform Engineering  
**Last reviewed**: 2026-09-16  
**Next review**: 2026-12-16  

## Scope

This runbook covers the two operational surfaces of the Databricks
control plane (openspec `add-databricks-control-plane`, Phase 9):

1. **Egress** — the network allowlist for the Hub platform and for the
   nightly live-CI runner (`.github/workflows/databricks-e2e-nightly.yml`).
2. **Credential rotation** — the OIDC trust setup for the nightly
   workflow's GitHub-federated credentials, the rotation cadence for the
   `DATABRICKS_E2E_*` GitHub secrets, and the tenant-side workspace
   credential rotation.

General platform credential rotation (INTERNAL_API_KEY, warehouse
credentials for all providers, webhook keys) lives in
[RB-SEC-001](RB-SEC-001-credential-rotation.md).

## Egress allowlist

### Allowed Databricks host families

The Hub accepts only these host families — enforced by the SSRF
validator (`hub/apps/databricks_admin/validation.py`,
`ALLOWED_DATABRICKS_HOST_SUFFIXES`) and mirrored by the platform's
NetworkPolicy egress allowlists:

- `helm/templates/networkpolicy/allow-warehouse-egress.yaml` — the
  api/worker pods' warehouse-vendor egress (task 0.14).
- `helm/templates/networkpolicy/allow-databricks-snapshot-egress.yaml` —
  the Delta Sharing snapshot sweep CronJob pod's 443 egress (the pod is
  the snapshot executor: workspace source read + Hub S3 write), with the
  host families rendered into the policy's
  `databricks-snapshot-egress-host-families` annotation.
- `helm/templates/networkpolicy/allow-databricks-cronjobs.yaml` — the
  four Databricks recurring-job CronJob pods' internal dependencies
  (DNS, PgBouncer, Redis).

| Host family suffix | Example |
|---|---|
| `.cloud.databricks.com` | `adb-1234567890.1.azuredatabricks.net`-style AWS/Azure workspaces use `.cloud.databricks.com` or the Azure family below |
| `.azuredatabricks.net` | `adb-1234567890.1.azuredatabricks.net` |
| `.gcp.databricks.com` | `1234567890.1.gcp.databricks.com` |
| `.databricks.us` | `adb-1234567890.1.databricks.us` (FedRAMP/Gov) |

- Workspace API calls go to the tenant's registered workspace host
  (one of the families above); the account API goes to
  `accounts.cloud.databricks.com`.
- Adding a NEW host family requires BOTH surfaces: the validation
  suffix tuple and the NetworkPolicy allowlist entry (the two are
  reviewed together — a host the validator rejects is unreachable
  anyway).

### Nightly runner egress

The GitHub Actions runner for the nightly workflow reaches:

1. `accounts.cloud.databricks.com` — the account API (workspace
   create/list/delete, metastore delete) via the OIDC-federated
   `DATABRICKS_E2E_ACCOUNT_TOKEN`.
2. The sandbox workspace host (a `meshant_e2e_*` workspace on one of
   the allowed families) — the journey + contract suites'
   `DATABRICKS_E2E_WORKSPACE_HOST/TOKEN` calls.

GitHub-hosted runners have open egress; if the workflow ever moves to
self-hosted runners, allowlist exactly those two destinations and
nothing else.

## OIDC trust setup (the nightly workflow)

The workflow authenticates WITHOUT long-lived tokens in the repo:
`permissions: id-token: write` federates the runner to the Databricks
account identity. Set the trust up once (a repository-environment
operation):

1. **Create the e2e service principal** in the Databricks account
   console with the least privilege the nightly needs: workspace
   create/delete and metastore delete on the account (nothing
   workspace-level, no billing reads beyond the journey's own usage
   query).
2. **Register the GitHub OIDC provider** in the Databricks account
   console's identity federation settings: issuer
   `https://token.actions.githubusercontent.com`, audience bound to the
   repository (`repo:<owner>/DataInteroperabilityHub`), subject claim
   constrained to the `databricks-e2e` environment (`environment:databricks-e2e`).
3. **Bind the federated principal** to the e2e service principal so the
   runner's OIDC token mints the account credential the scripts use.
4. **Arm the gate** — set the repository variable `DATABRICKS_E2E=1`
   and the Environment secrets `DATABRICKS_E2E_ACCOUNT_ID`,
   `DATABRICKS_E2E_ACCOUNT_TOKEN` (the federated short-lived token),
   `DATABRICKS_E2E_BUDGET_DBUS` (the hard DBU ceiling — see
   `scripts/databricks_e2e/budget.py`; unset means the budget is zero
   and every run refuses, fail-closed).
5. **Verify** with a manual `workflow_dispatch` and confirm the report
   outcome; record the run in
   [REAL_MARKETPLACE_E2E](REAL_MARKETPLACE_E2E.md)'s validation table
   (the Databricks row's SKIP → PASS migration).

## Rotation cadence

| Credential | Rotation window | Procedure |
|---|---|---|
| `DATABRICKS_E2E_ACCOUNT_TOKEN` (OIDC-federated) | **90 days** (alert at 80) | Rotate the federation binding in the Databricks account console, then update the GitHub Environment secret. The OIDC posture means NO PAT lives in GitHub — rotation is a federation-binding refresh, not a token copy. |
| `DATABRICKS_E2E_WORKSPACE_HOST/TOKEN` | Per run | Derived at run time from the sandbox the workflow creates; not stored long-term. |
| `DATABRICKS_E2E_BUDGET_DBUS` | Review quarterly | Update the ceiling with the observed run cost trend (the report's DBU evidence). |
| Tenant workspace credentials (PAT / OAUTH_M2M) | 90 days | `POST /api/v1/databricks/workspaces/{id}/credentials/{cid}/rotate/` — PAT rotates via token-management on-behalf-of + delete-old; M2M re-issues the client secret. Verify with `GET /api/v1/databricks/workspaces/{id}/test/`. |
| BYO OAuth App connection client secret | Per Databricks console policy | Regenerated in the Databricks account console; the Hub's authorization-code flow never holds it (only the client id is configured) — no Hub-side update needed unless the client id changes. |

## Verification

After any rotation or trust change:

1. Re-run the nightly via `workflow_dispatch` (or the tenant credential
   test endpoint above).
2. Confirm the run reaches its terminal outcome and the report
   (`report/e2e_report.json`) stamps PASSED/FAILED with the per-leg
   evidence — never a silent skip.
3. For tenant credentials: `GET /api/v1/databricks/workspaces/{id}/test/`
   green, and the workspace's breaker channel
   (`databricks_admin_{tenant_id}`) closed.

## Related

- [RB-SEC-001](RB-SEC-001-credential-rotation.md) — platform-wide credential rotation.
- [Databricks Control Plane User Guide](../user-guides/databricks-control-plane.md) — the P0–P9 surface map.
- [REAL_MARKETPLACE_E2E](REAL_MARKETPLACE_E2E.md) — the validation record the nightly stamps.
