# Testing Guide

**Last Updated**: 2025-01-27
**Version**: 1.0.0

---

## Overview

This document describes the testing infrastructure, best practices, and guidelines for writing tests in the Data Interoperability Hub frontend application.

The project uses **Vitest** (not Jest) as the testing framework because:
- Seamless integration with Vite
- Faster test execution
- Jest-compatible API
- Native ESM support
- Shared configuration with Vite

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Configuration](#test-configuration)
3. [Writing Tests](#writing-tests)
4. [Test Utilities](#test-utilities)
5. [Coverage](#coverage)
6. [Best Practices](#best-practices)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Running Tests

```bash
# Run all tests in watch mode
npm test

# Run all tests once
npm run test:run

# Run tests with UI
npm run test:ui

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test src/components/Button/Button.test.tsx

# Run tests matching a pattern
npm test -- --grep "Button"
```

### Test Scripts

| Script | Description |
|--------|-------------|
| `npm test` | Run tests in watch mode |
| `npm run test:run` | Run all tests once |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:ui` | Run tests with UI |
| `npm run test:coverage` | Run tests with coverage report |
| `npm run test:coverage:watch` | Run tests with coverage in watch mode |
| `npm run test:unit` | Run unit tests only |
| `npm run test:component` | Run component tests only |

---

## Test Configuration

### Vitest Configuration

The Vitest configuration is in `vitest.config.ts` and includes:

- **Environment**: jsdom (for DOM testing)
- **Setup File**: `src/test-utils/setup.ts`
- **Coverage Provider**: v8
- **Coverage Thresholds**: Enforced minimum coverage levels
- **Test Timeout**: 10 seconds
- **Globals**: Enabled (describe, it, expect available globally)

### Test Environment

Tests run in a jsdom environment, which provides:
- DOM APIs (document, window, etc.)
- Browser-like environment
- Fast execution
- No real browser required

### Setup File

The setup file (`src/test-utils/setup.ts`) automatically:
- Imports jest-dom matchers
- Cleans up DOM after each test
- Mocks browser APIs (matchMedia, IntersectionObserver, etc.)
- Mocks WebSocket and fetch APIs
- Configures global test utilities

---

## Writing Tests

### Basic Test Structure

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@/test-utils'
import { Button } from './Button'

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByText('Click me')).toBeInTheDocument()
  })
})
```

### Component Testing

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen, userEvent } from '@/test-utils'
import { Button } from './Button'

describe('Button', () => {
  it('calls onClick when clicked', async () => {
    const handleClick = vi.fn()
    const user = userEvent.setup()

    render(<Button onClick={handleClick}>Click me</Button>)

    await user.click(screen.getByRole('button'))

    expect(handleClick).toHaveBeenCalledTimes(1)
  })
})
```

### Testing with Providers

The custom `render` function automatically includes:
- React Query (QueryClientProvider)
- React Router (MemoryRouter)
- Material-UI (ThemeProvider)
- i18next (I18nextProvider)

```tsx
import { render } from '@/test-utils'

// Automatically wrapped with all providers
render(<MyComponent />)
```

### Custom Provider Options

```tsx
import { render, createTestQueryClient } from '@/test-utils'

// With custom options
render(<MyComponent />, {
  queryClient: createTestQueryClient(),
  router: 'browser', // or 'memory'
  initialEntries: ['/custom-route'],
  themeMode: 'dark',
})
```

### Testing Hooks

```tsx
import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useLocalStorage } from '@/hooks/useLocalStorage'

describe('useLocalStorage', () => {
  it('stores and retrieves values', () => {
    const { result } = renderHook(() => useLocalStorage('key', 'default'))

    expect(result.current[0]).toBe('default')

    result.current[1]('new value')

    expect(result.current[0]).toBe('new value')
  })
})
```

### Async Testing

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@/test-utils'
import { DataFetcher } from './DataFetcher'

describe('DataFetcher', () => {
  it('loads and displays data', async () => {
    const mockData = { id: 1, name: 'Test' }
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockData,
    })

    render(<DataFetcher />)

    await waitFor(() => {
      expect(screen.getByText('Test')).toBeInTheDocument()
    })
  })
})
```

---

## Test Utilities

### Custom Render Function

Located in `src/test-utils/index.tsx`, provides:

- **Automatic Provider Wrapping**: All necessary providers included
- **Custom Options**: Configure query client, router, theme
- **Type Safety**: Full TypeScript support

### Helper Functions

```tsx
import {
  render,
  screen,
  wait,
  waitForElementToBeRemoved,
  createTestQueryClient,
} from '@/test-utils'

// Wait for async operations
await wait(1000)

// Wait for element removal
await waitForElementToBeRemoved(element)

// Create test query client
const queryClient = createTestQueryClient({ retry: false })
```

### User Event

```tsx
import { userEvent } from '@/test-utils'

const user = userEvent.setup()

await user.click(button)
await user.type(input, 'text')
await user.keyboard('{Enter}')
```

---

## Coverage

### Coverage Configuration

Coverage is configured in `vitest.config.ts` with:

- **Provider**: v8 (fast and accurate)
- **Reporters**: text, json, html, lcov
- **Thresholds**: Enforced minimum coverage
- **Exclusions**: Test files, stories, types excluded

### Coverage Thresholds

| Metric | Threshold |
|--------|-----------|
| Lines | 70% |
| Functions | 70% |
| Branches | 65% |
| Statements | 70% |

### Running Coverage

```bash
# Generate coverage report
npm run test:coverage

# Coverage report location
# - HTML: coverage/index.html
# - JSON: coverage/coverage-final.json
# - LCOV: coverage/lcov.info
```

### Viewing Coverage

Open `coverage/index.html` in a browser to view:
- File-by-file coverage
- Line-by-line highlighting
- Coverage trends
- Uncovered code

---

## Best Practices

### 1. Test Structure

Follow the AAA pattern:
- **Arrange**: Set up test data and conditions
- **Act**: Execute the code being tested
- **Assert**: Verify the expected outcome

```tsx
it('should calculate total correctly', () => {
  // Arrange
  const items = [10, 20, 30]

  // Act
  const total = calculateTotal(items)

  // Assert
  expect(total).toBe(60)
})
```

### 2. Test Naming

Use descriptive test names:
- ✅ `it('should display error message when API call fails')`
- ❌ `it('test error')`

### 3. Test Isolation

Each test should be independent:
- Don't rely on test execution order
- Clean up after each test
- Use `beforeEach` and `afterEach` for setup/teardown

### 4. Mocking

Mock external dependencies:
- API calls (fetch, axios)
- Browser APIs (localStorage, WebSocket)
- Third-party libraries
- Complex utilities

```tsx
// Mock API call
vi.mock('@/lib/api/client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: mockData }),
  },
}))
```

### 5. Testing User Interactions

Test what users see and do:
- ✅ Test user interactions (clicks, typing)
- ✅ Test accessibility (roles, labels)
- ❌ Don't test implementation details

### 6. Coverage Goals

- Aim for high coverage of critical paths
- Don't obsess over 100% coverage
- Focus on testing user-facing behavior
- Test edge cases and error conditions

### 7. Performance

- Keep tests fast (< 100ms per test)
- Use `vi.fn()` for simple mocks
- Avoid unnecessary async operations
- Use `waitFor` only when necessary

---

## Troubleshooting

### Tests Not Running

1. **Check Vitest is installed**:
   ```bash
   npm list vitest
   ```

2. **Check configuration**:
   ```bash
   npm test -- --config vitest.config.ts
   ```

3. **Clear cache**:
   ```bash
   rm -rf node_modules/.vite
   ```

### Coverage Not Working

1. **Check coverage provider**:
   ```bash
   npm list @vitest/coverage-v8
   ```

2. **Verify coverage config** in `vitest.config.ts`

3. **Check file exclusions** match your patterns

### jsdom Issues

If you encounter jsdom-related errors:

1. **Check jsdom is installed**:
   ```bash
   npm list jsdom
   ```

2. **Verify environment** in `vitest.config.ts`:
   ```ts
   test: {
     environment: 'jsdom',
   }
   ```

3. **Check setup file** includes necessary mocks

### Type Errors

If you get TypeScript errors:

1. **Check types are installed**:
   ```bash
   npm list @types/react @types/react-dom
   ```

2. **Verify tsconfig** includes test files

3. **Check vitest types**:
   ```ts
   /// <reference types="vitest" />
   ```

---

## Resources

### Documentation

- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/react)
- [Testing Library User Event](https://testing-library.com/docs/user-event/)
- [Jest DOM Matchers](https://github.com/testing-library/jest-dom)

### Examples

See existing tests in:
- `src/components/**/__tests__/`
- `src/hooks/__tests__/`
- `src/utils/__tests__/`
- `src/pages/**/__tests__/`

---

## Summary

- ✅ Use Vitest (not Jest) for Vite projects
- ✅ Use custom `render` from `@/test-utils`
- ✅ Test user-facing behavior, not implementation
- ✅ Keep tests fast and isolated
- ✅ Aim for good coverage, not 100%
- ✅ Follow AAA pattern (Arrange, Act, Assert)
- ✅ Use descriptive test names
- ✅ Mock external dependencies

For questions or issues, refer to the troubleshooting section or consult the development team.

