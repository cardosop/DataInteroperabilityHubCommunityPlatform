# Incident Severity Levels & Response SLAs

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Severity Definitions

### SEV1 — Complete Outage (Critical)

The platform or a critical user-facing service is completely unavailable.

- **Definition**: >50% of users unable to access core functionality; API returns >50% 5xx errors; data loss or corruption
- **Response**: Page on-call immediately (PagerDuty)
- **Acknowledgment**: < 5 minutes
- **Resolution target**: < 1 hour
- **Communication**: Status page updated within 15 min; Slack #incidents channel; customer-facing notification within 30 min
- **Escalation**: CTO + VP Engineering if not resolved within 2 hours

### SEV2 — Degraded Service (Warning)

Service is operational but degraded — users affected but workarounds exist.

- **Definition**: Feature unavailable for subset of users; elevated error rates (1-10% 5xx); p95 latency > 2x baseline; compliance/DQ scans failing
- **Response**: Create Jira ticket + notify Slack #incidents channel
- **Acknowledgment**: < 30 minutes (business hours) / < 1 hour (off-hours)
- **Resolution target**: < 4 hours
- **Communication**: Status page updated within 1 hour
- **Escalation**: Engineering lead if not resolved within 8 hours

### SEV3 — Minor Issue (Info)

Low-impact issue that does not affect core functionality.

- **Definition**: Cosmetic bug; non-critical feature degraded; intermittent error affecting <1% of users; documentation gap; deprecation warning
- **Response**: Add to backlog; triage in next sprint planning
- **Acknowledgment**: < 1 business day
- **Resolution target**: Next sprint (or sooner if quick fix)
- **Communication**: Optional — internal only unless customer reports

## Severity Decision Matrix

| Symptom | SEV1 | SEV2 | SEV3 |
|---------|------|------|------|
| API 5xx rate | >50% | 1-50% | <1% |
| Users affected | >50% | 5-50% | <5% |
| p95 latency vs baseline | >10x | 2-10x | <2x |
| Data loss risk | Yes | No | No |
| Workaround exists | No | Yes | N/A |

## On-Call Rotation

- Primary: rotates weekly among Infrastructure Engineering team
- Secondary: rotates weekly among Platform Engineering team
- Escalation: CTO → VP Engineering → CEO (SEV1 only, >4h unresolved)

## Post-Incident

- Postmortem required for all SEV1 and SEV2 incidents
- Template: `docs/operations/postmortem-template.md`
- Review: within 5 business days of resolution
- Track action items in Jira with `incident-followup` label
