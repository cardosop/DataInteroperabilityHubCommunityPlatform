# Frontend npm Scripts Audit

**Date:** 2026-05-22
**Phase:** 312.8.4 — Frontend Test Infrastructure
**Source:** `frontend/package.json` → `scripts` section

---

## Summary

| Category | Count | Scripts |
|---|---|---|
| Development | 5 | `dev`, `build`, `preview`, `predev`, `prebuild` |
| Linting/Formatting | 7 | `lint`, `lint:fix`, `lint:rules`, `lint:e2e:guards`, `typecheck`, `format`, `format:check` |
| i18n | 4 | `i18n:check`, `i18n:check:strict`, `i18n:check:hardcoded`, `i18n:check:hardcoded:test` |
| Storybook | 3 | `storybook`, `build-storybook`, `chromatic` |
| Unit/Component Tests | 8 | `test`, `test:run`, `test:run:ci`, `test:ui`, `test:coverage`, `test:coverage:check`, `test:component`, `test:component:protected-route` |
| a11y Tests | 1 | `test:a11y` |
| Integration Tests | 1 | `test:integration:api` |
| E2E Tests | 25 | `test:e2e` + 8 batches + 3 routes batches + 13 other variants |
| Utility | 1 | `sync-shared` |
| **Total** | **55** | |

---

## Full Catalog

### Development

| Script | Command | Purpose |
|---|---|---|
| `sync-shared` | `bash scripts/sync-shared.sh` | Sync shared code from `shared/` |
| `predev` | `bash scripts/sync-shared.sh` | Auto-run before `dev` |
| `prebuild` | `bash scripts/sync-shared.sh` | Auto-run before `build` |
| `dev` | `vite` | Vite dev server |
| `build` | `tsc -b && vite build` | TypeScript check + production build |
| `preview` | `vite preview` | Preview production build |

### Linting & Type Checking

| Script | Command | Purpose |
|---|---|---|
| `lint` | `eslint .` | ESLint across all files |
| `lint:fix` | `eslint . --fix` | ESLint with auto-fix |
| `lint:rules` | `node e2e/.eslint-rules/run-tests.cjs` | Run ESLint custom rule tests |
| `lint:e2e:guards` | `eslint e2e` | ESLint E2E test guards |
| `typecheck` | `tsc --noEmit` | TypeScript type checking |
| `format` | `prettier --write "src/**/*.{ts,tsx,css}"` | Format source files |
| `format:check` | `prettier --check "src/**/*.{ts,tsx,css}"` | Check formatting (CI) |

### i18n

| Script | Command | Purpose |
|---|---|---|
| `i18n:check` | `node scripts/check-i18n-keys.cjs` | Check i18n key completeness |
| `i18n:check:strict` | `node scripts/check-i18n-keys.cjs --strict-orphans` | Strict orphan key check |
| `i18n:check:hardcoded` | `node scripts/check-i18n-hardcoded.cjs --all` | Detect hardcoded strings |
| `i18n:check:hardcoded:test` | `node --test scripts/check-i18n-hardcoded.test.cjs` | Test the hardcoded check |

### Storybook

| Script | Command | Purpose |
|---|---|---|
| `storybook` | `storybook dev -p 6006` | Storybook dev server |
| `build-storybook` | `storybook build -o storybook-static` | Build static Storybook |
| `chromatic` | `chromatic --build-script-name=build-storybook --exit-zero-on-changes` | Chromatic visual testing |

### Unit & Component Tests

| Script | Command | Heap | Purpose |
|---|---|---|---|
| `test` | `NODE_OPTIONS='--no-webstorage' vitest` | Default | Interactive test runner |
| `test:run` | `NODE_OPTIONS='--no-webstorage' vitest --run` | Default | Single run |
| `test:run:ci` | `NODE_OPTIONS='--no-webstorage --max-old-space-size=4096' vitest --run` | 4096 MB | CI runner |
| `test:ui` | `vitest --ui` | Default | Vitest UI |
| `test:coverage` | `NODE_OPTIONS='--no-webstorage' vitest --coverage` | Default | With coverage |
| `test:coverage:check` | `NODE_OPTIONS='--no-webstorage --max-old-space-size=8192' vitest run --coverage` | 8192 MB | CI coverage gate |
| `test:component` | `NODE_OPTIONS='--no-webstorage --max-old-space-size=8192' vitest run src/features/ && ... vitest run src/shared/...` | 8192 MB | Component tests split into 3 sub-runs to avoid OOM |
| `test:component:protected-route` | `VITEST_NODE_HEAP=16384 NODE_OPTIONS='--no-webstorage --max-old-space-size=32768' vitest run src/shared/components/__tests__/ProtectedRoute.test.tsx` | 32768 MB | Large ProtectedRoute test file |

### a11y Tests

| Script | Command | Purpose |
|---|---|---|
| `test:a11y` | `playwright test --config=playwright.a11y.config.ts` | Accessibility E2E (no backend) |

