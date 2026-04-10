# Incident Response

This page outlines the incident response process for the Meshant
platform. For detailed recovery procedures, see the
[Disaster Recovery](disaster-recovery.md) page and the
[RUNBOOKS.md disaster recovery section](../../RUNBOOKS.md#disaster-recovery).

## Severity Levels

| Level | Description                          | Response Time | Example                          |
|-------|--------------------------------------|---------------|----------------------------------|
| P0    | Platform completely unavailable      | 15 minutes    | All API endpoints returning 5xx  |
| P1    | Major feature broken, no workaround | 30 minutes    | Authentication failing           |
| P2    | Feature degraded, workaround exists  | 2 hours       | Search returning stale results   |
| P3    | Minor issue, cosmetic or edge case   | Next business day | Tooltip misaligned          |

## Escalation Path

1. **On-call engineer** receives the alert via PagerDuty/Slack.
2. If not resolved within the response time, escalate to the
   **engineering lead**.
3. P0/P1 incidents trigger a **war room** in the designated Slack
   channel.
4. If infrastructure is involved, loop in the **platform/infra lead**.

## Response Steps

1. **Acknowledge** the alert and join the incident channel.
2. **Assess** severity using the table above.
3. **Investigate** using health checks, logs, and dashboards:
   - [Health Checks](health-checks.md)
   - [Monitoring](monitoring.md)
4. **Mitigate** -- apply a fix or roll back:
   - `helm rollback meshant <revision>` for deployment issues
   - See [RUNBOOKS.md](../../RUNBOOKS.md) for service-specific runbooks
5. **Communicate** status updates every 30 minutes for P0/P1.
6. **Resolve** and confirm with health checks.

## Post-Mortem

After every P0/P1 incident:

1. Write a blameless post-mortem within 48 hours.
2. Identify root cause and contributing factors.
3. Define action items with owners and deadlines.
4. Review in the next team meeting.

## Related

- [Disaster Recovery](disaster-recovery.md) -- RTO/RPO and failover
- [Monitoring](monitoring.md) -- dashboards and alerting
- [RUNBOOKS.md](../../RUNBOOKS.md) -- full operator runbooks
