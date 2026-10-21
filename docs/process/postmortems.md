# Postmortem Process

**Owner:** Platform Engineering
**Last reviewed:** 2026-05-13

This document defines when postmortems are required, how they are
conducted, and how they are reviewed.  Every engineer who participates
in the on-call rotation must be familiar with this process.

## When is a postmortem required?

A postmortem is **always required** for:

| Trigger | Rationale |
|---|---|
| **P0 incident** | Platform-wide outage — must understand systemic failure |
| **P1 incident** | Major feature broken for all tenants — prevent recurrence |
| **Security incident** | Any confirmed security breach (regardless of severity) |
| **Data-loss incident** | Any confirmed data loss, corruption, or PII exposure |
| **Customer-visible outage > 5 min** | Even if self-recovered — external trust was impacted |

A postmortem is **required for P2 incidents** if the same root cause
recurs within 30 days (the "repeat P2 → postmortem" rule).

Postmortems are **optional but encouraged** for P2 incidents with
non-trivial customer impact or novel failure modes.

## Timeline

| Milestone | Deadline | Owner |
|---|---|---|
| Draft postmortem | **48 hours** after resolution | Incident Commander (IC) |
| Review with engineering team | **5 business days** after resolution | Engineering lead |
| Publish (internal runbook index) | **10 business days** after resolution | IC + engineering lead |

The 48-hour draft deadline is intentionally tight — the IC's memory
of the incident fades quickly.  The draft does not need to be polished;
it needs to capture the timeline, root cause, and initial prevention
items while they are fresh.

## Template

Postmortems follow the template at
[`docs/runbooks/postmortem-template.md`](../runbooks/postmortem-template.md).
Every postmortem must cover:

1. **Timeline** — all times in UTC; from detection through resolution.
2. **Impact** — users affected, data affected, revenue, regulatory.
3. **Root cause** — 5-whys analysis reaching a systemic finding.
4. **Detection** — how caught, time-to-detect, alert that fired.
5. **Resolution** — steps taken, rollback/restore needed, time-to-resolve.
6. **Prevention items** — each with a single owner and a concrete due date.
7. **Lessons learned** — what went well, poorly, and process changes.

## Conducting the postmortem

1. **The IC owns the draft.**  The IC schedules 30 minutes within 24
   hours of resolution to write the initial timeline and root-cause
   hypothesis.  The template should take < 30 minutes to fill in.

2. **Blameless.**  The postmortem investigates the SYSTEM, not the
   INDIVIDUAL.  "The deploy pipeline did not have a canary stage"
   is a finding; "Alice forgot to test" is not.

3. **5-whys must reach a systemic finding.**  "The certificate expired"
   is not a root cause.  "There is no automated certificate expiry
   alert for non-production environments" IS a root cause.

4. **Prevention items must be actionable and owned.**  "Improve
   monitoring" is not actionable enough.  "Add a Prometheus alert
   `CertExpiryWarning` with a 30-day threshold, owned by @infra-lead,
   due 2026-06-15" IS actionable.

5. **Invite contributors.**  If another engineer contributed to the
   investigation or mitigation, invite them to add to the postmortem
   before review.

## Postmortem review

The engineering team reviews the postmortem in their next weekly
meeting.  The review focuses on:

- **Prevention items:** Are they correctly scoped? Correctly owned?
  On track?  Have any been completed since drafting?
- **Root-cause quality:** Does the 5-whys reach a systemic finding,
  or does it stop at a procedural "someone forgot" explanation?
- **Lessons learned:** Are the process-change recommendations
  concrete enough to implement?

After review, the postmortem status is updated to **Reviewed** and
published to the internal runbook index.

## Postmortem tracking

Completed postmortems are indexed in
[`docs/runbooks/README.md`](../runbooks/README.md) under the
"Postmortems" category.  The engineering lead reviews open prevention
items monthly and escalates any past their due date.

## Graduation criteria

A postmortem is **closed** when all prevention items are either:

- **Completed** (code merged, alert deployed, runbook published), or
- **Accepted** as deferred with a new target phase (documented in
  the item's status column).

The engineering lead owns the decision to accept a deferral.

## Related

- [Incident Response](../../INCIDENT_RESPONSE.md) — the runbook that triggers the postmortem
- [Postmortem Template](../runbooks/postmortem-template.md) — fill-in-the-blank format
- [Runbook Index](../runbooks/README.md) — postmortem archive
- [Security Incident Response](../runbooks/RB-SEC-002-incident-response.md) — security-specific response
- Vendor failure runbooks (`vendor-failure-*.md`) — response-portion examples for third-party incidents

## Maintenance

| Owner | Last reviewed | Next review |
|---|---|---|
| Platform Engineering | 2026-05-13 | 2026-08-11 |
