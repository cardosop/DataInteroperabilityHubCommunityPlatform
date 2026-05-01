# Lineage WCAG 2.1 AA review checklist

**Phase:** 228 X (228.X.2 / REQ-LIN-X-002)
**Owner:** Frontend Eng + Accessibility Lead
**Last reviewed:** 2026-05-01

This is the per-phase manual review checklist for the lineage UI
surface. The automated `@axe-core/playwright` gate covers WCAG A
+ AA programmatic violations; the items below cover the assistive-
technology + manual review the spec calls out (NVDA + VoiceOver,
4.5:1 contrast, no info by colour alone).

The frontend release manager runs this checklist BEFORE flipping
the per-phase capability flag in production.

## Per-phase scope

| Phase | Surface to review |
|---|---|
| 228 F1 | Cross-tenant marketplace lineage browsing |
| 228 F2 | Field-level mapping editor |
| 228 F3 | Lineage change-notifications UI |
| 228 F4 | OpenLineage admin (key management + DLQ status panel) |
| 228 F5 | Time-travel controls + diff view |

## Automated gate (must be green before manual review)

```bash
# CI artifact: every E2E spec in frontend/e2e/features/
# that wraps the lineage surface runs an AxeBuilder scan with
# tags ['wcag2a', 'wcag2aa']. Zero violations = pass.
cd frontend && npm run test:a11y -- --grep "lineage"
```

If any spec reports violations, fix BEFORE the manual review.

## Manual review (per-phase)

### Screen-reader walkthrough (NVDA on Windows)

For each route surface in the table above:

- [ ] Tab through every interactive element. Reading order matches
      visual order. No focus traps.
- [ ] Every button/link has a visible focus indicator AND an
      announced label.
- [ ] Form errors announce as soon as they appear (`role="alert"`
      or `aria-live="polite"`).
- [ ] Modal / dialog announces its label on open (`aria-labelledby`).
- [ ] Lineage graph: keyboard navigation works (arrow keys move
      between nodes; Enter activates).

### Screen-reader walkthrough (VoiceOver on macOS)

- [ ] Repeat the NVDA list above on Safari + VoiceOver.
- [ ] Rotor (`VO-U`) lists all headings, landmarks, links — in
      logical order.
- [ ] No "image / image / image" runs without alt text.

### Contrast (4.5:1 minimum for body text, 3:1 for large text)

- [ ] Open Chrome DevTools → "Lighthouse" → "Accessibility" →
      run on every route surface.
- [ ] Inspect every flagged element; confirm its actual contrast
      ratio with the DevTools "Inspect Element" → "Accessibility"
      panel.
- [ ] Diff view (`LineageDiffView.tsx`) — every bucket carries a
      glyph in addition to colour, so achromatopsia simulation
      remains parseable.

### Info by colour alone

- [ ] Diff buckets distinguishable WITHOUT colour (Chrome DevTools
      → "Emulate vision deficiency" → "Achromatopsia"). Glyphs
      `+ − =` carry the meaning.
- [ ] Severity badges in the lineage notifications UI carry an
      icon + a text label, not colour alone.
- [ ] Edge-type indicators in the lineage graph carry an icon /
      shape, not just colour.

### Mobile / responsive

- [ ] Pinch-zoom up to 200% — no content lost off-screen.
- [ ] Touch targets ≥ 44 × 44 px on mobile breakpoints.
- [ ] Time-travel controls collapse cleanly on narrow viewports.

## Sign-off

Reviewer fills the table per phase before tagging the release:

| Phase | Reviewer | NVDA | VoiceOver | Contrast | Colour-alone | Mobile | Date |
|---|---|---|---|---|---|---|---|
| F1 | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| F2 | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| F3 | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| F4 | | ☐ | ☐ | ☐ | ☐ | ☐ | |
| F5 | | ☐ | ☐ | ☐ | ☐ | ☐ | |

Evidence (screenshots, NVDA recording, contrast-check JSON) stored
under `evidence/lineage-a11y-<phase>-<YYYY-MM-DD>/`.

## Related

- Automated config: [frontend/playwright.a11y.config.ts](../../frontend/playwright.a11y.config.ts)
- F5 a11y E2E: [frontend/e2e/features/lineage-time-travel.spec.ts](../../frontend/e2e/features/lineage-time-travel.spec.ts)
- F4 a11y review: [openlineage-dod-evidence.md](./openlineage-dod-evidence.md)
- F5 a11y review: [lineage-snapshots-dod-evidence.md](./lineage-snapshots-dod-evidence.md)
