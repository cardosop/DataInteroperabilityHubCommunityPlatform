# Testing Utilities

This directory contains utilities and helpers for testing.

## Purpose

Shared testing utilities and setup for:
- Test renderers
- Mock factories
- Test helpers
- Custom matchers
- Test fixtures

## Structure

```
test-utils/
├── render.tsx         # Custom render function with providers
├── mocks/             # Mock factories
│   ├── api.ts
│   └── data.ts
├── helpers.ts         # Test helper functions
├── fixtures.ts        # Test data fixtures
└── index.ts           # Public exports
```

## Guidelines

- **Reusability**: Utilities should be reusable across tests
- **Type safety**: All utilities should be typed
- **Documentation**: Document complex utilities
- **Maintenance**: Keep utilities up to date with app changes

## Usage

```tsx
import { render, screen } from '@/test-utils'
import { mockUser } from '@/test-utils/mocks'

test('renders component', () => {
  render(<MyComponent user={mockUser} />)
  expect(screen.getByText('Hello')).toBeInTheDocument()
})
```

## Best Practices

1. **Custom render**: Create custom render with all providers
2. **Mock factories**: Use factories for consistent mocks
3. **Fixtures**: Use fixtures for test data
4. **Helpers**: Create helpers for common test patterns
5. **Cleanup**: Ensure proper cleanup in utilities

