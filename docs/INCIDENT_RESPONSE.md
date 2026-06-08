# Incident Response Plan

**Owner:** security@meshant.com
**Last updated:** 2026-05-18 (Phase 285.8.2)

## Severity Levels

| Level | Definition | Response Time | Escalation |
|-------|-----------|---------------|------------|
| **SEV0** | Critical: data breach, tenant isolation bypass, RLS failure, credential leak | Immediate (<15 min) | All-hands page, CEO, CISO |
| **SEV1** | High: service outage, auth bypass, MFA bypass, audit log tampering | <30 min | Oncall + Platform Lead |
| **SEV2** | Medium: performance degradation, rate limit misconfiguration, partial outage | <2 hours | Oncall engineer |
| **SEV3** | Low: non-critical bug, cosmetic issue, documentation error | Next business day | Assigned to team |

## Oncall Rotation

| Week | Primary | Secondary |
|------|---------|-----------|
| Week 1 | Platform Lead | Security Lead |
| Week 2 | Data Plane Lead | Infra Lead |
| Week 3 | Privacy Lead | ML Lead |
| Week 4 | Semantic Lead | Integrations Lead |

Rotation managed in PagerDuty. Contact: #oncall Slack channel.

## Detection

- **Prometheus alerts:** `monitoring/prometheus/alerts/*.yml`
- **Grafana dashboards:** `monitoring/grafana/dashboards/`
- **CloudTrail/GuardDuty:** anomalous API patterns → SIEM → PagerDuty
- **Audit events:** `TENANT_FEATURE_FLAG_FLIPPED` (sensitive flags), `RLS_POLICY_BYPASSED`
- **User reports:** security@meshant.com, #security Slack

## Triage

1. **Acknowledge:** Confirm alert in PagerDuty within response time
2. **Assess severity:** Apply severity matrix above
3. **Assemble team:** Page oncall rotation; escalate if needed
4. **Open incident doc:** Create in `docs/incidents/YYYY-MM-DD-<slug>.md`
5. **Communicate:** #incident Slack channel; status page update for SEV0/SEV1

## Containment

1. **Stop the bleeding:** Feature flag toggle, rate limit increase, WAF rule
2. **Isolate:** Restrict affected tenant; rotate compromised credentials
3. **Evidence preservation:** Snapshot logs, audit events, DB state before changes

## Eradication

1. **Root cause:** Identify and fix the underlying vulnerability
2. **Verify fix:** Deploy to staging; run regression tests; verify in production
3. **Scan for similar:** Search codebase for same vulnerability pattern

## Recovery

1. **Restore service:** Remove containment measures
2. **Verify:** Monitor dashboards for 2× normal observation window
3. **Post-mortem:** Schedule within 5 business days (SEV0: within 48 hours)

## Post-Mortem Template

Every SEV0/SEV1 incident produces a post-mortem in `docs/incidents/`:

1. **Summary:** What happened, duration, severity
2. **Timeline:** Key events with timestamps
3. **Root cause:** Technical cause + process gap
4. **Impact:** Tenants affected, data exposed, revenue impact
5. **Remediation:** Immediate fixes deployed
6. **Prevention:** Long-term fixes + process changes
7. **Action items:** Jira tickets with owners + deadlines

## Related

- `docs/SECURITY.md` — vulnerability disclosure policy
- `docs/runbooks/RB-SEC-001-credential-rotation.md`
- `docs/runbooks/RB-SEC-002-cve-remediation.md`
