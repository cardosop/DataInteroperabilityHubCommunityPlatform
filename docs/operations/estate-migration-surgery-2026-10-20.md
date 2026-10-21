# Estate Migration Surgery — 2026-10-20 (P3-1, B-1)

The rehearsed dual-path surgery for `warehouses.0007` (the estate-FK
split) — condition `estate-migration-surgery`
(`openspec/changes/close-oss-release-conditions`).

## The condition

`warehouses.0007` (Django-6-generated, 2026-09-04) added two FKs from
`WarehouseConnection` to `databricks_admin` models and hard-depended on
`databricks_admin.0005`. The model itself carries the 313.1
conditional-paid-FK contract (`if not HUB_CORE_ONLY:` around the FK
fields in `hub/apps/warehouses/models.py`) — the migration never got
its twin, so in core-only mode (the public tree / `make quickstart`)
the migration graph could not build:
`NodeNotFoundError: Migration warehouses.0007_... dependencies
reference nonexistent parent node ('databricks_admin',
'0005_enable_rls_databricks_credentials')` — the W9.2 stranger-path
signature and the W7.3 public-CI 8th-job blocker.

## The surgery (executed 2026-10-20)

`warehouses/0007` is now the migration twin of the model's conditional
contract (Django's documented `apps.is_installed` pattern for optional
cross-app relations):

- the cross-app dependency (`databricks_admin.0005`) exists only when
  `databricks_admin` is installed;
- the two FK `AddField` operations exist only on the same condition —
  on a core-only database the migration is a recorded no-op;
- estate-installed databases that already applied the unconditional
  version are unaffected (the migration name is unchanged — the
  recorder never re-runs it).

Two real defects found + root-fixed on the way, each pinned:

1. **The hard dependency itself** — the unconditional
   `("databricks_admin", ...)` dependency list entry (the RED
   `NodeNotFoundError` signature, captured live in core-only
   `manage.py migrate --plan` and `makemigrations --check`).
2. **`apps.is_installed()` matches the AppConfig NAME, not the label** —
   `apps.is_installed("databricks_admin")` (the label form) is ALWAYS
   False in this project (the app config's `name` is the full dotted
   path `hub.apps.databricks_admin`); the label form would have
   silently turned the migration into a no-op on estate databases —
   caught by the full-mode `sqlmigrate` pin rendering no `ADD COLUMN`
   and the `makemigrations --check` pin proposing a duplicate 0008.
   The migration now gates on
   `apps.is_installed("hub.apps.databricks_admin")`, and the contract
   pin asserts the full-name form (the regression shape).

Pins: `scripts/tests/test_p31_estate_migration_surgery.py` **9/9**
(CI lint list) — the dual-path contract (structural), the real
migration graph in both modes (`migrate --plan`), the rendered SQL in
both modes (`sqlmigrate warehouses 0007` — core: no `ADD COLUMN`;
full: both FK adds), `makemigrations --check` clean in both modes,
and the core boot smoke.

## Verification drills (the repo's fresh-DB / clone / reverse convention)

### 1. Fresh-DB chain — core-only — GREEN

Dedicated DB `hub_test_p31core` (p313-pg), `HUB_CORE_ONLY=1
manage.py migrate --noinput` from zero: **611 migrations applied,
exit 0** — `warehouses.0007` RECORDED (the no-op) and the estate FK
columns correctly ABSENT. The exact blocked step of the public CI's
test-core job and the quickstart api migrate now completes.

### 2. Fresh-DB chain — full (estate) mode — GREEN

Dedicated DB `hub_test_p31full` (p313-pg), full `manage.py migrate
--noinput` from zero: **748 migrations applied, exit 0** — 0007
recorded with BOTH estate FK columns present
(`databricks_credential_id`, `databricks_workspace_id`): the estate
path applies the FK adds on a fresh estate DB.

### 3. Clone + reverse (forward → reverse → forward verbatim) — GREEN

On `hub_test_p31full`: `migrate warehouses 0006` unapplied 0007 and
DROPPED both FK columns (recorded row gone) → `migrate warehouses`
re-applied 0007 and RE-CREATED both columns (row back). The U.7
rehearsal discipline passes on the estate path.

### 3b. Existing-data catch-up drill — GREEN

The clone `hub_test_p31clone` ← `hub_test_313full` (a real
estate-shaped DB with existing `warehouse_connections` rows) was 580
migrations stale: full forward `migrate` caught it up **167 → 748
migrations, exit 0**, through the dual-path 0007 — both FK columns
present on the pre-existing data (nullable FKs, zero data loss).

### 4. Drift findings recorded along the way

- **`hub_test_313full` is 580 migrations stale** (167 recorded rows
  vs the 748-migration chain at HEAD) and lacks the 0007 FK columns —
  the shared host-side DB has been left behind since the drift era
  (the trap-17 class). Left untouched (parallel sessions use it); the
  catch-up drill above proves the stale→HEAD path.
- **The root conftest's paid-module regex drifted from the manifest**
  — the W7.3 `databricks_admin` manifest addition never propagated to
  `_PAID_MODULE_IMPORT_RE`, so core-mode collection imported the
  estate models (93 collection errors on the exact leg this condition
  unblocks). Root-fixed + pinned (the sync is now machine-enforced).
