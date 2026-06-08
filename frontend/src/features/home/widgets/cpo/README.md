# Chief Product Officer Widgets

**Persona:** CPO (PLATFORM_ADMIN role)
**Label:** "Chief Product Officer"

## Widget specs

### Pending Approvals Card (already rendered in RoleDashboard)
- **Data source:** `useAccessRequests({ status: 'PENDING', page_size: 1 })`
- **Display:** Count of pending access requests requiring review
- **Link:** `/governance/my-approvals`

### Tenant Health Overview
- **Data source:** `useAssets({ page_size: 1 })` aggregated across tenants
- **Display:** "N tenants · M assets · K listings"
- **Link:** `/admin/tenants`

### Billing Overview
- **Data source:** billing usage endpoint (TBD)
- **Display:** Current month cost, MoM trend, projected month-end
- **Link:** `/billing`

### Marketplace Performance
- **Data source:** `useOrders({ page_size: 1 })` aggregated
- **Display:** Total orders this month, conversion rate, GMV
- **Link:** `/marketplace/admin`

### Quick actions
- **"Manage Tenants"** → `/admin/tenants`
- **"Billing Reports"** → `/billing/reports`
