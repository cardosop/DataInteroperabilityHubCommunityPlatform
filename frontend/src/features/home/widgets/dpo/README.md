# Data Protection Officer Widgets

**Persona:** DPO (AUDITOR role)
**Label:** "Data Protection Officer"

## Widget specs

### Compliance Posture Card
- **Data source:** `useAssets({ page_size: 1 })` + `useAssets({ compliance_status: 'COMPLIANT', page_size: 1 })`
- **Display:** "N% compliance posture" with trend arrow
- **Link:** `/compliance`

### DSAR Queue Card
- **Data source:** `useAccessRequests({ request_type: 'DSAR', status: 'PENDING', page_size: 1 })`
- **Display:** "N pending DSARs"
- **Link:** `/governance?type=DSAR`

### Breach Alert Card
- **Data source:** breach incidents endpoint (TBD)
- **Display:** "N open breach incidents" (red if >0)
- **Link:** `/governance/breaches`

### Recent Audit Events (already rendered in RoleDashboard)
- **Data source:** `useAuditEvents({ page_size: 5 })`
- **Display:** Last 5 audit events with action, resource type, timestamp
- **Link:** `/audit`

### Quick actions
- **"Run Compliance Scan"** → `/compliance/scan`
- **"GDPR Right to Erasure"** → `/compliance/erasure`
