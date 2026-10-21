# UC-MKT-ADV-003: Save and Manage Marketplace Search Alerts

**Persona:** [Data Consumer (DC)](../personas/data-consumer/index.md)
**Phase:** 278 (UX Activation)
**Phase 278 Task:** `278.H.4`

## Description

A Data Consumer saves their current marketplace search filters with a
name and optional notification preferences (instant push, daily digest,
weekly digest). Saved searches persist across sessions, are listed in a
dropdown on the filter bar, and can be applied with a single click.
Clicking a saved search applies its filters to the current marketplace
view. Saved searches can be deleted when no longer needed.

## Preconditions

- The user is authenticated and belongs to a tenant with marketplace
  access.
- At least one published listing exists in the marketplace catalog.
- The SavedSearchButton component is mounted on the marketplace filter bar.

## Steps

1. DC navigates to `/marketplace` and applies filters (e.g., domain
   "healthcare", pricing model "Free").
2. DC clicks the 🔖 (SavedSearchButton) in the filter bar to open the
   saved search dropdown.
3. DC clicks "Save current filters", enters a name in the name input,
   and optionally selects a notification frequency (INSTANT, DAILY,
   WEEKLY, or NONE).
4. DC clicks "Save". The saved search is persisted via
   `POST /api/v1/marketplace/saved-searches/`.
5. DC re-opens the dropdown to verify the saved search appears in the
   list with its name and frequency badge.
6. DC clicks the saved search item. The saved filters are applied
   immediately and the dropdown closes.
7. To delete, DC clicks the 🗑 button on the saved search item. The
   deletion fires `DELETE /api/v1/marketplace/saved-searches/{id}/`.

## Expected Outcome

- The saved search is listed in the dropdown with correct name and
  frequency.
- Clicking a saved search applies its filters to the marketplace view
  (URL query string reflects the restored filters).
- Deleting a saved search removes it from the list.
- A `SEARCH_SAVED` audit event is emitted on creation; deletion emits
  a `SEARCH_DELETED` event.
- Empty-name submissions are silently rejected (frontend guard).

## Error Handling

| Condition | Expected Response |
|---|---|
| Duplicate saved search name | `409 Conflict` |
| Empty name | Frontend guard — save button returns early |
| No active filters when saving | "Save current filters" button hidden |
| Unauthenticated | `401 Unauthorized` |

## Related

- Concepts: [Marketplace Listings](../../concepts/marketplace-listings.md)
- Use Cases: [UC-MKT-ADV-002](UC-MKT-ADV-002.md) (Preview Data Before Purchase)
- Journeys: [JOURNEY-DC-002](../journeys/JOURNEY-DC-002.md) (Marketplace Discovery Flow)
- Components: `SavedSearchButton`, `SavedSearchListPage`
- Phase 278 tasks: `278.H.4` (Saved searches + alerts), `278.H.1` (Recommendations)
- E2E: `saved-search-crud.spec.ts` (278.V.7)
