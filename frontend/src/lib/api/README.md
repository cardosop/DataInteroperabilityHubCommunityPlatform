# API Client Foundation

Comprehensive API client foundation with interceptors, retry logic, and error handling.

## Overview

The API client provides:
- **Axios Instance Configuration** - Centralized HTTP client setup
- **Request Interceptors** - Authentication, tenant ID, request ID
- **Response Interceptors** - Error handling, token refresh, rate limiting
- **Retry Logic** - Exponential backoff for failed requests
- **API Client Factory** - Create multiple client instances

## Structure

```
api/
├── axios.ts          # Axios instance factory with interceptors
├── client.ts         # API client factory and singleton
├── types.ts          # TypeScript type definitions
├── errors.ts         # Error handling utilities
└── utils/
    ├── requestId.ts  # Request ID generation
    └── retry.ts      # Retry logic utilities
```

## Usage

### Basic Usage

```typescript
import { apiClient } from '@/lib/api'

// GET request
const response = await apiClient.get('/users')

// POST request
const newUser = await apiClient.post('/users', { name: 'John' })

// PUT request
const updated = await apiClient.put('/users/1', { name: 'Jane' })

// DELETE request
await apiClient.delete('/users/1')
```

### Request Configuration

```typescript
import { apiClient, ApiClientConfig } from '@/lib/api'

// Skip authentication for public endpoints
await apiClient.get('/public/data', {
  skipAuth: true,
} as ApiClientConfig)

// Skip tenant ID
await apiClient.get('/global/data', {
  skipTenantId: true,
} as ApiClientConfig)

// Custom request ID
await apiClient.get('/data', {
  requestId: 'custom-request-id',
} as ApiClientConfig)

// Disable retry for this request
await apiClient.get('/data', {
  skipRetry: true,
} as ApiClientConfig)

// Custom retry configuration
await apiClient.get('/data', {
  retry: {
    maxRetries: 5,
    initialDelay: 2000,
    maxDelay: 20000,
  },
} as ApiClientConfig)
```

### Creating Custom Clients

```typescript
import { createApiClient, createPublicApiClient, createAuthenticatedApiClient } from '@/lib/api'

// Create a named client instance
const customClient = createApiClient('custom', {
  baseURL: 'https://api.example.com',
  timeout: 60000,
})

// Create a public client (no auth)
const publicClient = createPublicApiClient({
  baseURL: 'https://public-api.example.com',
})

// Create an authenticated client with specific token
const authClient = createAuthenticatedApiClient('token-here', {
  baseURL: 'https://api.example.com',
})
```

### Error Handling

```typescript
import { apiClient, parseApiError, ApiError, NetworkError } from '@/lib/api'

try {
  const response = await apiClient.get('/users')
} catch (error) {
  const apiError = parseApiError(error)

  if (apiError instanceof ApiError) {
    console.error('API Error:', {
      code: apiError.code,
      message: apiError.message,
      status: apiError.status,
      requestId: apiError.requestId,
      details: apiError.details,
    })
  } else if (apiError instanceof NetworkError) {
    console.error('Network Error:', apiError.message)
  }
}
```

### Token Refresh

```typescript
import { createApiClient } from '@/lib/api'

const client = createApiClient('default', {
  tokenRefresh: async () => {
    // Call your token refresh endpoint
    const response = await fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'include',
    })
    const data = await response.json()
    return data.token
  },
})
```

### Rate Limiting

```typescript
import { createApiClient } from '@/lib/api'

const client = createApiClient('default', {
  rateLimitHandler: (retryAfter) => {
    console.warn(`Rate limited. Retry after ${retryAfter} seconds`)
    // Show user notification, disable UI, etc.
  },
})
```

## Features

### Request Interceptors

1. **Authentication** - Automatically adds Bearer token from localStorage
2. **Tenant ID** - Automatically adds X-Tenant-ID header from user context
3. **Request ID** - Generates unique request ID for tracing
4. **Logging** - Logs requests in development mode

### Response Interceptors

1. **Error Handling** - Parses and formats API errors
2. **Token Refresh** - Automatically refreshes expired tokens
3. **Rate Limiting** - Handles 429 responses with Retry-After headers
4. **Logging** - Logs responses in development mode

### Retry Logic

- **Exponential Backoff** - Delays increase exponentially between retries
- **Configurable** - Customize retry attempts, delays, and status codes
- **Smart Retry** - Only retries on retryable errors (network, 5xx, etc.)
- **Rate Limit Aware** - Respects Retry-After headers

### Error Handling

- **Typed Errors** - ApiError and NetworkError classes
- **Error Parsing** - Extracts error details from API responses
- **Request Tracing** - Includes request ID in errors

## Configuration

The API client uses environment configuration from `@/lib/config`:

- `config.api.baseUrl` - Base URL for API requests
- `config.api.timeout` - Request timeout in milliseconds
- `config.development.enableApiLogging` - Enable request/response logging

## Best Practices

1. **Use the default client** - For most cases, use the exported `apiClient`
2. **Handle errors** - Always wrap API calls in try-catch
3. **Use typed errors** - Use `parseApiError` for consistent error handling
4. **Configure retries** - Adjust retry settings based on endpoint criticality
5. **Monitor rate limits** - Implement rate limit handlers for user feedback
6. **Request IDs** - Use request IDs for debugging and support

## Examples

### Complete Example with Error Handling

```typescript
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api'

async function fetchUsers() {
  try {
    const response = await apiClient.get('/users')
    return response.data
  } catch (error) {
    const apiError = parseApiError(error)
    const message = getErrorMessage(apiError)

    // Show user-friendly error message
    toast.error(message)

    // Log detailed error for debugging
    console.error('Failed to fetch users:', apiError)

    throw apiError
  }
}
```

### Example with Retry Configuration

```typescript
import { apiClient } from '@/lib/api'

// Critical endpoint with aggressive retry
const criticalData = await apiClient.get('/critical-data', {
  retry: {
    maxRetries: 5,
    initialDelay: 500,
    maxDelay: 5000,
  },
} as ApiClientConfig)

// Non-critical endpoint with no retry
const optionalData = await apiClient.get('/optional-data', {
  skipRetry: true,
} as ApiClientConfig)
```
