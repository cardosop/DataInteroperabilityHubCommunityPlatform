# UC-MKT-ADV-004: Compare Listings Side-by-Side

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md)
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.H.3`

## Description

A Data Consumer selects 2–5 marketplace listings and opens a side-by-side
comparison view. The comparison grid displays pricing model, compliance
grade, data quality score, schema metrics, sample availability, and last
updated timestamp across all selected listings in a responsive horizontal
table. This allows the consumer to evaluate multiple data products at a
glance without navigating back and forth between detail pages.

## Preconditions

- The user is authenticated and has marketplace access.
- At least 2 published listings are visible on the marketplace list page.
- The `useBulkSelect` hook (Phase 278.E.2) is wired on the listing list
  page, providing row checkboxes and a BulkActionBar.

## Steps

1. DC navigates to `/marketplace` or `/marketplace/listings`.
2. DC selects 2–5 listing cards via the row checkboxes (BulkActionBar
   appears at the bottom of the page).
3. DC clicks "Compare" from the BulkActionBar.
4. `ComparisonView` opens as a modal overlay (`role="dialog"`) with a
   horizontal table. Columns = selected listings; rows = pricing,
   compliance grade, DQ score, schema metrics, sample availability,
   last updated, average rating.
5. DC reviews the comparison and optionally exports the comparison as
   CSV via the "Export comparison" button.
6. DC closes the view via the ✕ button, overlay click, or Escape key.

## Expected Outcome

- The comparison view renders all selected listings side-by-side with
  correct data for each comparison row.
- Selecting >5 listings disables additional checkboxes with a tooltip
  ("You can compare up to 5 listings at once").
- The view is keyboard-navigable (arrow keys between cells).
- CSV export produces a valid file with all visible comparison data.
- `MARKETPLACE_LISTINGS_COMPARED` audit event is emitted.
- `meshant.comparison.opened` and `meshant.comparison.closed`
  CustomEvents fire on window (Phase 278.T.2 telemetry).

## Error Handling

| Condition | Expected Response |
|---|---|
| < 2 listings selected | "Compare" button hidden/disabled |
| > 5 listings selected | Additional checkboxes disabled + tooltip |
| Comparison data fetch fails | Inline error per listing row |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md), [Compliance Runs](../../concepts/compliance-runs.md)
- Use Cases: [UC-MKT-ADV-002](UC-MKT-ADV-002.md) (Preview Data Before Purchase)
- Journeys: [JOURNEY-DC-002](../journeys/JOURNEY-DC-002.md) (Marketplace Discovery Flow)
- Components: `ComparisonView`, `BulkActionBar`, `useBulkSelect`
- Phase 278 tasks: `278.H.3` (ComparisonView), `278.E.2` (BulkActionBar)
- E2E: `comparison-side-by-side.spec.ts` (278.V.8)
