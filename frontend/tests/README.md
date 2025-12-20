# Tests

This directory contains all test files organized by test type.

## Structure

```
tests/
├── unit/              # Unit tests
├── component/         # Component tests
└── e2e/               # End-to-end tests
```

## Test Organization

### Unit Tests (`tests/unit/`)
- Test individual functions and utilities
- Fast, isolated tests
- No DOM rendering
- Test pure logic

### Component Tests (`tests/component/`)
- Test React components
- Use React Testing Library
- Test user interactions
- Test component behavior

### E2E Tests (`tests/e2e/`)
- Test complete user flows
- Use Playwright
- Test across browsers
- Test real user scenarios

## Guidelines

- **Co-location**: Prefer co-located tests when possible
- **Organization**: Mirror source structure in tests
- **Naming**: Use descriptive test names
- **Coverage**: Aim for high coverage of critical paths
- **Performance**: Keep tests fast

## Running Tests

```bash
# Run all tests
npm test

# Run unit tests
npm run test:unit

# Run component tests
npm run test:component

# Run E2E tests
npm run test:e2e

# Run tests in watch mode
npm run test:watch
```

## Best Practices

1. **AAA Pattern**: Arrange, Act, Assert
2. **Isolation**: Tests should be independent
3. **Clarity**: Tests should be easy to understand
4. **Maintenance**: Keep tests maintainable
5. **CI/CD**: Run tests in CI/CD pipeline

