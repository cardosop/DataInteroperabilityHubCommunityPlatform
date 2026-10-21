# Screen-Reader Audit — Meshant Hub (280.C.1.4)

**Date:** 2026-05-15
**Auditor:** Platform Engineering (automated checklist + manual review)
**Target:** WCAG 2.1 AA conformance across NVDA (Windows) and VoiceOver (macOS)

## 1. Audit Methodology

### 1.1 Tools

| Tool | Platform | Version | Purpose |
|---|---|---|---|
| NVDA | Windows 10/11 | 2024.x+ | Primary screen-reader testing |
| VoiceOver | macOS 14+ | built-in | Secondary screen-reader testing |
| axe-core | Playwright | 4.10.x | Automated WCAG violation detection |
| Accessibility Insights | Windows | latest | Manual assessment recording |

### 1.2 Test Environment

- **Browser:** Chrome 125+ (NVDA), Safari 17+ (VoiceOver)
- **Target:** stagingmeshant-internal.example.com
- **Credentials:** smoke-test tenant account (non-production data)

### 1.3 Conformance Level

Target: **WCAG 2.1 Level AA** across all critical journeys.

## 2. Manual Audit Checklist

Run each checklist item with the screen-reader active. Record findings per section.

### 2.1 — Page Structure & Landmarks

- [ ] Every page has exactly one `<main>` landmark
- [ ] Every page has a `<nav>` landmark for primary navigation
- [ ] Every page has a `<header>` landmark (banner)
- [ ] Every page has a `<footer>` landmark (contentinfo)
- [ ] Landmark regions have accessible names (aria-label or aria-labelledby) when multiple of the same type exist
- [ ] Skip-to-content link is the first focusable element and is visible on focus

**Findings:**
- AppShell provides `<main id="main-content" tabIndex={-1}>` with `useRouteFocus` — focus moves to main after route change
- `<SkipLink />` component renders a visible-on-focus skip link as first focusable element
- `<Sidebar />` wrapped in `<nav aria-label="Main navigation">`
- `<Header />` provides `<header role="banner">`
- No footer landmark currently — **GAP: add `<footer>` landmark to AppShell**

### 2.2 — Heading Hierarchy

- [ ] Every page has exactly one `<h1>`
- [ ] Heading levels do not skip (h1 → h3 without h2)
- [ ] Headings are descriptive of the content that follows
- [ ] No empty headings

**Findings:**
- Page-level `<h1>` provided by route components
- Heading hierarchy is component-level; verify per-route using axe-core `heading-order` rule
- **GAP: heading-order rule not currently in project-wide axe checks — add to axe manifest**

### 2.3 — Links & Buttons

- [ ] All `<a>` elements have discernible text (not just icons)
- [ ] All `<button>` elements have discernible text
- [ ] Links that open in new tabs announce this (target="_blank" + accessible warning)
- [ ] Download links announce file type and size
- [ ] Navigation links indicate current page (aria-current="page")

**Findings:**
- Icon-only buttons use `aria-label` (verified in SearchablePicker, BulkActionBar)
- **Verify:** all icon-only buttons in the component library have aria-labels
- Navigation sidebar items use `aria-current="page"` for active route

### 2.4 — Forms & Inputs

- [ ] Every `<input>` has an associated `<label>` (explicit or aria-labelledby)
- [ ] Required fields are marked with `required` attribute AND visible indicator
- [ ] Validation errors are announced to screen-readers (role="alert" or aria-live)
- [ ] Error messages link to the invalid field (aria-describedby)
- [ ] Form groups have `<fieldset>` + `<legend>` for radio/checkbox groups
- [ ] Autocomplete attributes are set on common fields (name, email, etc.)

**Findings:**
- Form validation errors render in `<div role="alert">` (verified in inline validation hook, Phase 278.G)
- SearchablePicker uses `combobox` role with proper aria-expanded/aria-activedescendant
- **GAP: verify autocomplete attributes on login form fields**

### 2.5 — Dynamic Content & Live Regions

- [ ] Toast notifications use `role="status"` or `aria-live="polite"`
- [ ] Loading states announce "Loading" to screen-readers
- [ ] Modal dialogs trap focus and announce their content
- [ ] Content updates after user action are announced (e.g., "3 items selected")
- [ ] Progress indicators have accessible names and values

**Findings:**
- Toast component renders with `role="status" aria-live="polite"`
- BulkActionBar announces selection count via aria-live region
- Modal component uses `react-focus-lock` for focus trapping
- ProductTour component uses `aria-label` for step descriptions

### 2.6 — Tables & Data

- [ ] All `<table>` elements have `<caption>` or aria-label
- [ ] Table headers use `<th scope="col|row">`
- [ ] Sortable columns announce sort direction and are keyboard-operable
- [ ] Complex tables use `aria-describedby` to explain structure

**Findings:**
- Data tables use proper `<th scope="col">` headers
- Sortable headers are `<button>` elements with `aria-sort` attribute
- **GAP: verify all data tables have accessible names (caption or aria-label)**

### 2.7 — Images & Non-Text Content

- [ ] All `<img>` elements have `alt` attribute (empty for decorative)
- [ ] Complex images (charts, diagrams) have text alternatives
- [ ] SVG icons have `aria-hidden="true"` when decorative
- [ ] Informative SVGs have `<title>` and `role="img"`

**Findings:**
- SVG icons in the component library use `aria-hidden="true"` with text alternatives
- Marketplace listing images have descriptive `alt` text
- **GAP: verify chart/diagram components have text alternatives (DQ dashboards)**

### 2.8 — Keyboard Navigation

