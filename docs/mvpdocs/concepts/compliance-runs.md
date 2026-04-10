# Compliance Runs

A compliance run is an automated scan of a data [asset](assets.md) that detects personally identifiable information (PII), sensitive data categories, and regulatory risk. Each run produces a risk assessment with a `risk_level` (low, medium, high, critical), a list of detected data categories (email addresses, credit card numbers, health records, etc.), and actionable findings that guide remediation.

Compliance runs are essential for organizations operating under GDPR, CCPA, HIPAA, or other data protection regulations. They integrate with the broader [governance](governance.md) framework to enforce automated compliance policies before data can be published or shared through the [Marketplace](marketplace-listings.md).

## Lifecycle

| State | Description |
|---|---|
| `PENDING` | The compliance scan is queued. Waiting for scanner capacity. |
| `RUNNING` | Scanners are actively inspecting the asset's data. Classification models are evaluating column content and sampling rows. |
| `SUCCEEDED` | Scanning completed. Results are available, including detected categories, risk level, and per-column findings. |
| `FAILED` | An infrastructure error prevented the scan from completing. The run can be retried. |
| `CANCELLED` | The scan was stopped before completion. Partial results may be available. |

As with [DQ runs](dq-runs.md), a `SUCCEEDED` status means the scan infrastructure worked correctly. The results within the run may show high risk levels and numerous findings.

## Risk Classification

| Risk Level | Criteria |
|---|---|
| `low` | No PII or sensitive data detected. Only public or anonymized data found. |
| `medium` | Indirect identifiers detected (zip codes, age ranges, job titles). Re-identification risk is low but non-zero. |
| `high` | Direct PII detected (names, email addresses, phone numbers). Requires access controls and may need consent tracking. |
| `critical` | Highly sensitive data detected (SSN, credit card numbers, health records, biometric data). Requires encryption, strict access controls, and regulatory reporting. |

The risk level is computed from the most sensitive category detected. A single column containing credit card numbers elevates the entire asset to `critical`, regardless of how many other columns are benign.

## Detection Categories

The compliance scanner recognizes the following data categories out of the box:

| Category | Examples | Default Risk Level |
|---|---|---|
| Full name | "Jane Smith", "Carlos Rodriguez" | high |
| Email address | "user@example.com" | high |
| Phone number | "+1-555-0123", "07700 900000" | high |
| Postal address | Street addresses, zip/postal codes | medium (full address: high) |
| Date of birth | "1990-03-15", "15/03/1990" | high |
| SSN / National ID | "123-45-6789", national ID patterns | critical |
| Credit card number | PAN patterns (Luhn-validated) | critical |
| Health record | ICD codes, diagnosis text, medication names | critical |
| Financial account | IBAN, routing numbers, account numbers | critical |
| IP address | IPv4 and IPv6 addresses | medium |
| Geolocation | Latitude/longitude coordinates | medium |

Each finding includes a confidence score (0.0 to 1.0) indicating how certain the classifier is about the detection. Findings with confidence below 0.5 are flagged as "possible" rather than "confirmed".

## Relationships

- **Assets** -- Each compliance run targets an [asset](assets.md). The asset's compliance status badge reflects the most recent scan results.
- **Governance** -- [Governance](governance.md) policies define the acceptable risk threshold per tenant. Assets exceeding the threshold are blocked from publishing.
- **Audit Events** -- Compliance run creation, completion, and findings are logged as [audit events](audit-events.md). These records support regulatory reporting and audit readiness.
- **Jobs** -- Each compliance run is managed as a [job](jobs.md), with standard progress tracking, timeout, and retry behavior.
- **Datasets** -- Scanners inspect the physical data within the asset's [datasets](datasets.md), sampling rows and analyzing column content.
- **Webhooks** -- The `compliance.completed` event fires on scan completion, delivering the risk level and summary to configured [webhook](webhooks.md) endpoints.
- **Orchestration** -- Compliance runs are commonly chained after [DQ runs](dq-runs.md) in [orchestration](orchestration.md) workflows: first validate quality, then scan for compliance risk.

## MVP Scope

**Available at launch:**

- Manual compliance run triggering via API, CLI, and SDK.
- Automatic triggering as part of asset validation workflow.
- PII detection for common categories: names, emails, phone numbers, addresses, SSN, credit card numbers, dates of birth.
- Risk level classification (low, medium, high, critical).
- Per-column findings with confidence scores.
- Detected category listing with occurrence counts.
- Webhook notification on scan completion.
- Historical scan results for trend analysis.

**Post-MVP:**

- Custom sensitive data category definitions (regex-based and ML-based).
- Automatic data masking and tokenization suggestions.
- Regulatory mapping (GDPR Article references, CCPA category mapping).
- Continuous compliance monitoring for streaming assets.
- Cross-asset compliance reports for tenant-wide risk dashboards.
- Integration with external DLP tools (Google DLP, AWS Macie).

## API Reference

| Operation | API | CLI | SDK |
|---|---|---|---|
| Trigger scan | `POST /api/v1/compliance-runs` | `meshant compliance run <asset_id>` | `client.compliance_runs.create(asset_id)` |
| Get scan | `GET /api/v1/compliance-runs/{id}` | `meshant compliance get <id>` | `client.compliance_runs.get(id)` |
| List scans | `GET /api/v1/compliance-runs` | `meshant compliance list` | `client.compliance_runs.list()` |
| Get findings | `GET /api/v1/compliance-runs/{id}/findings` | `meshant compliance findings <id>` | `client.compliance_runs.findings(id)` |
| Cancel scan | `POST /api/v1/compliance-runs/{id}/cancel` | `meshant compliance cancel <id>` | `client.compliance_runs.cancel(id)` |

See the full [API Reference](/docs/mvpdocs/api-reference) and [CLI Reference](/docs/mvpdocs/cli-reference) for scan configuration and category filtering.
