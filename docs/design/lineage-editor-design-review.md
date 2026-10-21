# Phase 228.F2.1 — Lineage editor design-review checklist

> **Purpose**: Ground truth for the F2 design surface, used as a
> stand-in for the Figma sign-off when high-fidelity mocks aren't
> available (or the Figma file location has drifted).  Every check
> here maps to a F2 spec requirement; the reviewer ticks the box
> when the implementation matches both the requirement and the
> intended interaction.
> **Audience**: 2-3 internal data engineers (the F2.1 reviewers).
> **Status**: Engineering-driven design doc; replaces the Figma
> mockup-review process for tranches where no separate Figma file
> exists.

## Layout

- [ ] **Two-pane field selector** (REQ-LIN-F2-004).  Source pane on
  the left, target pane on the right, equal width.
  *Implementation*: `LineageEditPage.tsx::FieldsTwoPane` uses
  `gridTemplateColumns: '1fr 1fr'`.
- [ ] **Edges table** below the field panes — full width, columns
  Source / Target / Type / Actions.
- [ ] **Toolbar at the bottom** — Add edge, Save changes, Cancel
  (in that order).

## Interactions

- [ ] Click "Add edge" opens the EdgeDetailModal pre-populated with
  empty source/target.
- [ ] Click "Edit" on an edge row opens the modal pre-populated
  with that edge's data.
- [ ] Click "Remove" on an edge row removes it from the local
  pending state (Save commits the diff).
- [ ] Save round-trip:
  - On 200, navigate back to `/contracts/<id>` (the detail page).
  - On 412 (stale ETag), open the conflict modal preserving the
    pending edges as a draft (REQ-LIN-F2-002).
  - On 400 cycle, render the CycleErrorPanel above the edges table
    with the offending edge highlighted.
  - On 400 field-not-found, render the validation panel.
  - On 413 (>1000 edges), render the too-large panel.

## Visual states

- [ ] **Loading**: skeleton with `aria-busy=true`; placeholder
  boxes suggest the graph shape (CSS-grid with 3 grey boxes).
- [ ] **Empty edges**: text-only "No edges yet. Click a source field
  then a target field to map them."
- [ ] **Empty fields** (contract has no models declared): "No
  fields declared. Open the Schema editor on the contract to add
  fields first."
- [ ] **Truncated graph**: yellow banner above the field panes
  announcing truncation (REQ-LIN-F2-D2 mitigation).

## Color + typography

- [ ] All text uses CSS variables from the project's design tokens
  (`--font-size-*`, `--spacing-*`).  No raw `px` values for spacing.
- [ ] Cycle-error panel: red background `#fff5f5` + border `#fca5a5`.
- [ ] Conflict modal: white background, 1px grey border, drop shadow.
- [ ] CTA contrast meets WCAG 2.1 AA (4.5:1) — verified via the
  WAVE / axe-core browser extension.

## Keyboard model

- [ ] Tab order: Source-pane → Target-pane → Edges-table → Toolbar.
- [ ] Inside the Edge detail modal, focus is trapped (cycles within
  the modal; Escape closes).
- [ ] Inside the Conflict modal, focus is trapped (Reload / Discard
  buttons).
- [ ] All buttons have visible focus rings (browser default — not
  removed via CSS `outline: none`).

## Responsiveness

- [ ] Layout works at 1280×720 (smallest desktop target).
- [ ] At 768px width the two panes stack vertically (single
  column).  Edges table scrolls horizontally rather than squashing
  columns.
- [ ] At 360px width (mobile smoke), the editor is still usable —
  field-pane height bounded so the toolbar stays reachable.

## i18n

- [ ] Every customer-visible string is sourced from
  `lineageEditorStrings.ts` under `lineage.editor.*` (REQ-LIN-X-001).
- [ ] No string concatenation that breaks RTL (e.g. no `${count} +
  ' items'`).  Strings are full sentences.

## Off-page entry

- [ ] "Edit lineage" button on the contract detail page's Lineage
  tab, capability-gated via `useCapabilities('contracts.lineage_field_editor')`.
  When the capability is OFF the button is hidden.

## Reviewer sign-off

This doc is the engineering design contract for F2.  When a Figma
mockup file lands, the source-of-truth shifts to Figma and this
doc becomes a redundant cross-check.  Until then, sign-off below
gates the F2 capability-flag flip.

| Reviewer | Role | Date | Notes |
| --- | --- | --- | --- |
|  | Data eng (rev 1) | | |
|  | Data eng (rev 2) | | |
|  | Data eng (rev 3) | | |
