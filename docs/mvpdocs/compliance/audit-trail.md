# Audit Trail

The Meshant audit trail provides an immutable, append-only record of every
significant action performed on the platform. It answers the four essential
audit questions -- **who** performed the action, **what** was changed, **when**
the change occurred, and **where** (which resource and region) it happened.

## Event Structure

Every audit event contains the following fields:

| Field | Description |
|---|---|
| `event_id` | Globally unique identifier (UUID v4) |
| `timestamp` | ISO 8601 timestamp with microsecond precision (UTC) |
| `actor` | User ID or service account that triggered the action |
| `action` | Machine-readable action code (e.g. `asset.created`, `compliance_run.completed`) |
| `resource_type` | Entity type affected (asset, dataset, tenant, user, listing, etc.) |
| `resource_id` | ID of the affected resource |
| `tenant_id` | Owning tenant |
| `region` | Storage region where the event was recorded |
| `detail` | JSON object with action-specific payload (before/after values, parameters) |
| `ip_address` | Source IP of the request |

See the [Audit Events concept](../concepts/audit-events.md) for the full
taxonomy of action codes.

## Immutability

Audit events are written to an append-only store. Once persisted, an event
cannot be modified or deleted by any user, including platform operators. The
storage layer uses cryptographic chaining so that any tampering with historical
records is detectable.

## Retention

The default retention period is **three years** from the event timestamp. Events
past the retention cutoff are marked as archived (`is_archived=True`) by the
`archive_old_audit_events` management command. Archived events are excluded
from default API queries but remain in the database for compliance access.

Run the archival command periodically (e.g., weekly via CronJob):

```bash
python manage.py archive_old_audit_events            # archive events > 3 years
python manage.py archive_old_audit_events --dry-run   # preview without changes
python manage.py archive_old_audit_events --retention-years 7  # SOX compliance
```

Tenants subject to regulations with longer retention requirements (for example,
certain SOX interpretations require seven years) can configure a longer period
via the `--retention-years` flag or the `AUDIT_RETENTION_YEARS` setting.

## Querying and Filtering

The audit API supports filtering by any combination of the following parameters:

- **Date range** -- `from` and `to` timestamps
- **Actor** -- one or more user IDs
- **Action** -- one or more action codes (supports wildcard, e.g. `asset.*`)
- **Resource type and ID** -- narrow to a specific entity
- **Tenant** -- required for non-superadmin callers (enforced by RBAC)

Example request:

```text
GET /api/v1/audit-events?from=2026-01-01T00:00:00Z&to=2026-03-31T23:59:59Z&action=asset.*&actor=user_42
```

Results are paginated using cursor-based pagination. See the
[API reference](../api-reference/) for full details.

## Export

Audit events can be exported in two formats:

- **CSV** -- suitable for spreadsheet analysis and regulatory submissions.
- **JSON** -- suitable for ingestion into SIEM or log-aggregation systems.

Export is available through both the API (`POST /api/v1/audit-events/export`)
and the CLI (`datahub audit export`). Exports respect the same RBAC rules as
the query API -- a user can only export events for tenants they have access to.

## Integration with Compliance Runs

Every [compliance run](../concepts/compliance-runs.md) generates a pair of audit
events: one when the run starts and one when it completes (with the pass/fail
result). This provides a continuous, auditable record of compliance enforcement.

## Further Reading

- [Audit Events concept](../concepts/audit-events.md)
- [Compliance Runs concept](../concepts/compliance-runs.md)
- [Regulations](regulations.md)
- [Security Posture](security-posture.md)
