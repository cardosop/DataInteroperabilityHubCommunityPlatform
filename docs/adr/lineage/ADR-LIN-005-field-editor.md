# ADR-LIN-005 — Field-level lineage editor surface

**Status:** Accepted (Phase 228 Foundations)
**Date:** 2026-04-30
**Related:** Phase 228 F2 (field-level lineage mapping, capability flag `lineage.field_level_mapping`)

## Context

Phase 228 F2 ships field-level lineage mapping: a data engineer can declare that `target_contract.target_model.target_field` is derived from `source_contract.source_model.source_field`. The mapping needs an editor surface; three options were considered:

1. **Inline editor on the existing `/contracts/:id/edit` page.** A new tab "Field lineage" alongside Schema, Lineage, and Metadata.
2. **Dedicated standalone page.** `/contracts/:id/lineage/edit` — separate route, full-page editor.
3. **Modal overlay.** Click an edge in the lineage visualization → modal opens for inline edit.

## Decision

**Adopt option 2 — dedicated `/contracts/:id/lineage/edit` page (table-style v1).**

The v1 editor is **table-based**: rows are field mappings, columns are `source_contract`, `source_model`, `source_field`, `target_model`, `target_field`, `transformation_ref`, `job_ref`. The user adds rows, edits inline, deletes by row. Save dispatches a single `PATCH` to update the lineage subtree atomically.

A subsequent phase MAY ship a graphical drag-and-drop editor; v1 is deliberately not graphical.

## Consequences

**Positive:**

- Table-based editing matches the data-engineer mental model (field-mapping is a row-oriented activity in DBT, ETL tools, spreadsheets) and is keyboard-friendly.
- A dedicated page allows full-screen real estate for tenants with hundreds of field mappings (the common case for a complex contract).
- The page is a separate Vite route, so its bundle is code-split — the Schema editor's bundle (heavy with Monaco / draft-js) is not loaded for users who only want to edit lineage.
- Deep-linking works natively: `/contracts/<id>/lineage/edit?source=<contract>&target_field=<f>` lets a runbook or audit alert link directly to the row.

**Negative:**

- Two editor pages instead of one (Schema editor at `/contracts/:id/edit` + Lineage editor at `/contracts/:id/lineage/edit`). Mitigated by clear navigation: the Schema editor's "Lineage" tab links to the dedicated editor with a "Open full editor" button.
- Mobile usability is poor for the table layout. Acceptable for v1; field-lineage editing is a desktop activity for our personas.

**Neutral:**

- The "Lineage" tab on the existing edit page becomes a read-only viewer with an "Open editor" CTA. The viewer renders the same table in disabled state.

## Alternatives Considered

- **Inline tab on the existing edit page (option 1):** rejected because the Schema editor's existing tab structure is already 4 tabs deep (Schema, Validation, Properties, Lineage); adding field-level editing inline would push the page to 5+ tabs, which usability testing on Wave 2 flagged as "tab fatigue".
- **Modal overlay (option 3):** rejected because the modal real estate cannot accommodate the 7-column table for tenants with > 20 mappings, and the `Esc`-closes-modal pattern conflicts with "Cmd+Z undo" muscle memory for spreadsheet users.
