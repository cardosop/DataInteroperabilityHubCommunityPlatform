# UC-GOV-ADV-001: Configure Automated Compliance

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_compliance_commands_real_api.py::test_automated_compliance`

## Description

A Compliance & Privacy Officer configures automated compliance scanning
policies so that every new or updated asset is automatically scanned
against the tenant's regulatory requirements. This eliminates the need
for manual, ad-hoc scans and ensures continuous compliance coverage
across the data catalog.

## Preconditions

- The user holds the `COMPLIANCE_OFFICER` or `PLATFORM_ADMIN` role.
- The compliance scanning service is deployed and healthy.
- At least one compliance policy template exists (GDPR, CCPA, HIPAA,
  or custom).
- The tenant has assets registered in the catalog.

## Steps

1. CPO navigates to "Governance > Compliance Policies" or calls
   `GET /api/v1/compliance/policies` to list existing policies.
2. CPO creates or updates an automated scanning policy via
   `POST /api/v1/compliance/policies` with:
   - **Name / description:** Human-readable identifier.
   - **Trigger:** `ON_ASSET_CREATE`, `ON_ASSET_UPDATE`,
     `ON_SCHEDULE` (cron expression), or `ON_PUBLISH`.
   - **Scope:** All assets, specific domains, specific tags, or
     explicit asset IDs.
   - **Rule set:** Regulations to evaluate (GDPR, CCPA, HIPAA) and
     PII categories to detect.
   - **Severity threshold:** Minimum finding severity that blocks
     downstream actions (e.g., `HIGH` blocks marketplace publication).
3. The API validates the policy configuration and returns `201 Created`
   with the `policy_id`.
4. CPO optionally configures notification rules for policy violations:
   `POST /api/v1/compliance/policies/{id}/notifications` with
   `{ channels: ["email", "in_app"], recipients: [steward, cpo] }`.
5. When the trigger condition is met (e.g., a new asset is created),
   the platform automatically enqueues a compliance scan (identical to
   [UC-COMP-001](UC-COMP-001.md)) against the matching assets.
6. Scan results are linked to the policy and visible on the
   "Compliance Dashboard" with trend charts showing compliance posture
   over time.
7. CPO reviews the dashboard via
   `GET /api/v1/compliance/dashboard?policy_id={id}` which returns
   aggregate statistics: total scans, pass rate, top PII types found,
   and assets requiring remediation.

## Expected Outcome

- The automated compliance policy is active and triggers scans based
  on the configured conditions.
- New/updated assets within scope are scanned without manual
  intervention.
- Policy violations generate notifications to configured recipients.
- The compliance dashboard shows real-time posture with historical
  trends.
- An `AUDIT_COMPLIANCE_POLICY_CREATED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Invalid cron expression | `422 Unprocessable Entity` |
| Scope references nonexistent domain | `422 Unprocessable Entity` |
| Policy name already exists | `409 Conflict` |
| Scanner service unavailable at trigger time | Scan queued for retry with exponential backoff |

## Related

- Concepts: [Compliance Runs](../../concepts/compliance-runs.md), [Governance](../../concepts/governance.md), [Assets](../../concepts/assets.md)
- Journeys: [JOURNEY-CPO-006 -- Configure Automated Compliance](../journeys/JOURNEY-CPO-006.md)
- Personas: [Compliance & Privacy Officer](../personas/compliance-privacy-officer/index.md)
