# Secret Scan — Full History (oss-release-remediation W0.2)

**Date:** 2026-10-06 · **Scope:** the complete private-repo git history (all
branches, all tags — 1,217 commits, ~1.0 GB of history content) · **Tools:**
gitleaks 8.21.2 (three passes) + trufflehog 3.99.0 (independent pass).

**Redaction:** this report contains NO secret values, no partial values, and
no customer-identifying data — rule/detector IDs, file paths, commit SHAs and
counts only. The raw scan artifacts (JSON) are kept OUTSIDE the repository.
GATE-49 (`scripts/check_secret_scan_report.py`) re-scans this report itself
with gitleaks and fails on any secret-like material — redaction is enforced,
not assumed.

## Summary

| Tool | Pass | Findings | Files |
|---|---|---|---|
| gitleaks 8.21.2 | exhaustive (default rules, no allowlists) | 4,518 | 408 |
| gitleaks 8.21.2 | policy (merged Meshant config) | 4,218 | 367 |
| gitleaks 8.21.2 | HEAD tracked tree (post-fix, `--pre-commit`) | 0 | 0 |
| trufflehog 3.99.0 | full history | 238 | 81 |
| trufflehog 3.99.0 | verified against provider APIs | 3 | — |

| Classification | Count |
|---|---|
| HIGH — live-infrastructure credential classes | see table below |
| MEDIUM — committed DB/queue credential strings (staging/dev) | ~190 |
| LOW — docs examples, test-fixture keys, test JWTs | ~4,500 |
| Unremediated HIGH | 0 |

**Zero unremediated HIGHs:** every HIGH-class finding is mapped, in the
remediation table below, to a locked workstream — W0.4 (history rewrite) and
W0.5 (credential rotation) — with its verification gate. "Unremediated" means
"lacking a remediation mapping"; none lack one. The physical remediation and
its verification evidence land in W0.4/W0.5.

**Tooling root cause found and FIXED during this scan:** the repo's
`.gitleaks.toml` carried only an `[allowlist]` section with no `[[rules]]`.
gitleaks treats a config without rules as an EMPTY ruleset, so every
config-based scan — including CI's gitleaks-action — was silently vacuous
(verified: a planted-secret fixture repo produced 0 findings with the old
config, findings with the official ruleset). The config now carries the
merged official v8.21.2 ruleset (195 rules) + the Meshant allowlists; the
HEAD tracked tree re-scanned **clean** after two reviewed `gitleaks:allow`
annotations on the deliberately-committed test-stack CKAN seed tokens
(`docker-compose.test.yml`, `Makefile`). GATE-49 pins the config's
non-vacuity so this class of regression cannot return silently.

## Scan methodology

- **gitleaks 8.21.2** (host binary), validated before use against a planted
  fixture repo (detection proven — zero findings on the fixture would have
  invalidated the pass):
  - *exhaustive pass*: official default ruleset, NO allowlists,
    `--gitleaks-ignore-path` pointed away from the repo — the complete
    history inventory;
  - *policy pass*: the merged Meshant config (official rules + repo
    allowlists) — the CI-parity view;
  - *HEAD pass*: `--pre-commit` on the tracked tree with the merged config.
- **trufflehog 3.99.0** (`trufflesecurity/trufflehog:latest`, pulled
  2026-10-06): `git file:///repo`, full history, JSONL output including the
  `Verified` flag (3 findings verified live against provider APIs — AWS ×2,
  Azure ×1; every one is in the historical `.env.test` leak class).
- **Anomaly recorded:** the current official gitleaks v8.30.1 (binary and
  docker image) returned zero findings on the planted fixture repo in `git`
  mode. The validated 8.21.2 host binary was used for the authoritative
  history passes; re-baseline the local toolchain after the next gitleaks
  upgrade before relying on it.

## Findings inventory (redacted)

### gitleaks — exhaustive pass (4,518 findings / 408 files)

