# UX & Frontend Validation — Meshant Platform

**Last updated:** 2026-05-15

## B.1.1 — UX Research (Deferred — Human-dependent)

**Status:** ⏭️ Requires recruiting 30 users across 6 personas.

| Persona | Users Needed | Core Workflow to Test |
|---|---|---|
| Data Engineer | 5 | Asset creation → DQ run → activate |
| Data Consumer | 5 | Marketplace browse → checkout → entitlement |
| Compliance Officer (CPO) | 5 | Compliance scan → report → DSAR submit |
| Data Protection Officer (DPO) | 5 | DPIA wizard → RoPA generate → breach report |
| Platform Admin | 5 | Tenant settings → feature flags → user management |
| External Developer | 5 | API keys → SDK docs → marketplace listings |

**Test protocol:** 30-minute moderated session per user. Measure: task completion rate, time-on-task, error rate, SUS score. Use `docs/audit-reports/ux-themes-ranked-backlog-278a.md` for prioritized UX themes.

## B.1.2 — Dark-Mode Chromatic Baseline (Deferred — Infrastructure)

**Status:** ⏭️ No Chromatic workflow configured for this repo. Requires:
1. `chromatic.config.json` exists but no CI integration
2. Chromatic project token + GitHub Actions workflow
3. Capture all components in dark mode (`[data-theme='dark']`)
4. Accept baselines after visual review

**Pre-requisite:** 278.C design token migration complete (303 hardcoded colors replaced across 48 files). Dark mode should now render correctly via token overrides.

## B.1.3 — Mobile-Responsive Testing (Deferred — Device-dependent)

**Status:** ⏭️ Requires physical devices or device lab.

| Device | Browser | Critical Journey |
|---|---|---|
| iPhone 15 | Safari iOS | Asset detail → DQ run → activate |
| Pixel 8 | Android Chrome | Marketplace browse → checkout |
| iPad Air | Safari | Compliance scan → report |
| Galaxy Tab | Android Chrome | User management |

**Known responsive patterns:** `AppShell.css` has `@media (max-width: 768px)` breakpoint. Sidebar becomes overlay. Table wrappers get `overflow-x: auto`. 55 page wrappers have individual `max-width` constraints.

## B.1.4 — INTEGRATION PENDING Resolution

**Status:** ✅ COMPLETE (verified 2026-05-15).

Previously-reported `INTEGRATION PENDING` components all wired:
- `RetryBanner` → imported by `ErrorDisplay.tsx` (line 11)
- `FormErrors` → imported by `AssetCreatePage.tsx` (line 35), `ContractCreatePage.tsx` (line 17), `DatasetCreatePage.tsx` (line 17), `WebhookCreatePage.tsx` (line 10)
- `KeyboardShortcuts` → imported by `App.tsx` (line 70)
- `ProductTourGate` → imported by `App.tsx` (line 72)

**Zero INTEGRATION PENDING notes remain.** All Phase 278 components are rendered in production code paths.

## B.1.5 — Core Web Vitals Instrumentation

**Status:** ⏭️ Not yet instrumented. `web-vitals` library not imported.

**Implementation plan:**
```typescript
// frontend/src/shared/telemetry/webVitals.ts (new)
import { onCLS, onFCP, onLCP, onTTFB } from 'web-vitals';

function sendToAnalytics(metric: { name: string; value: number; rating: string }) {
  // POST to /api/v1/analytics/web-vitals/
  fetch('/api/v1/analytics/web-vitals/', {
    method: 'POST',
    body: JSON.stringify(metric),
    headers: { 'Content-Type': 'application/json' },
    keepalive: true,
  });
}

onCLS(sendToAnalytics);
onFCP(sendToAnalytics);
onLCP(sendToAnalytics);
onTTFB(sendToAnalytics);
```

**Requires:** `npm install web-vitals`, create `shared/telemetry/webVitals.ts`, import in `main.tsx`, create backend `POST /api/v1/analytics/web-vitals/` endpoint, Grafana dashboard.

## B.1.6 — Error Boundary Coverage Audit

**Status:** ✅ AUDITED (2026-05-15).

| Metric | Count |
|---|---|
| Total route elements | 164 |
| ErrorBoundary-wrapped | 132 (80%) |
| Direct element assignments | 47 |

**Unwrapped routes:** 47 direct elements are structural (public routes, redirects, `<Outlet />`, `<RootRoute />`) — not feature pages. Feature pages (lazy-loaded routes) all go through `<EB fallbackMsg="...">` wrapper (line 48 of routes.tsx).

**No gap to fix** — public routes and structural elements intentionally unwrapped.

## B.1.7 — Cross-Browser E2E Checklist

**Status:** ✅ CONFIGURED (verified 2026-05-15). Playwright config (`playwright.config.ts`) has 15 browser refs including `chromium`, `firefox`, `webkit` projects.

**Checklist for operator:**

| Browser | Engine | Critical Journey Spec | Status |
|---|---|---|---|
| Chrome | Chromium | `e2e/cross-cutting/infrastructure-canary.spec.ts` | ⏭️ |
| Firefox | Gecko | `e2e/cross-cutting/failure-scenarios-tests.spec.ts` | ⏭️ |
| Safari | WebKit | `e2e/a11y/axe-critical-pages.spec.ts` | ⏭️ |

```bash
# Run cross-browser
npx playwright test --project=chromium e2e/cross-cutting/infrastructure-canary.spec.ts
npx playwright test --project=firefox e2e/cross-cutting/failure-scenarios-tests.spec.ts
npx playwright test --project=webkit e2e/a11y/axe-critical-pages.spec.ts
```
