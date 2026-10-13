# UC-DB-009: Manage UC Grants

**Persona:** [Platform Admin](../personas/platform-admin/index.md)
**MVP Tier:** :white_check_mark:
**Phase P2 Test:** `hub/apps/databricks_admin/tests/test_grants_journeys.py::TestJOURNEYDB009ManageUcGrants::test_manage_uc_grants`

## Description

Manage UC grants through the ABAC plan-first bridge: the ABAC engine PLANS the intended grants from attribute policies (`conditions["uc_grant"]` blocks), the bridge DIFFS them against the live UC assignments, APPLIES the delta via the REST PATCH (SQL GRANT/REVOKE fallback for catalog/schema grants), and VERIFIES by re-reading. OWNERSHIP is never granted (`DATABRICKS_GRANT_UNSUPPORTED`); model grants use the `FUNCTION` securable; attribute-policy shadows mark bindings `OUT_OF_SYNC`.

## Preconditions

- A registered workspace and ALLOW effect attribute policies with `uc_grant` blocks.

## Steps

1. The planner derives the intended grants; bindings are upserted at the (principal, securable, privilege) grain with `source_policy_id`.
2. The diff computes add/remove pairs against the live assignments.
3. The apply leg PATCHes `/api/2.1/unity-catalog/permissions/{securable}/{full_name}` with remove-then-add changes (or issues backtick-quoted GRANT/REVOKE statements for catalog/schema).
4. The verify leg re-reads the live assignments and reports mismatches (never masks, never crashes).

## Expected Outcome

- Bindings reflect the policy intent; shadows mark `OUT_OF_SYNC` when a policy can no longer produce its grant.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| OWN/OWNERSHIP in the plan | `UCGrantBridgeError` `DATABRICKS_GRANT_UNSUPPORTED` |
| Unmappable securable | skipped with a warning (never applied, never crashes the sweep) |
| Unrepresentable privilege | refused (`DATABRICKS_GRANT_UNSUPPORTED`) |

## Related

- Concepts: [Warehouse Connectivity](../concepts/warehouse-connectivity.md)
- Journeys: [JOURNEY-DB-009 -- Manage UC Grants](../journeys/JOURNEY-DB-009.md)
- Personas: [Platform Admin](../personas/platform-admin/index.md)
