# Phase 228 — Lineage announcement & sales enablement

**Phase:** 228 (overall — 228.0/F1/F2/F3/F4/F5)
**Owner:** Product Marketing + Customer Success
**Status:** TEMPLATE — fills out at GA cutover
**Last reviewed:** 2026-05-01

This is the GA announcement template that Product Marketing fills
out as each phase reaches 100% rollout (228.DoD.4 + the per-phase
DoD.6/DoD.8 production rollout completions). It is intentionally
phase-by-phase so a partial-GA shipment doesn't force a single
"Phase 228 complete" all-or-nothing announcement.

## Phase-by-phase checklist

For each phase: cut a customer-facing announcement (web post +
email + in-app banner) on the day the global capability flag flips
ON. The announcement template below is the canonical body; adjust
the phase-specific section + embed the user guide link.

### 228.F1 — Cross-tenant marketplace lineage

- [ ] Web post drafted (path: `/blog/lineage-cross-tenant-rolls-out`)
- [ ] Email subject: "Lineage now visible across the marketplace"
- [ ] In-app banner copy approved
- [ ] User guide linked: [docs/user-guides/lineage-f1.md](../user-guides/lineage-f1.md)
- [ ] Sales deck slide updated: "F1 — see upstream lineage on every listing"
- [ ] Date sent: _YYYY-MM-DD_

### 228.F2 — Field-level mapping editor

- [ ] Web post drafted
- [ ] In-app banner copy approved
- [ ] User guide linked: [docs/user-guides/lineage-f2.md](../user-guides/lineage-f2.md)
- [ ] Sales deck slide updated
- [ ] Date sent: _YYYY-MM-DD_

### 228.F3 — Change-impact notifications

- [ ] Web post drafted
- [ ] User guide linked: [docs/user-guides/lineage-f3.md](../user-guides/lineage-f3.md)
- [ ] Sales deck slide updated
- [ ] Date sent: _YYYY-MM-DD_

### 228.F4 — OpenLineage integration *(spec-explicit)*

The 228.DoD.4 spec text calls out F4 specifically — the OpenLineage
launch is the most externally-visible piece of Phase 228 because
it adds an industry-standard endpoint that customers' Airflow / dbt /
custom producers can integrate with.

- [ ] Web post drafted (path: `/blog/openlineage-integration-ga`)
- [ ] Email subject: "Meshant now speaks OpenLineage"
- [ ] In-app banner copy approved
- [ ] User guide linked: [docs/user-guides/lineage-f4.md](../user-guides/lineage-f4.md)
- [ ] **Sales enablement deck dedicated slide** added
      (`enablement/lineage-f4-openlineage.pptx`):
  - "Why OpenLineage" — adoption + ecosystem talking points.
  - "How it works" — outbound + inbound flow diagram.
  - "Customer onboarding" — link to quick-start in the user guide.
  - "Troubleshooting" — link to DLQ + Marquez outage runbooks.
- [ ] Bug-bounty scope page updated: [SECURITY.md](../../SECURITY.md)
      already lists `/api/v1/lineage/openlineage/events/` +
      `/api/v1/lineage/openlineage/keys/`; verify on cutover day.
- [ ] Customer-success training session held (228.X.12 cadence).
- [ ] Date sent: _YYYY-MM-DD_

### 228.F5 — Time-travel + diff

- [ ] Web post drafted
- [ ] User guide linked: [docs/user-guides/lineage-f5.md](../user-guides/lineage-f5.md)
- [ ] Sales deck slide updated
- [ ] Date sent: _YYYY-MM-DD_

## Body template (per-phase customisation)

```text
Subject: <one-line value prop, customer-facing>

We just shipped <Phase N>: <one-line "what does it do">.

Why it matters
--------------
<2-3 bullets — outcome-focused, not feature-focused>

How to use it
-------------
<2-3 bullets — including a "where do I click" reference>

Read the full guide:
<link to docs/user-guides/lineage-fN.md>

Have feedback? Reply to this email or contact your CS rep.
```

## Sales enablement deck

Single source of truth: `enablement/lineage-228.pptx` (in the
internal SharePoint). Each phase's slide is updated AT cutover, NOT
in advance — so the deck always reflects what's actually shipped.

Master deck table-of-contents:

| Slide | Phase | Owner |
|---|---|---|
| 1 | Phase 228 overview | Product Marketing |
| 2 | F1 — Cross-tenant marketplace lineage | Product Marketing |
| 3 | F2 — Field-level mapping | Product Marketing |
| 4 | F3 — Change-impact notifications | Product Marketing |
| 5 | F4 — OpenLineage integration | **Spec-explicit, Product Marketing** |
| 6 | F5 — Time-travel + diff | Product Marketing |
| 7 | Roadmap (post-228) | Product Lead |

## Sign-off

| Role | Name | Date |
|---|---|---|
| Product Marketing | _to be filled_ | _YYYY-MM-DD_ |
| Customer Success | _to be filled_ | _YYYY-MM-DD_ |
| Engineering Lead | _to be filled_ | _YYYY-MM-DD_ |

228.DoD.4 closes once every phase row above has a non-empty "Date
sent" + the F4-dedicated sales enablement slide is in the deck.