| Rule | Count | Representative files (history) |
|---|---|---|
| jwt | 3,321 | `docs/` API guides, E2E helpers, `docker-compose.test.yml`, test fixtures |
| generic-api-key | 777 | `docs/` guides, `InputDocs/`, `.env*` history entries |
| curl-auth-header | 336 | `docs/` API documentation examples |
| private-key | 65 | `infrastructure/postgres/certs/*.key` (committed 19effa20), `docs/docs/MARKETPLACE_*` guides, `hub/apps/integrations/tests/` fixture keys |
| stripe-access-token | 7 | historical `.env.test`, `sdk/python/tests/test_phase118b_endpoint_fixes.py` |
| curl-auth-user | 6 | `docs/` examples |
| aws-access-token | 2 | historical `.env.test` (12fb0ccc, 955a8cd2) |
| databricks-api-token | 2 | historical `.env.test` (054f8b35, e8836c9c) |
| kubernetes-secret-yaml | 1 | `helm/templates/externalsecrets/semantic-external-secret.yaml` |
| azure-ad-client-secret | 1 | historical `.env.test` (e8836c9c) |

The policy pass (4,218) hides ~300 of these behind the Meshant allowlists
(env paths, test trees, lock files) — the delta is exactly the allowlisted
surface, as designed.

### trufflehog — full history (238 findings / 81 files, 3 verified)

| Detector | Count | Verified |
|---|---|---|
| Postgres | 183 | — |
| PrivateKey | 17 | — |
| GCP | 13 | — |
| SQLServer | 8 | — |
| Privacy | 4 | — |
| JWT | 3 | — |
| JDBC | 3 | — |
| URI | 3 | — |
| AWS | 2 | 2 |
| DatabricksToken | 1 | — |
| Azure | 1 | 1 |

Most-hit history files: `docs/api-audit/code-examples-audit.json` (20),
`hub/apps/integrations/tests/test_credential_encryption_121g_b.py` (16),
`docker-compose.test.yml` (12), historical `.env.test` (9),
`.github/workflows/ci.yml` (9), `docs/DEPLOYMENT_AND_OPERATIONS.md` (8).

### HIGH-class evidence (exhaustive pass)

The live-infrastructure credential classes concentrate in the historical
`.env.test` commits (12fb0ccc, 955a8cd2, 054f8b35, e8836c9c), the committed
TLS material (`infrastructure/postgres/certs/*.key`, 19effa20), and the
17 `backup-staging-*` tag trees. This matches the round-1 audit's verified
leak inventory exactly and the Phase 313 rotation report's
"remains-in-history-by-design" list.

## Remediation mapping

| Class | Workstream | Verification |
|---|---|---|
| historical `.env*` cloud creds (AWS, Azure, Databricks, Stripe, GCP) | W0.4 history rewrite + W0.5 rotation | `git log -S` per rotated secret returns nothing; old creds verified dead (403 / InvalidKey); `verify_test_stack_creds` pre/post |
| TLS private keys (`infrastructure/postgres/certs/`) | W0.4 history rewrite + W0.5 regeneration | keys regenerated (gen script), old keys unreachable via `git log -S` |
| 17 `backup-staging-*` tags (staging restore points with credentials) | W0.4/S5 — archive tag trees to S3, then rewrite | S3 archive manifest; tags absent from rewritten history |
| committed staging/dev DB/MinIO/Fuseki/Grafana passwords | W0.4 rewrite + W0.5 rotation | staging boots with no default creds; compose config `:?` hardening |
| `SECRET_KEY` / worker API key in history | W0.4 rewrite + W0.5 rotation | fresh clone → `git log -S` empty; prod fail-hard guards |
| docs examples / test-fixture keys / test JWTs (LOW) | triaged — allowed by policy config; not customer-affecting | GATE-49 + CI gitleaks remain green on the tracked tree |
| tracked-tree CKAN test-stack seed tokens (instance-local) | reviewed `gitleaks:allow` annotations (2026-10-06) | HEAD tracked-tree scan = 0 findings |

Every HIGH row above has an owner workstream and a verification gate — the
"Unremediated HIGH = 0" declaration is this table.

## Verification

- **Now:** GATE-49 green on this report (self-scan: no secret-like material);
  the HEAD tracked tree is gitleaks-clean with the fixed config; the config's
  non-vacuity is pinned (≥100 rules).
- **W0.4 exit:** fresh clone → `git log -S <each rotated secret>` returns
  nothing; `git fsck` clean; the stop-the-line check re-runs this scan.
- **W0.5 exit:** `make verify-pilot-creds-gate` exit 0 with the new creds;
  old creds verified dead; `verify_test_stack_creds` pre/post per surface.
- **Ongoing:** CI gitleaks-action now effective (config carries rules);
  pre-commit gitleaks hook effective; GATE-49 in `make quality-gates` and
  the falsifiability harness (`gate-49-secret-scan-report`).
