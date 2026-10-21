# Developer Widgets

**Persona:** DEV (DEVELOPER role)
**Label:** "Developer"

## Widget specs

### API Keys Card
- **Data source:** BaaS API keys endpoint (TBD)
- **Display:** "N active API keys" with next-expiring key date
- **Link:** `/developer/keys`

### SDK Usage Card
- **Data source:** BaaS usage endpoint (TBD)
- **Display:** Requests this month, error rate, latency p50
- **Link:** `/developer/usage`

### Rate Limit Status
- **Data source:** BaaS quota endpoint or response headers
- **Display:** "N% of monthly quota used" with progress bar
- **Link:** `/developer/usage`

### Developer Portal Quick Link (already rendered in RoleDashboard)
- **Link:** `/developer`

### Quick actions
- **"Create API Key"** → `/developer/keys`
- **"SDK Documentation"** → `/developer/docs`
