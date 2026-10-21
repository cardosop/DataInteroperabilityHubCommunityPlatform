# Change Freeze Calendar

**Version**: 1.0 | **Owner**: Infrastructure Engineering
**Aligned with**: `production-deployment-runbook.md`

## Quarterly Maintenance Windows

| Quarter | Window | Type | Notes |
|---------|--------|------|-------|
| Q1 | Jan 15–17 | Maintenance | Post-holiday stabilization |
| Q2 | Apr 10–12 | Maintenance | Pre-Q2 feature release |
| Q3 | Jul 10–12 | Maintenance | Mid-year infrastructure updates |
| Q4 | Oct 15–17 | Maintenance | Pre-holiday freeze prep |

## Freeze Dates

| Period | Dates | Scope |
|--------|-------|-------|
| **Winter freeze** | Dec 15 – Jan 2 | No non-critical deploys; security patches only |
| **Summer freeze** | Aug 1–15 | Reduced deploy velocity; no major refactors |
| **Black Friday/Cyber Monday** | Nov 25–30 | Full freeze; on-call only |

## Exception Process

1. File exception request in `#incidents` Slack with:
   - What you're deploying
   - Why it can't wait
   - Risk assessment (blast radius, rollback plan)
2. Get approval from Engineering Lead + on-call
3. Deploy with heightened monitoring for 1 hour post-deploy
4. Document exception in post-freeze review

## Communication

- Freeze dates published in `#engineering` Slack 2 weeks in advance
- Calendar invites sent to engineering@meshant.com
- Status page banner during freeze windows

## Post-Freeze Review

After each freeze:
1. Count exceptions filed + approved/rejected
2. List any incidents during freeze
3. Recommend process changes for next freeze
4. Document findings in `docs/operations/freeze-reviews/YYYY-MM.md`
