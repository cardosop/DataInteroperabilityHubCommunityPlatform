# Data Consumer Widgets

**Persona:** DC (DATA_CONSUMER role)
**Label:** "Data Consumer"

## Widget specs

### My Orders Card (already rendered in RoleDashboard)
- **Data source:** `useOrders({ page_size: 1 })`
- **Display:** Count of active orders
- **Link:** `/marketplace/orders`

### My Entitlements Card (already rendered in RoleDashboard)
- **Data source:** `useEntitlements({ page_size: 1 })`
- **Display:** Count of active entitlements
- **Link:** `/marketplace/entitlements`

### Saved Searches Card
- **Data source:** `useSavedSearches()` (from marketplace hooks)
- **Display:** List of saved searches with notification status and last-matched count
- **Empty state:** "No saved searches. Browse the marketplace to save your first search."
- **Link:** `/marketplace/saved-searches`

### Marketplace Recommendations
- **Data source:** `useAssetRecommendations({ limit: 3 })`
- **Display:** Top 3 recommended listings for this consumer
- **Link:** `/marketplace`

### Quick actions
- **"Browse Marketplace"** → `/marketplace`
- **"View My Entitlements"** → `/marketplace/entitlements`
