# JOURNEY-CPO-013: Generate and Export Record of Processing Activities (RoPA)

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-ROPA-001
**Phase:** 232 (GDPR Programme)
**Status:** Implemented
**E2E:** `test_ropa_journey.py`
**Routes:** `/compliance/ropa`

## Overview

A Compliance & Privacy Officer generates a Record of Processing Activities (RoPA) document mandated by GDPR Art. 30. The RoPA aggregates processing activities, data categories, legal bases, cross-border transfers, and retention periods into a structured document. The CPO can preview the RoPA, export it in multiple formats, and archive versions for audit.

## Journey Steps

1. **Navigate to RoPA list** — From the compliance sidebar, the CPO opens the RoPA management page. The list shows previously generated RoPA records with status, generation date, and regime coverage.
2. **Generate new RoPA** — Clicks "Generate RoPA" → `POST /api/v1/ropa/generate/`. Backend aggregates processing activities across all registered assets, consent records, processor agreements, and retention policies. Status transitions: PENDING → PROCESSING → COMPLETED.
3. **Preview RoPA** — Clicks a completed RoPA record to view the structured document with sections: controller identity, processing purposes, data categories, recipients, cross-border transfers, retention periods, technical/organisational measures.
4. **Export RoPA** — Selects export format (PDF, JSON, CSV) → `POST /api/v1/ropa/export/` → downloads the formatted document.
5. **Archive version** — The CPO can archive the current RoPA version before re-generating, preserving a snapshot for regulatory audit.

## Error Handling

- **Generation timeout** — If aggregation takes >60s, the job continues async; status polls until COMPLETED/FAILED.
- **Empty processing activities** — Renders "No processing activities registered — create assets and configure data categories first."
- **Export failure** — `<ErrorDisplay>` with the specific backend error code.

## Audit Events

| Event | Trigger | Retention |
|---|---|---|
| `ROPA_GENERATED` | New RoPA generation completes | 90 days |
| `ROPA_EXPORTED` | RoPA exported in any format | 90 days |

## Success Criteria

- RoPA generation completes within 60s for tenants with <1000 processing activities.
- All mandatory Art. 30 fields appear in the generated document.
- Export produces valid PDF/JSON/CSV output.
- Archived versions are immutable and retrievable.

## Related

- E2E: `test_ropa_journey.py`
- Runbook: [phase232-ropa.md](../../runbooks/phase232-ropa.md)
- Components: `RopaListPage`, `RopaDetailPage`, `RopaExportPage`
- Phase: 232.4 (RoPA generation)