- **The quickstart seed chain crashed core mode** —
  `seed_demo_data → ensure_e2e_user_roles → seed_e2e_uc_mirror`
  invoked the estate command BY NAME gated only on a tenant flag, not
  on the app being installed (`CommandError: Unknown command
  'seed_e2e_uc_mirror'`). Root-fixed with the
  `apps.is_installed("hub.apps.databricks_admin")` guard + pinned.
- **Committed collection breakage surfaced by the unblocked leg** —
  `hub/apps/scheduled_ingestion/catalog_records.py` had a
  SyntaxError (the P2-3 broad-except mis-indented one level up) and
  `hub/apps/files/tests/test_views.py` had two defs at the wrong
  indent (the W11.11 DAST test + `test_list_files_success_returns_200`
  mangled at module/nested level); both root-fixed.
  `hub/apps/core/error_handling/tests/test_error_responses.py` tested
  a module DELETED in the b0c53036d consolidation (superseded by
  `hub.apps.api.standards.response_formats` + its live contract
  test) — the stale file deleted with this disposition recorded.
- **Pre-existing, recorded not fixed (owning lanes):** the
  warehouses connector tests
  (`test_connectors_databricks_athena.py::TestSessionConfigTags` ×3)
  call the refactored-away `_session_config` method (W4.6 connector
  lane); the W4.6 standalone-seams pins fail registration-order
  assertions in this environment (the P3-2 sibling-red-gates lane's
  battery covers them); the estate runtime suites
  (`test_obo_tokens`, `test_uc_sync*`, `test_delta_sharing_*`,
  dashboard-parse tests, …) fail HOST-SIDE on the documented
  environment classes (compose-network DNS for `minio`, live SSRF
  DNS probes for `*.cloud.databricks.com`) — their canonical home is
  the in-container test stack; 0 of their failures reference the
  migration, the FK fields, or any file this lane touched.

### 5. Public-tree core-tests + stranger-path quickstart boot

- **The public CI's blocked job substance — GREEN:** the core-only
  migration chain (drill 1) + `scripts/core_boot_smoke.py` (pinned) +
  the core-only backend run over `hub/apps/` (see the tasks.md
  entry for the count) on the dedicated core DB.

### 5b. The next layers the unblocked run exposed (root-fixed + pinned)

The first green-collection core-only run (6h09m, `hub_test_p31core`)
measured **16,848 passed / 1,071 failed / 17 errors** — and the
triaged failure classes were fixed at the root, each pinned:

- **601+ `RuntimeError` paid-model imports at setUp/fixture level** —
  the collection-time conftest filter only sees COLUMN-0 imports;
  function-level paid imports must degrade-or-skip themselves (the
  W7.1 guard contract). **121 indented unguarded sites across 49
  core-app test files** wrapped with the canonical
  `try/except (RuntimeError, ModuleNotFoundError) → pytest.skip`
  guard (idempotent AST fixer; multi-line parenthesized imports
  handled). Regrowth pin
  `test_paid_imports_in_core_test_modules_are_guarded` (RED-first:
  121 sites live) — the full P3-1 suite is 12/12.
- **~64 redis `AUTH` failures** — the host invocation passed an
  auth'd URL against the host's no-auth redis; the canonical env uses
  the plain URL (the G12 redis-auth guard applies in
  production/staging only — `ENVIRONMENT=test` is exempt). Invocation
  corrected in the re-runs.
- **The explicit-file collection trap (recorded):** explicitly-passed
  test-file arguments BYPASS `pytest_ignore_collect` in this pytest —
  a column-0-import module that directory collection correctly
  ignores errors out when named on the command line. Directory-based
  invocation is the canonical shape.
- Remaining host-side environment classes (minio compose DNS, live
  SSRF DNS probes, dashboard fixture files) resolve in the
  in-container CI environment — recorded, not fixable host-side.
- **Public-CI local equivalents — GREEN:** the boundary suite 51/51,
  GATE-29 clean in all three modes (`--check`,
  `--check-allowlist-growth`, `--public`).
- **Stranger-path quickstart boot (api included) — GREEN:** a fresh
  `git clone` of the private repo + the working-tree overlay +
  generated `.env` → `make quickstart` (core-mode dev stack) —
  "Core stack ready": api healthy on :8000 (migrate + seed green —
  the two steps the surgery unblocked), frontend serving on :3000,
  postgres/redis×4/traefik healthy. Two stranger-path defects
  root-fixed on the way (both pinned): the worker's dev port 8092
  collides with the running test stack (documented override
  `WORKER_HEALTH_PORT`); and the fresh-clone tree must carry the
  working tree's uncommitted WIP (the clone's api crashed importing
  the untracked `hub.apps.audit.command_audit` — the W9.2
  overlay-the-working-tree precedent).
  Observation recorded (not a blocker): the dev worker container
  reports unhealthy — its healthz HTTP server isn't started under the
  rq-command shape while the worker processes jobs fine (pre-existing
  dev-stack quirk; the W9.2 run's healthy list didn't include the
  worker either).

## Condition closure

**CLOSED 2026-10-20** — ledger row `estate-migration-surgery` in
`docs/operations/oss-go-nogo-ledger.md` flipped CLOSED with this
evidence; ticket `TICKET=W105-ESTATE-MIGRATION-SURGERY` closed in
`openspec/changes/track-oss-deferred-debt/tasks.md`; P3-1 recorded
in `openspec/changes/close-oss-release-conditions/tasks.md`.
