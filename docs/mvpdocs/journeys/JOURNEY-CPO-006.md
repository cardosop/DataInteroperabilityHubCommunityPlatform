# JOURNEY-CPO-006: Configure Automated Compliance

**Persona:** [Compliance & Privacy Officer](../personas/compliance-privacy-officer/)
**Use Cases:** UC-COMP-003, UC-COMP-004

## Overview

A Compliance Officer sets up automated compliance scanning so that
every new data ingestion or asset update is automatically evaluated
against regulatory policies. This journey covers creating compliance
policies, defining event-based triggers, setting risk thresholds, and
enabling auto-scan on data ingest to ensure continuous compliance
without manual intervention.

## Journey Steps

1. **Create policy** — The CPO navigates to "Compliance > Policies"
   and creates a new compliance policy. A policy groups one or more
   scan profiles with enforcement rules. The CPO names the policy
   (e.g., "GDPR Auto-Scan"), selects the applicable regulation
   framework, and defines which [asset](../concepts/assets.md) tags
   or domains the policy applies to (e.g., all assets tagged
   `contains-pii` or in the `customer` domain).

2. **Define triggers** — The CPO configures when the policy
   automatically executes:

   - **On ingest:** Scan runs immediately after a new data file is
     uploaded or attached to an asset.
   - **On schema change:** Scan runs when the asset schema is modified.
   - **On schedule:** Scan runs on a cron schedule (e.g., weekly).
   - **On contract update:** Scan runs when the bound
     [data contract](../concepts/contracts.md) is updated.

   Multiple triggers can be combined. Each trigger is recorded in the
   policy configuration.

3. **Set thresholds** — The CPO defines what happens when a scan
   completes based on the risk level:

   - `LOW`: Asset passes; no action required.
   - `MEDIUM`: Asset passes with a warning badge; notification sent
     to the asset owner.
   - `HIGH`: Asset is flagged; publication is blocked until findings
     are resolved.
   - `CRITICAL`: Asset is quarantined; access is restricted to
     compliance officers and the asset owner.

4. **Enable auto-scan on ingest** — The CPO toggles the "Auto-scan
   on ingest" setting at the tenant level or per-policy level. When
   enabled, every `asset.data_uploaded` event triggers the matching
   compliance policy's scan profile. The scan runs asynchronously and
   results are available on the asset's compliance tab and via
   [webhooks](../concepts/webhooks.md).

5. **Test the policy** — The CPO uploads a test dataset to verify
   the policy fires correctly. They confirm the scan ran, the risk
   level was assessed, and the correct enforcement action was taken
   (e.g., blocking publication for HIGH risk). The test run appears
   in the [audit trail](../concepts/audit-events.md).

6. **Monitor policy effectiveness** — The CPO reviews the policy
   dashboard showing scan count, pass/fail rate, most common findings,
   and trend over time. Policies can be edited, disabled, or cloned
   for different regulatory contexts.

## Success Criteria

- The compliance policy is created with correct scope and triggers.
- Auto-scan fires within 60 seconds of a qualifying event.
- Risk thresholds correctly block or flag assets as configured.
- The audit trail records every automated scan with the triggering
  event and policy reference.
- Policy changes are versioned and auditable.

## Related

- Concepts: [Compliance Runs](../concepts/compliance-runs.md), [Governance](../concepts/governance.md), [Webhooks](../concepts/webhooks.md), [Audit Events](../concepts/audit-events.md)
- How-To: [CPO How-To Guides](../personas/compliance-privacy-officer/how-to/)
- Journeys: [JOURNEY-CPO-001](JOURNEY-CPO-001.md) (Run Compliance Scan), [JOURNEY-DE-004](JOURNEY-DE-004.md) (Set Up Compliance Scanning)
