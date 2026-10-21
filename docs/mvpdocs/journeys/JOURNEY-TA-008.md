# JOURNEY-TA-008: Configure Integration Ecosystem

**Persona:** [Marketplace & Platform Admin](../personas/marketplace-platform-admin/)
**Use Cases:** UC-TA-002, UC-INT-001

## Overview

A Tenant Admin configures integrations with external systems to extend
the Meshant platform's connectivity. This journey covers reviewing
available connectors, enabling integrations, configuring credentials,
testing connections, and monitoring ongoing sync status to ensure data
flows reliably between Meshant and the broader data ecosystem.

## Journey Steps

1. **Review available connectors** — The admin navigates to "Admin >
   Integrations" and browses the connector catalog. Connectors are
   grouped by category:

   - **Cloud storage:** AWS S3, Google Cloud Storage, Azure Blob.
   - **Databases:** PostgreSQL, MySQL, Snowflake, BigQuery, Redshift.
   - **Data catalogs:** Apache Atlas, DataHub, Collibra.
   - **Observability:** Datadog, Grafana, PagerDuty.
   - **Messaging:** Slack, Microsoft Teams, email (SMTP).
   - **Orchestration:** Airflow, Dagster, Prefect.

   Each connector card shows its status (available, beta, coming soon),
   required credentials, and supported data flow directions (inbound,
   outbound, bidirectional).

2. **Enable integration** — The admin selects a connector and clicks
   "Enable." The platform presents a configuration form specific to
   the connector type. The admin provides required parameters such as
   endpoint URL, region, and authentication method (API key, OAuth,
   IAM role).

3. **Configure credentials** — The admin enters credentials securely.
   Credentials are encrypted at rest using AES-256 and stored in the
   platform's secrets vault. For cloud providers the admin can
   configure IAM role-based access (no long-lived keys). Credential
   rotation schedules can be set with reminders.

4. **Test connection** — The admin clicks "Test Connection." The
   platform attempts a lightweight operation against the external
   system (e.g., listing buckets for S3, running `SELECT 1` for
   databases). The test result shows success or failure with
   diagnostic details (HTTP status, error message, latency).
   A successful test is required before the integration can be
   activated.

5. **Activate and configure sync** — Once tested the admin activates
   the integration and configures sync behavior:

   - **Frequency:** Real-time (webhook-driven), scheduled (cron), or
     manual.
   - **Direction:** Inbound (pull data into Meshant), outbound (push
     events/data out), or bidirectional.
   - **Scope:** All [assets](../concepts/assets.md) or filtered by
     domain, tag, or specific asset IDs.
   - **Mapping:** Field mapping between Meshant metadata and the
     external system's schema.

6. **Monitor sync status** — The admin views the integration health
   dashboard showing each active integration's status (healthy,
   degraded, error), last sync timestamp, records processed, error
   count, and average latency. Failed syncs are retried automatically
   (exponential backoff, max 3 retries) and flagged in the
   [audit trail](../concepts/audit-events.md) with error details.

## Success Criteria

- Available connectors are displayed with accurate status and
  requirements.
- Credentials are stored encrypted and never exposed in logs or UI.
- Connection test succeeds before activation is allowed.
- Sync operates at the configured frequency without manual
  intervention.
- The health dashboard reflects real-time integration status.
- All integration operations produce audit events.

## Related

- Concepts: [Webhooks](../concepts/webhooks.md), [Assets](../concepts/assets.md), [Audit Events](../concepts/audit-events.md), [Tenants](../concepts/tenants.md)
- How-To: [MPA How-To Guides](../personas/marketplace-platform-admin/how-to/)
- Journeys: [JOURNEY-TA-007](JOURNEY-TA-007.md) (Monitor Costs), [JOURNEY-PA-001](JOURNEY-PA-001.md) (Onboard Instance)
