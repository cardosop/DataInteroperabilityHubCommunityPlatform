# JOURNEY-DB-009: Manage UC Grants

## Overview

An MPA manages UC grants through the ABAC plan-first bridge: attribute policies (`conditions["uc_grant"]` blocks) define the INTENT, the bridge plans it into principal/securable/privilege bindings, diffs it against the live UC assignments, applies the delta via the REST PATCH (SQL GRANT/REVOKE fallback for catalog/schema grants), and verifies by re-reading. OWNERSHIP is never granted — the DPO owns. Model grants use UC's `FUNCTION` securable; attribute-policy shadows mark bindings `OUT_OF_SYNC` so operators see the divergence instead of the bridge guessing.

## Journey Steps

1. **Plan** — The planner derives the intended grants from the tenant's ALLOW policies and refuses OWN/OWNERSHIP (`DATABRICKS_GRANT_UNSUPPORTED`).
2. **Diff** — The bridge computes the (principal, privilege) pairs to add/remove against the live assignments.
3. **Apply** — The PATCH leg hits `/api/2.1/unity-catalog/permissions/{securable}/{full_name}` with remove-then-add changes; catalog/schema grants ride the SQL fallback with backtick-quoted GRANT/REVOKE statements.
4. **Verify** — The verify leg re-reads the live assignments and reports mismatches — never masks, never crashes.

## Success Criteria

- The binding grain (workspace, principal, securable, privilege) stays unique and tenant-scoped (RLS).
- Disabled policies shadow their bindings `OUT_OF_SYNC`; unmappable securables are skipped, never applied, never a crash.

## Related

- Use cases: [UC-DB-009](../use-cases/UC-DB-009.md)
- Journeys: [JOURNEY-DB-006](JOURNEY-DB-006.md) (Inspect Table Permissions)