### Integration Tests

| Script | Command | Purpose |
|---|---|---|
| `test:integration:api` | `bash scripts/run-integration-api-tests.sh` | API integration tests |

### E2E Tests

| Script | Command | Notes |
|---|---|---|
| `test:e2e` | `bash scripts/e2e-detect-api.sh` | Auto-detect API, run all E2E |
| `test:e2e:mvp` | `bash scripts/e2e-detect-api.sh --config=playwright.mvp.config.ts --project=chromium-mvp` | MVP-only specs |
| `test:e2e:mvp:visible` | `E2E_VISIBLE=1 bash scripts/e2e-detect-api.sh --config=playwright.mvp.config.ts --project=chromium-mvp --project=visible-mvp` | MVP headed debug |
| `test:e2e:full` | `bash ../scripts/run-e2e-with-backend.sh` | Full stack (backend + frontend) |
| `test:e2e:ui` | `bash scripts/e2e-detect-api.sh --ui` | Playwright UI mode |
| `test:e2e:headed` | `bash scripts/e2e-detect-api.sh --headed` | Headed browser |
| `test:e2e:debug` | `bash scripts/e2e-detect-api.sh --debug` | Debug mode |
| `test:e2e:visible` | `E2E_VISIBLE=1 bash scripts/e2e-detect-api.sh --project=visible` | Visible browser |
| `test:e2e:visible:ui` | `E2E_VISIBLE=1 playwright test --ui --project=visible` | Visible + UI |
| `test:e2e:visible:auth` | `E2E_VISIBLE=1 bash scripts/e2e-detect-api.sh --project=visible e2e/auth-visitor-journeys.spec.ts e2e/journeys/auth/` | Auth-specific visible |
| `test:e2e:routes` | `bash scripts/e2e-detect-api.sh --project=chromium-routes --timeout=120000 e2e/journeys/...` | All route smoke tests |
| `test:e2e:routes:batch1` | Routes batch 1: contracts-odps + marketplace-dc | |
| `test:e2e:routes:batch2` | Routes batch 2: dq-compliance-governance + mesh-virtualization-search-ai | |
| `test:e2e:routes:batch3` | Routes batch 3: integrations-jobs-webhooks + admin-audit-settings + alternate-flows | |
| `test:e2e:ux` | `bash scripts/e2e-detect-api.sh --project=chromium e2e/use-cases/ux/` | UX flow tests |
| `test:e2e:report` | `npx playwright show-report` | Show HTML report |
| `test:e2e:batches:list` | `bash scripts/e2e-batches.sh list` | List batch definitions |
| `test:e2e:batch1`–`test:e2e:batch8` | `bash scripts/e2e-batches.sh N` | Individual batches |


---

## Bash Script Dependencies

| npm Script | Depends On | Script Location |
|---|---|---|
| `predev`, `prebuild`, `sync-shared` | `scripts/sync-shared.sh` | `frontend/scripts/sync-shared.sh` |
| `test:e2e`, `test:e2e:mvp`, `test:e2e:routes`, `test:e2e:ux` | `scripts/e2e-detect-api.sh` | `frontend/scripts/e2e-detect-api.sh` |
| `test:e2e:batch1`–`test:e2e:batch8` | `scripts/e2e-batches.sh` | `frontend/scripts/e2e-batches.sh` |
| `test:e2e:full` | `../scripts/run-e2e-with-backend.sh` | `scripts/run-e2e-with-backend.sh` |
| `test:integration:api` | `scripts/run-integration-api-tests.sh` | `frontend/scripts/run-integration-api-tests.sh` |

---

## Observations

### Memory Management
Three component test scripts use elevated heap sizes (8GB, 16GB, 32GB). The `test:component:protected-route` specifically allocates 32GB for a single test file due to its size. This suggests the ProtectedRoute test file should be further split.

### Batch Complexity
25 E2E-related scripts expose multiple dimensions: batches (1-8), route batches (1-3), projects (chromium, routes, visible), modes (headed, debug, UI), and scopes (MVP, UX, routes). Each combination has its own npm script. The `e2e-batches.sh` script centralizes batch definitions.

### Missing Documentation
Several npm scripts reference bash scripts without inline help:
- `scripts/e2e-detect-api.sh` — no `--help` flag
- `scripts/run-integration-api-tests.sh` — undocumented
- `scripts/run-e2e-with-backend.sh` — in repo root, not frontend dir

### Recommendations
1. Document `e2e-detect-api.sh` flags (`--config`, `--project`, `--timeout`, `--workers`, `--ui`, `--headed`, `--debug`)
2. Consider consolidating `test:e2e:routes:batch1-3` into `test:e2e:batch2` (already covers route areas)
3. Split `ProtectedRoute.test.tsx` further to eliminate the 32GB heap requirement
4. Move `../scripts/run-e2e-with-backend.sh` into frontend scripts directory or Makefile
