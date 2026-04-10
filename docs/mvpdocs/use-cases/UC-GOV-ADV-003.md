# UC-GOV-ADV-003: Manage Consent Tracking

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_compliance_commands_real_api.py::test_consent_tracking`

## Description

A Compliance & Privacy Officer configures and monitors consent records
that track which data subjects have granted (or withdrawn) consent for
specific data processing purposes. The consent ledger provides an
auditable, tamper-evident record that supports GDPR Article 7, CCPA
opt-out, and similar regulatory requirements.

## Preconditions

- The user holds the `COMPLIANCE_OFFICER` or `PLATFORM_ADMIN` role.
- At least one consent purpose has been defined at the tenant level
  (e.g., "Marketing analytics", "Third-party sharing", "Model
  training").
- Assets that process personal data are tagged with the applicable
  consent purposes.

## Steps

1. CPO navigates to "Governance > Consent Management" or calls
   `GET /api/v1/governance/consent-purposes` to list configured
   purposes.
2. CPO creates a new consent purpose (if needed) via
   `POST /api/v1/governance/consent-purposes` with
   `{ name, description, legal_basis, retention_period }`.
   - `legal_basis`: `CONSENT`, `LEGITIMATE_INTEREST`, `CONTRACT`,
     `LEGAL_OBLIGATION`.
   - `retention_period`: Duration the consent record must be retained
     after withdrawal (e.g., `P5Y` for 5 years).
3. The API returns `201 Created` with the `purpose_id`.
4. CPO links the purpose to applicable assets via
   `POST /api/v1/governance/consent-purposes/{id}/assets` with
   `{ asset_ids[] }`.
5. When a data subject grants consent (captured externally or via the
   Meshant intake API), a consent record is created:
   `POST /api/v1/governance/consent-records` with
   `{ subject_id, purpose_id, granted: true, evidence_url }`.
6. When a subject withdraws consent, the record is updated:
   `PATCH /api/v1/governance/consent-records/{id}` with
   `{ granted: false, withdrawn_at }`. The platform flags linked
   assets for processing review.
7. CPO monitors the consent dashboard via
   `GET /api/v1/governance/consent-dashboard` which shows:
   - Total active consents per purpose.
   - Withdrawal rate trend over time.
   - Assets processing data without valid consent (compliance gap).
   - Approaching retention expiry dates.
8. CPO exports the consent ledger for audit via
   `GET /api/v1/governance/consent-records?format=csv&purpose_id={id}`.

## Expected Outcome

- Consent purposes are defined and linked to relevant assets.
- Every consent grant and withdrawal is recorded as an immutable ledger
  entry with a timestamp and evidence reference.
- The dashboard surfaces assets operating without valid consent.
- An `AUDIT_CONSENT_RECORDED` or `AUDIT_CONSENT_WITHDRAWN` event is
  recorded in the [audit log](../../concepts/audit-events.md) for each
  state change.
- The consent ledger is exportable in CSV or JSON for external audits.

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Duplicate consent record (same subject + purpose) | `409 Conflict` |
| Unknown subject identifier | `404 Not Found` |
| Purpose not found | `404 Not Found` |
| Invalid legal basis | `422 Unprocessable Entity` |

## Related

- Concepts: [Governance](../../concepts/governance.md), [Compliance Runs](../../concepts/compliance-runs.md), [Audit Events](../../concepts/audit-events.md)
- Journeys: [JOURNEY-CPO-008 -- Manage Consent Tracking](../journeys/JOURNEY-CPO-008.md)
- Personas: [Compliance & Privacy Officer](../personas/compliance-privacy-officer/index.md)
