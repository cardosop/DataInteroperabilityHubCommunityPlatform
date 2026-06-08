# UC-SEM-003: Browse Resource Version History

**ID:** UC-SEM-003
**Title:** Browse Resource Version History
**Persona:** Data Consumer (DC)
**Priority:** Medium
**Phase:** 283.4 (GA)
**Feature Flag:** `versioning_enabled` (ON by default for new tenants),
`sematic_memento_enabled` (OFF by default, opt-in for Memento datetime negotiation)

## Summary

A Data Consumer browses the version history of a dataset or contract, compares
two versions to understand schema evolution, and uses time-travel queries
to inspect the resource state at a specific point in time.

## Preconditions

- Tenant has `versioning_enabled = True`
- Resource has multiple versions (at least 2)
- User has DC role

## Main Flow

1. DC navigates to a dataset or contract detail page
2. DC opens the version history panel
3. Hub lists all versions with creation timestamps and status
4. DC selects two versions and clicks "Compare"
5. Hub displays the schema and metadata differences between versions
6. Optionally: DC uses time-travel to query the resource as it existed
   at a specific timestamp (`semantic_memento_enabled` required)

## Acceptance Criteria

- Version history paginated and filterable
- Version comparison shows field-level diffs
- Time-travel query returns resource state at specified timestamp
- CLI: `datahub versioning list|get|diff|rollback` commands functional
