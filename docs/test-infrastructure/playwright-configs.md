# Playwright Configuration Files

**Date:** 2026-05-22
**Phase:** 312.8.1 — Frontend Test Infrastructure
**Scope:** 5 Playwright configuration files in `frontend/`.

---

## Summary

| Config | Purpose | Backend Needed? | CI Trigger |
|---|---|---|---|
| `playwright.config.ts` | Main E2E (8 batches) | Yes | PR + push to main/develop |
| `playwright.a11y.config.ts` | Accessibility only | No | PR (via `playwright-e2e.yml`) |
| `playwright.mvp.config.ts` | MVP-gated features | Yes | PR + push |
| `playwright.mvp.quarantine.config.ts` | Quarantined flaky specs | Yes (staging) | Nightly schedule |
| `playwright.visual.config.ts` | Visual regression snapshots | No | Scheduled + manual dispatch |

---

## 1. `playwright.config.ts` — Main E2E Configuration

**File:** `frontend/playwright.config.ts` (14,209 bytes)

### Purpose
Primary E2E test configuration. Runs all functional E2E specs against a real backend (Docker Compose or staging).

### Key Settings
- **testDir:** `./e2e`
- **fullyParallel:** `true` (except `E2E_VISIBLE=1` mode)
- **retries:** `2` in CI, `0` locally
- **timeout:** 60s default (individual tests override via `test.setTimeout()`)
- **workers:** 2 default; batch scripts override per batch

### Projects
| Project | When Used | Purpose |
|---|---|---|
| `setup-auth` | Always (dependency) | One-time login to save `storageState` |
| `chromium` | Default | Main headless test run |
| `chromium-routes` | Route-level smoke tests | Full-page route verification |
| `visible` | `E2E_VISIBLE=1` | Headed + slowMo for interactive debugging |

### CI Integration
- **Workflow:** `playwright-e2e.yml`
- **Triggers:** `push: [main, develop]` (path-filtered), `pull_request` (path-filtered), `workflow_dispatch`
- **Timeout:** 90 minutes

### Features
- Fast-path `loginUser` via `storageState` (avoids full navigation to `/login` for every test)
- External target support (`PLAYWRIGHT_BASE_URL` for staging/production)
- Excludes `e2e/dimensions/` and `e2e/personas/` from default runs (marked `testIgnored`)

---

## 2. `playwright.a11y.config.ts` — Accessibility Configuration

**File:** `frontend/playwright.a11y.config.ts` (1,176 bytes)

### Purpose
Runs ONLY accessibility tests. No backend API required — tests verify WCAG compliance of static pages and component states.

### Key Settings
- **testDir:** `./e2e`
- **testMatch:** `**/a11y/**/*.spec.ts`
- **fullyParallel:** `true`
- **Projects:** `chromium` only (single browser)
- **webServer:** `npm run dev` (frontend only, no backend)
- **globalSetup:** None (no auth needed)

### CI Integration
- **Workflow:** `playwright-e2e.yml` (via matrix configuration)
- Can run independently: `npm run test:a11y`

### When to Use
- Local: `npx playwright test --config=playwright.a11y.config.ts`
- npm: `npm run test:a11y`
- CI: Automatically as part of Playwright E2E pipeline

---

## 3. `playwright.mvp.config.ts` — MVP-Gated Features

**File:** `frontend/playwright.mvp.config.ts` (13,537 bytes)

### Purpose
Runs E2E tests scoped to MVP features (`release/mvp-v1` branch). Uses `grep`/`grepInvert` to filter tests by persona and journey tags.

### Key Settings
- **grepInvert:** `/@quarantine\b/` — excludes quarantined flaky tests
- **testMatch:** Persona-specific specs (DPO, DE, DC, TA, PA, CPO, Auditor, Visitor)
- **Projects:** `chromium-mvp`, `setup-auth-mvp`

### CI Integration
- **Trigger:** `release/mvp-v1` branch pushes
- **npm:** `npm run test:e2e:mvp`

### Cross-Browser Support
- `E2E_CROSS_BROWSER=1` enables Firefox + WebKit projects for weekly cross-browser runs (@312.8.7)
- `E2E_MOBILE=1` enables Pixel 5 viewport for mobile testing (@312.8.8)

---

## 4. `playwright.mvp.quarantine.config.ts` — Quarantined Tests

**File:** `frontend/playwright.mvp.quarantine.config.ts` (1,087 bytes)

### Purpose
Runs ONLY `@quarantine`-tagged tests. Inherits all settings from `playwright.mvp.config.ts` but inverts the grep filter.

### Quarantine Lifecycle
```
Spec tagged @quarantine
  → Nightly quarantine run passes 5 consecutive times
  → Strip @quarantine tag
  → Spec re-joins main MVP CI run
```

### Key Settings
- **grep:** `/@quarantine\b/` (opposite of main MVP config)
- **grepInvert:** `undefined`
- **retries:** `3` (extra budget for known-flaky specs)

### CI Integration
- **Workflow:** `playwright-mvp-quarantine-nightly.yml`
- **Trigger:** Daily at 02:30 UTC + `workflow_dispatch`
- **Environment:** Staging (via `PLAYWRIGHT_BASE_URL`)
- **Non-blocking:** Failures do NOT block merges — advisory signal only

---

## 5. `playwright.visual.config.ts` — Visual Regression

**File:** `frontend/playwright.visual.config.ts` (5,128 bytes)

### Purpose
Visual regression testing using `expect.toHaveScreenshot()`. Isolated from functional test runs because visual diff stability requires different settings (animations disabled, pinned viewport, consistent font rendering).

### Key Settings
- **testDir:** `./e2e/visual`
- **testMatch:** `**/*.spec.ts`
- **Projects:** `chromium` only (pinned viewport 1280×720)
- **Snapshot directory:** `frontend/e2e/visual/__snapshots__/`

### CI Integration
- **Workflow:** `visual-regression-playwright.yml`
- **Trigger:** Scheduled + `workflow_dispatch` with `update_snapshots` input
- **Chromatic:** Also integrated via `chromatic.yml` for Storybook visual testing

### Usage
```bash
npx playwright test --config=playwright.visual.config.ts                   # run / compare
npx playwright test --config=playwright.visual.config.ts --update-snapshots # bump baselines
```

---

## Configuration Matrix

| Feature | Main | A11y | MVP | Quarantine | Visual |
|---|---|---|---|---|---|
| Backend API | Yes | No | Yes | Yes (staging) | No |
| Auth (login) | Yes | No | Yes | Yes | No |
| WebServer (Vite) | Yes | Yes | Yes | No (remote) | Yes |
| Browsers | Chromium | Chromium | Chromium (+FF/WebKit) | Chromium | Chromium |
| Workers | 1-2 | Auto | 1 | 1 | Auto |
| Retries | 2 (CI) | 2 (CI) | 2 | 3 | 0 |
| Timeout | 60s | 60s | 60s | 60s | 60s |
| CI Trigger | PR + push | PR | MVP branch | Nightly | Scheduled |
| CI Blocking | Yes | Yes | Yes | No | No |

---

## Related Documentation
- [e2e-batch-strategy.md](e2e-batch-strategy.md) — 8-batch E2E execution strategy
- [ci-workflow-audit.md](ci-workflow-audit.md) — CI workflow audit
- [existing-infra-inventory.md](existing-infra-inventory.md) — Test infrastructure inventory
