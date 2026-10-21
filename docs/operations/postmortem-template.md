# Postmortem: [INCIDENT TITLE]

| Field | Value |
|-------|-------|
| **Incident ID** | INC-YYYY-NNN |
| **Date** | YYYY-MM-DD |
| **Severity** | SEV1 / SEV2 |
| **Duration** | Xh Ym (HH:MM–HH:MM UTC) |
| **Author** | Name (role) |
| **Status** | Draft / Reviewed / Closed |

## Timeline (UTC)

| Time | Event |
|------|-------|
| HH:MM | [Detection] — how was the incident discovered? (alert, user report, etc.) |
| HH:MM | [Acknowledgment] — on-call acknowledged |
| HH:MM | [Diagnosis] — root cause identified |
| HH:MM | [Mitigation] — temporary fix applied |
| HH:MM | [Resolution] — permanent fix deployed |
| HH:MM | [Verification] — confirmed resolved via monitoring |

## Impact

- **Users affected**: [number or percentage]
- **Services degraded**: [list affected services]
- **Data loss**: [none / describe]
- **Revenue impact**: [none / estimate]

## Root Cause

[Detailed technical explanation of what caused the incident. Be specific — reference code paths, config changes, infrastructure events.]

## Resolution

[What was done to resolve the incident. Distinguish temporary mitigations from permanent fixes.]

## Detection

- **How was it detected**: [alert / user report / proactive monitoring]
- **Time to detect**: [minutes from onset to detection]
- **Could detection have been faster?**: [analysis]

## Action Items

| # | Action | Owner | Due | Status |
|---|--------|-------|-----|--------|
| 1 | [Immediate fix — e.g. revert config change] | | | |
| 2 | [Prevent recurrence — e.g. add validation] | | | |
| 3 | [Improve detection — e.g. add alert] | | | |
| 4 | [Improve response — e.g. update runbook] | | | |

## Lessons Learned

- **What went well**: [aspects of detection, diagnosis, resolution that worked]
- **What went poorly**: [gaps in monitoring, runbooks, communication, tooling]
- **What we'll change**: [concrete process or system improvements]

## Appendix

- [Link to monitoring dashboards during incident window]
- [Link to relevant Slack threads]
- [Link to relevant PRs / commits]
