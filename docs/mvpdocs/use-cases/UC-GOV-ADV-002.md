# UC-GOV-ADV-002: GDPR Right to be Forgotten

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_compliance_commands_real_api.py::test_gdpr_erasure`

## Description

A Compliance & Privacy Officer processes a GDPR Article 17 erasure
request (Right to be Forgotten) by identifying all assets containing
the data subject's personal data, executing erasure or anonymization
across those assets, and generating a verifiable completion certificate
within the regulatory deadline.

## Preconditions

- The user holds the `COMPLIANCE_OFFICER` or `PLATFORM_ADMIN` role.
- A valid erasure request has been received from a data subject (tracked
  externally or via the Meshant request intake endpoint).
- The compliance scanning service has previously identified PII columns
  in the affected assets (see [UC-COMP-001](UC-COMP-001.md)).
- The tenant has GDPR policies configured (see
  [UC-GOV-ADV-001](UC-GOV-ADV-001.md)).

## Steps

1. CPO creates an erasure request via
   `POST /api/v1/governance/erasure-requests` with
   `{ subject_identifier, identifier_type, reason, deadline }`.
   - `subject_identifier`: The data subject's email, user ID, or other
     unique key.
   - `identifier_type`: `EMAIL`, `USER_ID`, `CUSTOM_KEY`.
   - `deadline`: Regulatory deadline (default: 30 days from request).
2. The API creates an `ErasureRequest` record in `PENDING` status and
   returns `201 Created` with `erasure_request_id`.
3. The platform runs a **subject search** across all assets in the
   tenant, identifying rows containing the subject's identifier in
   PII-tagged columns. Results are stored as `ErasureTarget` records.
4. CPO reviews the impact assessment via
   `GET /api/v1/governance/erasure-requests/{id}/targets` which lists
   affected assets, row counts, and columns.
5. CPO approves the erasure by calling
   `POST /api/v1/governance/erasure-requests/{id}/execute`.
6. The platform executes the erasure strategy per asset:
   - **Hard delete:** Rows are permanently removed.
   - **Anonymization:** PII columns are replaced with anonymized values
     while preserving non-identifying data for analytics.
   - **Tombstone:** Rows are marked as deleted with an erasure
     timestamp.
7. After all targets are processed, the request status moves to
   `COMPLETED`. The platform generates a completion certificate with
   a cryptographic hash of the erasure log.
8. CPO downloads the certificate via
   `GET /api/v1/governance/erasure-requests/{id}/certificate`.

## Expected Outcome

- All identified rows containing the data subject's PII are erased or
  anonymized across every affected asset.
- The `ErasureRequest` record has `status = COMPLETED` with an auditable
  log of every action taken.
- A signed completion certificate is available for regulatory evidence.
- An `AUDIT_ERASURE_COMPLETED` event is recorded in the
  [audit log](../../concepts/audit-events.md).
- Downstream consumers are notified that affected data has changed.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Subject not found in any asset | Request completes with `targets_found = 0` |
| Partial failure (some assets fail) | Request status `PARTIAL_FAILURE`; retry available |
| Deadline approaching without completion | Escalation notification to CPO and admin |
| Asset locked by another operation | Queued for retry after lock release |

## Related

- Concepts: [Governance](../../concepts/governance.md), [Compliance Runs](../../concepts/compliance-runs.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-CPO-007 -- Execute GDPR Right to be Forgotten](../journeys/JOURNEY-CPO-007.md)
- Personas: [Compliance & Privacy Officer](../personas/compliance-privacy-officer/index.md)
