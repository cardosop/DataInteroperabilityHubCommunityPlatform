# Phase 228.F2.26 — Lineage editor screen-reader test plan

> **Audience**: QA / accessibility reviewers running NVDA (Windows)
> and VoiceOver (macOS / iOS) against the Phase 228.F2 lineage
> editor.
> **Status**: Manual test plan — `LineageEditPage.test.tsx`
> (Phase 228.F2.25) covers the WCAG 2.1 AA baseline programmatically;
> this plan adds the human screen-reader pass that an automated
> tool can't replicate (announce ordering, focus traversal, modal
> dismissal sound cues, etc.).

## Pre-conditions

- F2 backend deployed with `is_capability_enabled("contracts.lineage_field_editor")` returning True.
- A contract exists in the tester's tenant with at least 3 model fields.
- Tester is a tenant admin OR holds the `EDIT_LINEAGE` permission.

## Test environments

| Environment | Browser | Screen reader |
| --- | --- | --- |
| **NVDA primary** | Windows 10/11 + Firefox latest | NVDA 2024.x |
| **NVDA secondary** | Windows 10/11 + Chrome latest | NVDA 2024.x |
| **VoiceOver macOS** | macOS Sonoma + Safari | VoiceOver |
| **VoiceOver iOS** (smoke only) | iOS 17 + Safari | VoiceOver |

NVDA primary is the canonical environment for sign-off. VoiceOver
macOS catches platform-specific defects in the focus trap. VoiceOver
iOS smoke-tests the responsive layout but isn't gated.

## Test cases

### TC-1 — Page landmark + skip link

1. Navigate to `/contracts/<id>/lineage/edit`.
2. With NVDA running, press `D` (move to next landmark).
3. **Expected**: NVDA announces *"main, Edit lineage"*. The
   page is exposed as a single `<main>` landmark with an
   `aria-label` of "Edit lineage".
4. Press `H` (move to next heading).
5. **Expected**: NVDA announces *"Edit lineage, heading level 1"*.

### TC-2 — Loading skeleton announcement

1. Open the editor on a slow connection (devtools network throttling
   set to "Slow 3G").
2. With NVDA running, observe the announcement during the data fetch.
3. **Expected**: NVDA announces *"Saving…, busy"* (or equivalent).
   The skeleton element has `role="status"` + `aria-busy="true"`,
   so NVDA's polite live region surfaces it.

### TC-3 — Field-pane navigation

1. After the editor renders, tab through the page.
2. **Expected** tab order: Source-pane heading → Source-pane fields →
   Target-pane heading → Target-pane fields → Edges-table → Toolbar
   buttons (Add edge, Save, Cancel).
3. **Expected**: each interactive control announces its purpose
   (e.g. *"Source field id, list item"*); no element receives focus
   without an accessible name.

### TC-4 — Edge-detail modal focus trap

1. Click "Add edge".
2. **Expected**: focus moves into the modal. NVDA announces
   *"Edge detail, dialog"*.
3. Tab through the modal. **Expected**: focus cycles through the
   form fields + Save + Cancel, then returns to the first form
   field — never escaping the modal.
4. Press `Escape`. **Expected**: modal closes, focus returns to
   the "Add edge" button.

### TC-5 — Edge-detail form labels

1. Open the modal.
2. With NVDA, navigate each form field with Tab.
3. **Expected**: each input announces its label (Source model,
   Source field, Target model, Target field, Edge type,
   Transformation reference, Job reference).

### TC-6 — Cycle error panel

1. Construct a cyclical edge set that the validator will reject
   (e.g. A → B and B → A on the same fields).
2. Click Save.
3. **Expected**: the cycle error panel appears with `role="alert"`.
   NVDA announces the alert text immediately
   (*"Alert. Cycle detected. This mapping would create a circular dependency…"*).

### TC-7 — Conflict modal (412)

1. Open the editor in two tabs.
2. Save in tab 1, then save in tab 2 (with stale ETag).
3. **Expected**: the conflict modal in tab 2 appears as
   `role="dialog"` + `aria-modal="true"`. NVDA announces
   *"Lineage was edited by someone else, dialog"*.
4. Press Tab. **Expected**: focus cycles between the
   "Reload and merge" + "Discard my changes" buttons.

### TC-8 — Edge table semantic structure

1. Add 3+ edges so the edges table populates.
2. Use NVDA's table-navigation shortcuts (`Ctrl+Alt+arrow`).
3. **Expected**: the table is exposed as a real `<table>` with
   `<thead>` + `<tbody>`, and column headers are announced when
   navigating cells. Row count + column count match what's
   visually shown.

### TC-9 — Truncation banner

1. Trigger a >F1_NODE_CAP graph (developer-helper: temporarily
   patch `F1_NODE_CAP=2` server-side).
2. **Expected**: the truncation banner appears. NVDA announces it
   via `role="status"` (*"Lineage graph truncated for performance…"*).

### TC-10 — Color-contrast + zoom

1. Set browser zoom to 200%.
2. **Expected**: layout doesn't break; horizontal scroll appears
   only on narrow viewports; all text remains legible. Color
   contrast of CTA buttons + error panels passes WCAG 2.1 AA
   (verified against the WAVE / axe-core extension).

## Acceptance

- Every TC above passes on NVDA primary (Windows + Firefox).
- TC-1 through TC-7 pass on VoiceOver macOS.
- Failures filed as GitHub issues with the `a11y` label and the
  TC number; each issue blocks the F2 capability-flag flip.

## Sign-off

- Tester name: _________________
- Date: _________________
- Browser + SR version: _________________
- Result: PASS / FAIL (file count) / RETEST
