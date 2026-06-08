# Maintenance Window Communication Template (280.C.6.8)

**Purpose:** Standardized communication for scheduled maintenance windows.  
**Audience:** Tenant administrators (email) + platform status page.  
**Owner:** Platform Engineering  

---

## Template: Scheduled Maintenance Notification

### Subject

```
[NON-URGENT] Scheduled Maintenance — Meshant Hub — {DATE} {START_TIME}–{END_TIME} {TIMEZONE}
```

### Body

```
Dear {TENANT_NAME} Administrator,

Meshant Hub will undergo scheduled maintenance on:

  Date:    {DAY_OF_WEEK}, {MONTH} {DAY}, {YEAR}
  Window:  {START_TIME} – {END_TIME} {TIMEZONE}
           ({DURATION_HOURS} hour window; expected impact: {EXPECTED_DOWNTIME_MINUTES} minutes)

TYPE OF MAINTENANCE
  {MAINTENANCE_TYPE}
  {MAINTENANCE_DESCRIPTION}

SERVICE IMPACT
  During the window, the following services may be intermittently unavailable:

  [ ] API (REST + WebSocket)         — {API_IMPACT}
  [ ] Frontend (meshant.com)         — {FRONTEND_IMPACT}
  [ ] Marketplace listings           — {MARKETPLACE_IMPACT}
  [ ] File uploads                   — {UPLOAD_IMPACT}
  [ ] Compliance scans               — {COMPLIANCE_IMPACT}
  [ ] Webhook deliveries             — {WEBHOOK_IMPACT}
  [ ] Search                         — {SEARCH_IMPACT}

  A status page will be updated throughout the window:
    https://meshant-internal.example.com

WHAT YOU NEED TO DO
  {ACTION_REQUIRED}

POST-MAINTENANCE
  We will send a follow-up email when the maintenance is complete.
  If you experience issues after the window, contact:
    Email: support@meshant.com
    Emergency: +1-XXX-XXX-XXXX (PagerDuty on-call)

SCHEDULED BY
  {ENGINEER_NAME}, Platform Engineering
  {SLACK_HANDLE}

This maintenance has been reviewed and approved per our change management policy.

—
Meshant Platform Team
```

---

## Template: Maintenance Complete

### Subject

```
[COMPLETE] Scheduled Maintenance — Meshant Hub — {DATE}
```

### Body

```
Dear {TENANT_NAME} Administrator,

The scheduled maintenance on {DATE} has been completed.

  Start:   {ACTUAL_START_TIME} {TIMEZONE}
  End:     {ACTUAL_END_TIME} {TIMEZONE}
  Duration: {ACTUAL_DURATION} ({PLANNED_DURATION} planned)

CHANGES APPLIED
  {CHANGE_SUMMARY}

VERIFICATION
  All post-maintenance checks passed:
  [x] API health endpoint responding (200 OK)
  [x] Login flow functional
  [x] Critical journey smoke tests passed
  [x] All pods healthy in hub-production namespace
  [x] Synthetic probes green (login, asset_list, search, health)
  [x] No SEV1 alerts triggered

KNOWN ISSUES
  {KNOWN_ISSUES_OR_NONE}

If you encounter any issues, please contact support@meshant.com.

—
Meshant Platform Team
```

---

## Template: Emergency Maintenance (SEV1)

### Subject

```
[URGENT] Emergency Maintenance — Meshant Hub — In Progress
```

### Body

```
We are performing emergency maintenance on Meshant Hub to address a critical issue.

  Started: {START_TIME} {TIMEZONE}
  Impact:  Service disruption expected for approximately {ESTIMATED_DURATION}

ISSUE: {BRIEF_DESCRIPTION}

We will send an update when service is restored. Status page:
  https://meshant-internal.example.com

For urgent concerns: +1-XXX-XXX-XXXX (on-call engineer)

—
Meshant Platform Team
```

---

## Template Variables Reference

| Variable | Source | Example |
|---|---|---|
| `{TENANT_NAME}` | Tenant record | "Acme Corp" |
| `{DAY_OF_WEEK}` | Calendar | "Wednesday" |
| `{MONTH} {DAY}, {YEAR}` | Calendar | "May 21, 2026" |
| `{START_TIME}` | Deploy schedule | "02:00" |
| `{END_TIME}` | Deploy schedule | "04:00" |
| `{TIMEZONE}` | Constant | "UTC" |
| `{DURATION_HOURS}` | Calculated | "2" |
| `{EXPECTED_DOWNTIME_MINUTES}` | Engineering estimate | "5" |
| `{MAINTENANCE_TYPE}` | Change record | "Database version upgrade" |
| `{MAINTENANCE_DESCRIPTION}` | Change record | "Upgrading Aurora PostgreSQL from 16.3 to 16.4" |
| `{API_IMPACT}` | Engineering estimate | "Intermittent 503 during DB failover (~60s)" |
| `{ENGINEER_NAME}` | Deployer | "Jane Smith" |
| `{SLACK_HANDLE}` | Deployer | "@jane" |

## Communication Cadence

| Event | Channel | Timing |
|---|---|---|
| Initial notice | Email to tenant admins | ≥72 hours before window |
| Reminder | Email + status page banner | 24 hours before window |
| Window start | Status page update | At window open |
| Window end | Status page update + email | Within 15 min of completion |
| Emergency | Email + status page + Slack #meshant-incidents | Immediately |
