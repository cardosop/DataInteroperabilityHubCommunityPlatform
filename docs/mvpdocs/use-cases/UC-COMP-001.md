# UC-COMP-001: Run Compliance Scan

**Persona:** [Compliance & Privacy Officer (CPO)](../personas/compliance-privacy-officer/index.md) / [Data Engineer (DE)](../personas/data-engineer/index.md)
**MVP Tier:** :white_check_mark:
**Phase 216 Test:** `cli/tests/integration/test_compliance_commands_real_api.py::test_compliance_scan`

## Description

A Compliance & Privacy Officer or Data Engineer executes a compliance
scan against a registered asset to detect PII exposure, classify
sensitive columns, evaluate regulatory risk (GDPR, CCPA, HIPAA), and
produce a structured findings report. Compliance scans are a mandatory
gate before marketplace publication.

## Preconditions

- The asset exists with at least one data version uploaded and a
  completed schema inference.
- The user holds `COMPLIANCE_OFFICER`, `DATA_ENGINEER`, or
  `PLATFORM_ADMIN` role.
- The compliance scanning service is running and healthy.
- Applicable compliance policies are configured at the tenant level
  (see [UC-GOV-ADV-001](UC-GOV-ADV-001.md)).

## Steps

1. CPO navigates to the asset's "Compliance" tab and clicks "Run Scan",
   or calls `POST /api/v1/assets/{asset_id}/compliance-runs` with an
   optional `{ policy_ids[] }` to override the default policy set.
2. The API creates a `ComplianceRun` record in `PENDING` status and
   enqueues the scan job. Returns `202 Accepted` with
   `compliance_run_id` and `job_id`.
3. The scanner reads the asset data and evaluates each column against
   the configured policies:
   - **PII detection:** Identifies columns containing names, emails,
     phone numbers, SSNs, IP addresses using pattern matching and ML
     classifiers.
   - **Sensitivity classification:** Labels columns as `PUBLIC`,
     `INTERNAL`, `CONFIDENTIAL`, or `RESTRICTED`.
   - **Regulatory mapping:** Maps findings to applicable regulations
     (GDPR Article 9, CCPA categories, HIPAA identifiers).
   - **Risk scoring:** Assigns a composite risk score (LOW / MEDIUM /
     HIGH / CRITICAL) based on PII density and sensitivity.
4. Results are written to the `ComplianceRun` record with
   `status = COMPLETED`.
5. CPO polls `GET /api/v1/assets/{asset_id}/compliance-runs/{id}` or
   receives a notification on completion.
6. CPO reviews the compliance dashboard:
   - Overall risk level with a color-coded indicator.
   - Column-level findings table (column name, PII type, confidence
     score, regulation, recommended action).
   - Suggested remediation steps (mask, encrypt, remove, or annotate).
7. CPO marks findings as `ACCEPTED`, `MITIGATED`, or `FALSE_POSITIVE`
   via `PATCH /api/v1/compliance-findings/{finding_id}`.

## Expected Outcome

- A `ComplianceRun` record exists with `status = COMPLETED` and
  detailed findings per column.
- The asset's `compliance_status` field is updated (COMPLIANT,
  REVIEW_REQUIRED, or NON_COMPLIANT).
- Blocking findings prevent marketplace publication until resolved.
- An `AUDIT_COMPLIANCE_SCAN_COMPLETED` event is recorded in the
  [audit log](../../concepts/audit-events.md).

## Error Handling

| Condition | Expected Response |
|-----------|-------------------|
| Asset has no data | `422 Unprocessable Entity` |
| Scanner service unavailable | Job status `FAILED` |
| No policies configured | `422` with `NO_POLICIES` code |
| Concurrent scan on same asset | `409 Conflict` |

## Related

- Concepts: [Compliance Runs](../../concepts/compliance-runs.md), [Governance](../../concepts/governance.md), [Assets](../../concepts/assets.md)
- Journeys: [JOURNEY-CPO-001 -- Run Compliance Scan for Asset](../journeys/JOURNEY-CPO-001.md), [JOURNEY-DE-004 -- Set Up Compliance Scanning](../journeys/JOURNEY-DE-004.md)
- Personas: [Compliance & Privacy Officer](../personas/compliance-privacy-officer/index.md), [Data Engineer](../personas/data-engineer/index.md)
