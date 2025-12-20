# MSW (Mock Service Worker) Setup

This directory contains the Mock Service Worker (MSW) setup for API mocking in both development and tests.

## Overview

MSW provides API mocking capabilities that work in both browser and Node.js environments. This allows you to:

- Mock API responses during development
- Mock API responses in tests
- Test error scenarios easily
- Develop frontend without backend dependency

## Structure

```
msw/
├── handlers.ts      # API endpoint handlers
├── server.ts        # Node.js server setup (for tests)
├── browser.ts       # Browser worker setup (for development)
├── utils.ts         # Helper utilities
├── index.ts         # Exports
└── __tests__/       # Tests
```

## Usage

### In Tests

MSW is automatically set up in the test environment. The server is started before all tests and reset between tests.

```tsx
import { describe, it, expect } from 'vitest'
import { server } from '@/test-utils/msw'
import { http, HttpResponse } from 'msw'
import { config } from '@/lib/config'

describe('MyComponent', () => {
  it('should fetch data', async () => {
    // Use default handlers
    const response = await fetch(`${config.api.baseUrl}/assets/`)
    const data = await response.json()

    expect(data.results).toBeDefined()
  })

  it('should handle errors', async () => {
    // Override handler for this test
    server.use(
      http.get(`${config.api.baseUrl}/assets/`, () => {
        return HttpResponse.json(
          { error: { message: 'Not found', code: 'NOT_FOUND' } },
          { status: 404 }
        )
      })
    )

    const response = await fetch(`${config.api.baseUrl}/assets/`)
    expect(response.status).toBe(404)
  })
})
```

### In Development

To enable MSW in development mode:

1. Set environment variable: `VITE_MSW_ENABLED=true`
2. MSW will automatically start when the app loads

The service worker file (`mockServiceWorker.js`) is already initialized in `public/`.

### Custom Handlers

You can create custom handlers for specific tests:

```tsx
import { useCustomHandlers } from '@/test-utils/msw/utils'
import { http, HttpResponse } from 'msw'
import { config } from '@/lib/config'

it('should use custom handler', () => {
  const restore = useCustomHandlers([
    http.get(`${config.api.baseUrl}/assets/`, () => {
      return HttpResponse.json({ results: [] })
    })
  ])

  // ... test code ...

  restore() // Restore default handlers
})
```

## Available Handlers

### Authentication
- `POST /api/v1/auth/login/` - Login
- `POST /api/v1/auth/logout/` - Logout
- `POST /api/v1/auth/refresh/` - Refresh token
- `GET /api/v1/auth/me/` - Get current user

### Assets
- `GET /api/v1/assets/` - List assets (with pagination, search, filtering)
- `GET /api/v1/assets/:id/` - Get asset by ID
- `POST /api/v1/assets/` - Create asset
- `PUT /api/v1/assets/:id/` - Update asset
- `DELETE /api/v1/assets/:id/` - Delete asset

### Contracts
- `GET /api/v1/contracts/` - List contracts (with pagination, search)
- `GET /api/v1/contracts/:id/` - Get contract by ID
- `POST /api/v1/contracts/` - Create contract
- `PUT /api/v1/contracts/:id/` - Update contract
- `DELETE /api/v1/contracts/:id/` - Delete contract
- `POST /api/v1/contracts/:id/validate/` - Validate contract

### Jobs
- `GET /api/v1/jobs/` - List jobs (with pagination)
- `GET /api/v1/jobs/:id/` - Get job by ID
- `POST /api/v1/jobs/` - Create job
- `POST /api/v1/jobs/:id/cancel/` - Cancel job

### Datasets
- `GET /api/v1/datasets/` - List datasets (with pagination)
- `GET /api/v1/datasets/:id/` - Get dataset by ID
- `POST /api/v1/datasets/` - Create dataset
- `PUT /api/v1/datasets/:id/` - Update dataset
- `DELETE /api/v1/datasets/:id/` - Delete dataset

### API Info
- `GET /api/v1/` - Get API information

## Utilities

### `resetMockData()`

Reset all mock data to initial state:

```tsx
import { resetMockData } from '@/test-utils/msw'

beforeEach(() => {
  resetMockData()
})
```

### `getMockData()`

Get current mock data:

```tsx
import { getMockData } from '@/test-utils/msw'

const mockData = getMockData()
console.log(mockData.assets) // Array of mock assets
```

### `useCustomHandlers()`

Use custom handlers for a test:

```tsx
import { useCustomHandlers } from '@/test-utils/msw/utils'

const restore = useCustomHandlers([...])
// ... test code ...
restore()
```

### `createErrorHandler()`

Create an error handler:

```tsx
import { createErrorHandler } from '@/test-utils/msw/utils'

server.use(createErrorHandler(500, 'Internal server error', 'SERVER_ERROR'))
```

## Best Practices

1. **Use default handlers**: Default handlers provide realistic mock data
2. **Override for specific tests**: Override handlers only when needed for specific test scenarios
3. **Reset between tests**: Handlers are automatically reset, but you can also reset mock data
4. **Test error scenarios**: Use custom handlers to test error cases
5. **Keep handlers simple**: Handlers should return realistic but simple responses

## Environment Variables

- `VITE_MSW_ENABLED`: Set to `true` to enable MSW in development mode (default: disabled)

## Troubleshooting

### MSW not working in development

1. Make sure `VITE_MSW_ENABLED=true` is set
2. Check browser console for MSW messages
3. Verify `public/mockServiceWorker.js` exists
4. Clear browser cache and reload

### MSW not working in tests

1. Check that `setupMSW()` is called in `setup.ts`
2. Verify handlers are imported correctly
3. Check test output for MSW warnings

### Service worker not registering

1. Make sure you're running the app over HTTP (not file://)
2. Check browser console for service worker errors
3. Try clearing browser cache

## References

- [MSW Documentation](https://mswjs.io/)
- [MSW GitHub](https://github.com/mswjs/msw)

