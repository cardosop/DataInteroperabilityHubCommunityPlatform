# UC-GOV-ADV-004: Configure Automated Retention

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_compliance_commands_real_api.py::test_automated_retention`

## Description

A Compliance & Privacy Officer defines automated data retention policies
that schedule purges of expired data across the tenant's asset catalog.
Retention policies ensure the platform does not hold personal or
sensitive data beyond regulatory or business-mandated time limits,
reducing storage costs and legal exposure.

## Preconditions

- The user holds the `COMPLIANCE_OFFICER` or `PLATFORM_ADMIN` role.
- Assets in the catalog have a `created_at` or `data_effective_date`
  timestamp that the retention engine can evaluate.
- The retention execution service is deployed and healthy.
- Consent purposes with `retention_period` values exist if GDPR-driven
  (see [UC-GOV-ADV-003](UC-GOV-ADV-003.md)).

## Steps

1. CPO navigates to "Governance > Retention Policies" or calls
   `GET /api/v1/governance/retention-policies` to list existing
   policies.
2. CPO creates a new retention policy via
   `POST /api/v1/governance/retention-policies` with:
   - **Name / description:** e.g., "GDPR 3-year PII retention".
   - **Scope:** All assets, specific domains, tags, sensitivity levels,
     or explicit asset IDs.
   - **Retention period:** ISO 8601 duration (e.g., `P3Y` for 3 years,
     `P90D` for 90 days).
   - **Date field:** Which timestamp to evaluate (`created_at`,
     `data_effective_date`, `last_accessed_at`).
   - **Action on expiry:** `ARCHIVE` (move to cold storage), `DELETE`
     (permanent removal), or `ANONYMIZE`.
   - **Schedule:** Cron expression for the purge check (e.g.,
     `0 2 * * 0` for weekly at 2 AM Sunday).
3. The API validates the policy and returns `201 Created` with
   `policy_id`.
4. CPO optionally configures a pre-purge notification window:
   `PATCH /api/v1/governance/retention-policies/{id}` with
   `{ notification_days_before: 30, notify_roles: ["DPO", "STEWARD"] }`.
   Asset owners receive a warning 30 days before scheduled purge.
5. On the scheduled run, the retention engine evaluates all assets
   within scope:
   - Identifies assets (or data versions) whose retention period has
     expired.
   - Generates a `RetentionRun` with the list of affected assets and
     the planned action.
   - If pre-purge notification is configured and the window has not
     elapsed, the run status is `PENDING_NOTIFICATION`.
   - Otherwise, executes the configured action (archive, delete, or
     anonymize).
6. CPO reviews retention run results via
   `GET /api/v1/governance/retention-runs` which shows: run date, assets
   processed, actions taken, any failures.
7. CPO can also view the retention forecast:
   `GET /api/v1/governance/retention-forecast?horizon=P6M` returns
   assets scheduled for purge in the next 6 months.

## Expected Outcome

- Automated retention policies are active and execute on the configured
  schedule.
- Expired data is archived, deleted, or anonymized without manual
  intervention.
- Asset owners and stewards receive advance notification before purges.
- A `RetentionRun` record documents every action taken for audit
  purposes.
- An `AUDIT_RETENTION_POLICY_CREATED` and `AUDIT_RETENTION_EXECUTED`
  event are recorded in the [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Invalid cron expression | `422 Unprocessable Entity` |
| Invalid ISO 8601 duration | `422 Unprocessable Entity` |
| Asset locked during purge | Action deferred to next run with warning |
| Partial failure | Run status `PARTIAL_FAILURE`; unprocessed assets retried next cycle |

## Related

- Concepts: [Governance](../../concepts/governance.md), [Assets](../../concepts/assets.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-CPO-009 -- Configure Automated Retention](../journeys/JOURNEY-CPO-009.md), [JOURNEY-CPO-010 -- Review Retention Reports](../journeys/JOURNEY-CPO-010.md)
- Personas: [Compliance & Privacy Officer](../personas/compliance-privacy-officer/index.md)
