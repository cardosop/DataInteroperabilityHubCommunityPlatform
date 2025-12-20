# React Query Setup

This document describes the React Query (TanStack Query) setup for the Data Interoperability Hub frontend.

## Overview

React Query is used for server state management, providing:
- Automatic caching and background updates
- Request deduplication
- Optimistic updates
- Error handling and retry logic
- DevTools for debugging

## Configuration

### QueryClient Configuration

The QueryClient is configured in `src/lib/api/react-query.ts` with:

- **Stale Time**: 5 minutes (data is fresh for 5 minutes)
- **Garbage Collection Time**: 10 minutes (unused data stays in cache for 10 minutes)
- **Retry Logic**:
  - Queries: Up to 3 retries for network/server errors, no retries for 4xx errors
  - Mutations: Up to 2 retries for network errors, no retries for 4xx errors
- **Exponential Backoff**: Retry delays increase exponentially (1s, 2s, 4s, ...)
- **Refetch Behavior**:
  - `refetchOnWindowFocus`: false (don't refetch on focus)
  - `refetchOnReconnect`: true (refetch when network reconnects)
  - `refetchOnMount`: true (refetch if data is stale)

### QueryClientProvider Setup

The `ReactQueryProvider` is set up in `main.tsx` and wraps the entire application:

```tsx
<ReactQueryProvider>
  <ThemeProvider>
    <App />
  </ThemeProvider>
</ReactQueryProvider>
```

React Query DevTools are automatically included in development mode (when `VITE_ENABLE_REACT_QUERY_DEVTOOLS=true`).

## Query Key Factories

All query keys are managed through centralized factories for type safety and consistency.

### Usage

```tsx
import { queryKeys } from '@/lib/api'

// List queries
const { data } = useQuery({
  queryKey: queryKeys.assets.list({ status: 'active' }),
  queryFn: () => api.getAssets({ status: 'active' }),
})

// Detail queries
const { data } = useQuery({
  queryKey: queryKeys.assets.detail('asset-123'),
  queryFn: () => api.getAsset('asset-123'),
})

// Search queries
const { data } = useQuery({
  queryKey: queryKeys.assets.search('keyword'),
  queryFn: () => api.searchAssets('keyword'),
})
```

### Available Query Key Factories

#### Assets
- `queryKeys.assets.all` - All asset queries
- `queryKeys.assets.lists()` - All asset list queries
- `queryKeys.assets.list(filters?)` - Specific asset list
- `queryKeys.assets.details()` - All asset detail queries
- `queryKeys.assets.detail(id)` - Specific asset detail
- `queryKeys.assets.search(query)` - Asset search

#### Users
- `queryKeys.users.all` - All user queries
- `queryKeys.users.list(filters?)` - User list
- `queryKeys.users.detail(id)` - User detail
- `queryKeys.users.current` - Current user
- `queryKeys.users.profile(id)` - User profile

#### Workspaces
- `queryKeys.workspaces.all` - All workspace queries
- `queryKeys.workspaces.list(filters?)` - Workspace list
- `queryKeys.workspaces.detail(id)` - Workspace detail
- `queryKeys.workspaces.current` - Current workspace
- `queryKeys.workspaces.members(id)` - Workspace members

#### Connections
- `queryKeys.connections.all` - All connection queries
- `queryKeys.connections.list(filters?)` - Connection list
- `queryKeys.connections.detail(id)` - Connection detail
- `queryKeys.connections.status(id)` - Connection status

#### Data Quality
- `queryKeys.dataQuality.all` - All data quality queries
- `queryKeys.dataQuality.checks()` - All quality checks
- `queryKeys.dataQuality.check(id)` - Specific check
- `queryKeys.dataQuality.results(checkId)` - Check results
- `queryKeys.dataQuality.metrics()` - Quality metrics

#### Compliance
- `queryKeys.compliance.all` - All compliance queries
- `queryKeys.compliance.policies()` - All policies
- `queryKeys.compliance.policy(id)` - Specific policy
- `queryKeys.compliance.violations()` - All violations
- `queryKeys.compliance.violation(id)` - Specific violation

#### Marketplace
- `queryKeys.marketplace.all` - All marketplace queries
- `queryKeys.marketplace.listings()` - All listings
- `queryKeys.marketplace.listing(id)` - Specific listing
- `queryKeys.marketplace.categories()` - Categories
- `queryKeys.marketplace.search(query)` - Marketplace search

#### Search
- `queryKeys.search.all` - All search queries
- `queryKeys.search.global(query, filters?)` - Global search
- `queryKeys.search.assets(query, filters?)` - Asset search
- `queryKeys.search.suggestions(query)` - Search suggestions

#### Analytics
- `queryKeys.analytics.all` - All analytics queries
- `queryKeys.analytics.dashboard()` - Dashboard data
- `queryKeys.analytics.metrics(timeRange)` - Metrics
- `queryKeys.analytics.reports()` - All reports
- `queryKeys.analytics.report(id)` - Specific report

#### Notifications
- `queryKeys.notifications.all` - All notification queries
- `queryKeys.notifications.list(filters?)` - Notification list
- `queryKeys.notifications.unread()` - Unread notifications
- `queryKeys.notifications.count()` - Notification count

## Helper Functions

### Invalidate Queries

Invalidate queries to trigger refetch:

```tsx
import { invalidateQueries, queryKeys } from '@/lib/api'

// Invalidate all asset queries
await invalidateQueries(queryKeys.assets.all)

// Invalidate specific asset list
await invalidateQueries(queryKeys.assets.list({ status: 'active' }))

// Invalidate after mutation
const mutation = useMutation({
  mutationFn: createAsset,
  onSuccess: () => {
    invalidateQueries(queryKeys.assets.lists())
  },
})
```

### Reset Queries

Reset queries to clear cache and refetch:

```tsx
import { resetQueries, queryKeys } from '@/lib/api'

// Reset all asset queries
await resetQueries(queryKeys.assets.all)
```

### Remove Queries

Remove queries from cache:

```tsx
import { removeQueries, queryKeys } from '@/lib/api'

// Remove specific query
await removeQueries(queryKeys.assets.detail('asset-123'))
```

### Prefetch Queries

Prefetch data for better UX:

```tsx
import { prefetchQuery, queryKeys } from '@/lib/api'

// Prefetch asset detail
await prefetchQuery({
  queryKey: queryKeys.assets.detail('asset-123'),
  queryFn: () => api.getAsset('asset-123'),
})
```

## Best Practices

### 1. Use Query Key Factories

Always use query key factories for consistency:

```tsx
// ✅ Good
queryKey: queryKeys.assets.detail(id)

// ❌ Bad
queryKey: ['assets', id]
```

### 2. Invalidate Related Queries

When mutating data, invalidate related queries:

```tsx
const mutation = useMutation({
  mutationFn: updateAsset,
  onSuccess: (data) => {
    // Invalidate list queries
    invalidateQueries(queryKeys.assets.lists())
    // Invalidate specific detail
    invalidateQueries(queryKeys.assets.detail(data.id))
  },
})
```

### 3. Use Appropriate Stale Times

Override stale time for frequently changing data:

```tsx
// Real-time data (stale immediately)
useQuery({
  queryKey: queryKeys.notifications.unread(),
  queryFn: fetchUnread,
  staleTime: 0,
  refetchInterval: 30000, // Refetch every 30 seconds
})

// Static data (stale after 1 hour)
useQuery({
  queryKey: queryKeys.workspaces.detail(id),
  queryFn: fetchWorkspace,
  staleTime: 60 * 60 * 1000, // 1 hour
})
```

### 4. Handle Errors Gracefully

```tsx
const { data, error, isError } = useQuery({
  queryKey: queryKeys.assets.list(),
  queryFn: fetchAssets,
  retry: (failureCount, error) => {
    // Don't retry on 404
    if (error?.response?.status === 404) {
      return false
    }
    return failureCount < 3
  },
})

if (isError) {
  return <ErrorState error={error} />
}
```

### 5. Use Optimistic Updates

```tsx
const mutation = useMutation({
  mutationFn: updateAsset,
  onMutate: async (newData) => {
    // Cancel outgoing refetches
    await queryClient.cancelQueries({
      queryKey: queryKeys.assets.detail(newData.id),
    })

    // Snapshot previous value
    const previous = queryClient.getQueryData(
      queryKeys.assets.detail(newData.id)
    )

    // Optimistically update
    queryClient.setQueryData(
      queryKeys.assets.detail(newData.id),
      newData
    )

    return { previous }
  },
  onError: (err, newData, context) => {
    // Rollback on error
    queryClient.setQueryData(
      queryKeys.assets.detail(newData.id),
      context?.previous
    )
  },
  onSettled: (data) => {
    // Refetch to ensure consistency
    queryClient.invalidateQueries({
      queryKey: queryKeys.assets.detail(data.id),
    })
  },
})
```

## Type Safety

All query keys are fully typed:

```tsx
import type { QueryKey } from '@/lib/api'

// Type-safe query key
const key: QueryKey['assets']['detail'] = queryKeys.assets.detail('123')
```

## DevTools

React Query DevTools are available in development mode:

- Open/close with the floating button (bottom-right)
- View all queries and their status
- Inspect cache contents
- Manually invalidate/refetch queries
- View query details and timings

## See Also

- [React Query Documentation](https://tanstack.com/query/latest)
- [API Client Documentation](./README.md)

