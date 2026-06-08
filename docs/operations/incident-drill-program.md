# Incident Drill Program

**Version**: 1.0 | **Owner**: Infrastructure Engineering

## Quarterly Drill Schedule

Drills run on the first Tuesday of the scheduled month. Each drill has a designated owner and success criteria.

| Quarter | Month | Drill | Description |
|---------|-------|-------|-------------|
| Q1 | March | RDS Failover | Simulate primary RDS failure. Restore from snapshot using `scripts/dr/restore_verify_rds.sh`. Verify app recovers within RTO. |
| Q2 | June | Secret Rotation | Rotate `SECRET_KEY`, `JWT_SECRET_KEY`, and `ENCRYPTION_KEY` in staging. Verify app restarts cleanly with new secrets. Roll back if broken. |
| Q3 | September | Rate-Limit Cascade | Artificially trigger rate limits on search + SPARQL endpoints (reduce throttle to 1/min). Verify 429 responses, retry-after headers, and that non-throttled endpoints remain available. |
| Q4 | December | Compliance Service Degradation | Stop compliance-service container. Verify asset creation degrades gracefully (compliance_status=WARN, asset activates). Verify circuit breaker opens. Restore service; verify circuit closes and backlog clears. |

## Drill Execution

### Before
1. Announce drill date in Slack #incidents ≥ 1 week in advance
2. Verify monitoring is operational (Prometheus + Grafana + PagerDuty)
3. Identify rollback procedure and owner
4. Create calendar invite with Zoom link for observers

### During
1. Start recording in #incidents-drill Slack channel
2. Execute drill per the drill-specific runbook
3. Record timeline, observations, and any surprises
4. If drill causes unexpected SEV1-level impact → abort immediately

### After
1. Document results in `docs/operations/dr-drill-reports/YYYY-MM/drill-<name>.md`
2. File action items as Jira tickets with `drill-followup` label
3. Update runbook if procedure was insufficient or unclear
4. Present findings at next engineering all-hands

## Drill Completion Tracking

Track drill completion via git commits to this file:

| Quarter | Drill | Date | Result | Commit | Operator |
|---------|-------|------|--------|--------|----------|
| 2026-Q1 | (planned) | | | | |
| 2026-Q2 | (planned) | | | | |
| 2026-Q3 | (planned) | | | | |
| 2026-Q4 | (planned) | | | | |

## Success Criteria

- **PASS**: Drill completed within timebox, all success criteria met, no SEV1 escalation
- **PASS WITH ISSUES**: Drill completed but with surprises (e.g. slower recovery than expected; needed manual intervention)
- **FAIL**: Drill aborted due to unexpected impact; recovery exceeded RTO; critical bug discovered

Two consecutive FAIL results for the same drill → escalate to VP Engineering; allocate sprint for remediation.