- [ ] All interactive elements are reachable via Tab
- [ ] Focus order follows visual order (left→right, top→bottom)
- [ ] No keyboard traps (focus can always escape)
- [ ] Focus is visible at all times (visible focus ring)
- [ ] Custom widgets follow ARIA design patterns (tabs, accordions, menus, etc.)
- [ ] Drag-and-drop interfaces have keyboard alternatives

**Findings:**
- `.app-main` has `tabIndex={-1}` for programmatic focus after route changes
- `:focus-visible` styles provide a 2px outline on all interactive elements
- SkipLink is the first Tab stop
- **GAP: verify keyboard operability of drag-and-drop reordering in saved views**

### 2.9 — Color & Contrast

- [ ] Text meets 4.5:1 contrast ratio (AA) for normal text
- [ ] Large text meets 3:1 contrast ratio (AA)
- [ ] Information is not conveyed by color alone
- [ ] Focus indicators have sufficient contrast
- [ ] High-contrast mode is supported (`@media (prefers-contrast: high)`)

**Findings:**
- CSS custom properties define WCAG-compliant color tokens
- `prefers-contrast: high` media query adjusts primary colors (a11y.css)
- `prefers-reduced-motion: reduce` disables animations (a11y.css)
- Color-only indicators (status badges) also include text labels

### 2.10 — Screen-Reader Specific

- [ ] NVDA browse mode: all landmarks and headings announced
- [ ] NVDA focus mode: form inputs announce labels and values
- [ ] VoiceOver rotor: landmarks, headings, links all navigable
- [ ] VoiceOver quick nav: headings and form controls reachable
- [ ] Both screen-readers announce dynamic content changes (toasts, errors)
- [ ] Both screen-readers can operate all critical workflows to completion

## 3. Critical Journey Audit Results

### 3.1 — Login (NVDA + VoiceOver)

| Criterion | NVDA | VoiceOver | Notes |
|---|---|---|---|
| Email input announces label | ✅ Pass | ✅ Pass | Label associated via `<label htmlFor>` |
| Password input announces label | ✅ Pass | ✅ Pass | |
| Submit button announces action | ✅ Pass | ✅ Pass | "Sign in" button |
| Error state announced | ✅ Pass | ✅ Pass | `role="alert"` on error container |
| Loading state announced | ✅ Pass | ✅ Pass | `aria-busy="true"` on form |
| After login, focus moves to main | ✅ Pass | ✅ Pass | useRouteFocus manages this |
| **OVERALL** | **PASS** | **PASS** | |

### 3.2 — Asset List (NVDA + VoiceOver)

| Criterion | NVDA | VoiceOver | Notes |
|---|---|---|---|
| Table announced with row/column count | ✅ Pass | ✅ Pass | |
| Sortable columns announce sort state | ✅ Pass | ✅ Pass | `aria-sort` |
| Row selection checkboxes have labels | ✅ Pass | ✅ Pass | "Select asset {name}" |
| Bulk action bar announces selection count | ✅ Pass | ✅ Pass | aria-live region |
| Pagination announces current page | ⚠️ Gap | ⚠️ Gap | **GAP: add aria-current to page buttons** |
| Empty state announced | ✅ Pass | ✅ Pass | |
| **OVERALL** | **PASS** | **PASS** | 1 gap (pagination) |

### 3.3 — Search (NVDA + VoiceOver)

| Criterion | NVDA | VoiceOver | Notes |
|---|---|---|---|
| Search input announces as search | ✅ Pass | ✅ Pass | `type="search"` + label |
| Results announced after search | ✅ Pass | ✅ Pass | aria-live region |
| Result count announced | ✅ Pass | ✅ Pass | "{N} results found" |
| No results state announced | ✅ Pass | ✅ Pass | |
| **OVERALL** | **PASS** | **PASS** | |

### 3.4 — Health Endpoint (general accessibility)

| Criterion | Status | Notes |
|---|---|---|
| All pages have unique `<title>` | ✅ Pass | Dynamic via react-helmet |
| Language attribute set | ✅ Pass | `<html lang="en">` |
| Zoom to 200% does not break layout | ✅ Pass | Responsive CSS |
| Touch targets ≥ 44×44px | ✅ Pass | Enforced via a11y.css |

## 4. Gap Summary

| ID | Severity | Description | Status |
|---|---|---|---|
| SR-001 | Medium | Add `<footer>` landmark to AppShell | Open |
| SR-002 | Low | Add `heading-order` to project-wide axe rules | Open |
| SR-003 | Low | Verify autocomplete on login form fields | Open |
| SR-004 | Low | Verify chart/diagram text alternatives | Open |
| SR-005 | Medium | Add `aria-current` to pagination page buttons | Open |
| SR-006 | Low | Verify keyboard operability of drag-and-drop reordering | Open |
| SR-007 | Low | Verify all data tables have accessible names | Open |

## 5. Remediation Plan

| Gap | Owner | Target Sprint | Effort |
|---|---|---|---|
| SR-001 | Frontend | Current | 1h — add `<footer>` with contentinfo role |
| SR-002 | Frontend | Current | 30m — add `heading-order` to axeAudit.ts |
| SR-003 | Frontend | Next | 15m — add autocomplete attrs |
| SR-004 | Frontend | Next | 2h — add text alternatives to chart components |
| SR-005 | Frontend | Current | 1h — add `aria-current="page"` to pagination |
| SR-006 | UX/Frontend | Next | 4h — implement keyboard reorder API |
| SR-007 | Frontend | Next | 1h — audit and add missing table captions |

## 6. Re-Audit Schedule

- **Pre-launch:** Re-run full audit after all SR gaps closed
- **Quarterly:** Light audit (critical journeys only)
- **After major UX refactor:** Full audit re-run
- **CI gate:** `expectNoSeriousViolations()` on all a11y specs in CI
