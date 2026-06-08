# Marketplace Platform Admin Widgets

**Persona:** MPA (TENANT_ADMIN role, marketplace-focused)
**Label:** "Marketplace Administrator"

## Widget specs

### Listing Volume Card
- **Data source:** marketplace listings aggregated count
- **Display:** "N active listings across M tenants"
- **Link:** `/admin/marketplace`

### Order Volume Card
- **Data source:** `useOrders()` aggregated
- **Display:** Orders this month with MoM trend
- **Link:** `/admin/marketplace/orders`

### Provider Onboarding Card
- **Data source:** tenant activation status (TBD)
- **Display:** "N providers onboarding, M active"
- **Link:** `/admin/tenants`

### Pending Approvals (already rendered in RoleDashboard, shared with CPO)
- **Data source:** `useAccessRequests({ status: 'PENDING', page_size: 1 })`
- **Display:** Count of pending access requests
- **Link:** `/governance/my-approvals`

### Quick actions
- **"Manage Listings"** → `/admin/marketplace/listings`
- **"Review KYB Submissions"** → `/admin/kyb`
