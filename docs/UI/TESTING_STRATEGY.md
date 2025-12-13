# Frontend Testing Strategy

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

---

## Table of Contents

1. [Overview](#overview)
2. [Testing Pyramid](#testing-pyramid)
3. [Unit Testing](#unit-testing)
4. [Component Testing](#component-testing)
5. [Integration Testing](#integration-testing)
6. [End-to-End Testing](#end-to-end-testing)
7. [Visual Regression Testing](#visual-regression-testing)
8. [Accessibility Testing](#accessibility-testing)
9. [Performance Testing](#performance-testing)
10. [Test Data Management](#test-data-management)
11. [Mocking Strategies](#mocking-strategies)
12. [CI/CD Integration](#cicd-integration)

---

## Overview

This document outlines the comprehensive testing strategy for the frontend application. The strategy follows the testing pyramid approach, emphasizing unit and component tests with fewer integration and E2E tests.

**Testing Principles**:
- **Test User Behavior**: Test what users see and do, not implementation details
- **Fast Feedback**: Tests should run quickly
- **Reliable**: Tests should be deterministic and not flaky
- **Maintainable**: Tests should be easy to update
- **Comprehensive**: Cover critical paths and edge cases

**Testing Tools**:
- **Unit/Component**: Jest, React Testing Library
- **E2E**: Cypress or Playwright
- **Visual**: Chromatic or Percy
- **Accessibility**: jest-axe, pa11y
- **Coverage**: Istanbul/nyc

---

## Testing Pyramid

```
        /\
       /  \
      / E2E \          (10%)
     /--------\
    /          \
   / Integration \     (20%)
  /--------------\
 /                \
/   Unit/Component  \  (70%)
/--------------------\
```

**Distribution**:
- **70%**: Unit and Component Tests (fast, isolated)
- **20%**: Integration Tests (moderate speed, test interactions)
- **10%**: E2E Tests (slower, test complete flows)

---

## Unit Testing

### Testing Utilities

**Setup**: `src/test-utils/index.ts`

```typescript
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@mui/material/styles';
import { theme } from '@/theme';

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        cacheTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions
) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          {children}
        </ThemeProvider>
      </QueryClientProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}

export * from '@testing-library/react';
export { renderWithProviders as render };
```

### Example Unit Test

**File**: `src/components/Button.test.tsx`

```typescript
import { render, screen } from '@/test-utils';
import { Button } from './Button';

describe('Button', () => {
  it('renders with text', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    
    screen.getByRole('button').click();
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('is disabled when disabled prop is true', () => {
    render(<Button disabled>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('applies variant styles correctly', () => {
    const { container } = render(<Button variant="contained">Click me</Button>);
    expect(container.firstChild).toHaveClass('MuiButton-contained');
  });
});
```

### Testing Hooks

**File**: `src/hooks/useAssets.test.ts`

```typescript
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClientProvider } from '@tanstack/react-query';
import { useAssets } from './useAssets';
import { createTestQueryClient } from '@/test-utils';
import { server } from '@/test-utils/msw';
import { rest } from 'msw';

describe('useAssets', () => {
  it('fetches assets successfully', async () => {
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        return res(
          ctx.json({
            count: 2,
            results: [
              { id: '1', name: 'Asset 1' },
              { id: '2', name: 'Asset 2' },
            ],
          })
        );
      })
    );

    const queryClient = createTestQueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );

    const { result } = renderHook(() => useAssets(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.results).toHaveLength(2);
  });
});
```

---

## Component Testing

### Component Test Example

**File**: `src/components/AssetCard.test.tsx`

```typescript
import { render, screen, userEvent } from '@/test-utils';
import { AssetCard } from './AssetCard';
import type { Asset } from '@/types';

const mockAsset: Asset = {
  id: '1',
  name: 'Test Asset',
  key: 'test-asset',
  status: 'ACTIVE',
  description: 'Test description',
};

describe('AssetCard', () => {
  it('renders asset information', () => {
    render(<AssetCard asset={mockAsset} />);
    
    expect(screen.getByText('Test Asset')).toBeInTheDocument();
    expect(screen.getByText('test-asset')).toBeInTheDocument();
    expect(screen.getByText('Test description')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(<AssetCard asset={mockAsset} />);
    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', async () => {
    const onEdit = jest.fn();
    render(<AssetCard asset={mockAsset} onEdit={onEdit} />);
    
    const editButton = screen.getByRole('button', { name: /edit/i });
    await userEvent.click(editButton);
    
    expect(onEdit).toHaveBeenCalledWith(mockAsset.id);
  });

  it('handles loading state', () => {
    render(<AssetCard asset={mockAsset} loading />);
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });
});
```

### Testing Forms

**File**: `src/components/AssetForm.test.tsx`

```typescript
import { render, screen, waitFor } from '@/test-utils';
import userEvent from '@testing-library/user-event';
import { AssetForm } from './AssetForm';

describe('AssetForm', () => {
  it('validates required fields', async () => {
    const onSubmit = jest.fn();
    render(<AssetForm onSubmit={onSubmit} />);

    const submitButton = screen.getByRole('button', { name: /create/i });
    await userEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits form with valid data', async () => {
    const onSubmit = jest.fn();
    render(<AssetForm onSubmit={onSubmit} />);

    await userEvent.type(screen.getByLabelText(/name/i), 'Test Asset');
    await userEvent.type(screen.getByLabelText(/key/i), 'test-asset');
    await userEvent.click(screen.getByRole('button', { name: /create/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        name: 'Test Asset',
        key: 'test-asset',
      });
    });
  });
});
```

---

## Integration Testing

### Integration Test Example

**File**: `src/features/assets/AssetList.test.tsx`

```typescript
import { render, screen, waitFor } from '@/test-utils';
import { AssetList } from './AssetList';
import { server } from '@/test-utils/msw';
import { rest } from 'msw';

describe('AssetList Integration', () => {
  it('loads and displays assets', async () => {
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        return res(
          ctx.json({
            count: 2,
            results: [
              { id: '1', name: 'Asset 1', status: 'ACTIVE' },
              { id: '2', name: 'Asset 2', status: 'DRAFT' },
            ],
          })
        );
      })
    );

    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText('Asset 1')).toBeInTheDocument();
      expect(screen.getByText('Asset 2')).toBeInTheDocument();
    });
  });

  it('handles pagination', async () => {
    const user = userEvent.setup();
    
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        const page = req.url.searchParams.get('page') || '1';
        return res(
          ctx.json({
            count: 50,
            page: parseInt(page),
            total_pages: 3,
            results: Array.from({ length: 20 }, (_, i) => ({
              id: `${page}-${i}`,
              name: `Asset ${page}-${i}`,
            })),
          })
        );
      })
    );

    render(<AssetList />);

    await waitFor(() => {
      expect(screen.getByText('Asset 1-0')).toBeInTheDocument();
    });

    const nextButton = screen.getByRole('button', { name: /next/i });
    await user.click(nextButton);

    await waitFor(() => {
      expect(screen.getByText('Asset 2-0')).toBeInTheDocument();
    });
  });

  it('handles search', async () => {
    const user = userEvent.setup();
    
    server.use(
      rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
        const search = req.url.searchParams.get('search') || '';
        return res(
          ctx.json({
            count: 1,
            results: search
              ? [{ id: '1', name: 'Matching Asset' }]
              : [{ id: '1', name: 'Asset 1' }],
          })
        );
      })
    );

    render(<AssetList />);

    const searchInput = screen.getByPlaceholderText(/search/i);
    await user.type(searchInput, 'Matching');

    await waitFor(() => {
      expect(screen.getByText('Matching Asset')).toBeInTheDocument();
    });
  });
});
```

---

## End-to-End Testing

### Cypress Setup

**File**: `cypress.config.ts`

```typescript
import { defineConfig } from 'cypress';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:3000',
    viewportWidth: 1280,
    viewportHeight: 720,
    video: true,
    screenshotOnRunFailure: true,
    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
  component: {
    devServer: {
      framework: 'react',
      bundler: 'vite',
    },
  },
});
```

### E2E Test Example

**File**: `cypress/e2e/asset-creation.cy.ts`

```typescript
describe('Asset Creation Flow', () => {
  beforeEach(() => {
    // Login
    cy.login('user@example.com', 'password');
    cy.visit('/assets');
  });

  it('creates a new asset via data-first flow', () => {
    // Click create asset button
    cy.findByRole('button', { name: /create asset/i }).click();

    // Fill in basic metadata
    cy.findByLabelText(/asset name/i).type('Customer Orders');
    cy.findByLabelText(/description/i).type('Customer order data');
    cy.findByLabelText(/domain/i).select('Sales');

    // Select data-first onboarding mode
    cy.findByLabelText(/data first/i).check();

    // Continue to file upload
    cy.findByRole('button', { name: /continue/i }).click();

    // Upload file
    cy.findByLabelText(/upload file/i).attachFile('sample.csv');

    // Wait for file processing
    cy.findByText(/file uploaded successfully/i).should('be.visible');

    // Continue to contract editor
    cy.findByRole('button', { name: /continue/i }).click();

    // Verify contract editor is shown
    cy.findByText(/edit contract/i).should('be.visible');

    // Save and activate
    cy.findByRole('button', { name: /save/i }).click();
    cy.findByRole('button', { name: /activate/i }).click();

    // Verify success
    cy.findByText(/asset created successfully/i).should('be.visible');
    cy.url().should('include', '/assets/');
  });
});
```

### Custom Cypress Commands

**File**: `cypress/support/commands.ts`

```typescript
declare global {
  namespace Cypress {
    interface Chainable {
      login(email: string, password: string): Chainable<void>;
      createAsset(data: Partial<Asset>): Chainable<string>;
      waitForJob(jobId: string): Chainable<void>;
    }
  }
}

Cypress.Commands.add('login', (email: string, password: string) => {
  cy.request({
    method: 'POST',
    url: '/api/v1/auth/login/',
    body: { email, password },
  }).then((response) => {
    window.localStorage.setItem('auth_token', response.body.access);
    window.localStorage.setItem('tenant_id', response.body.user.tenant_id);
  });
});

Cypress.Commands.add('createAsset', (data: Partial<Asset>) => {
  return cy.request({
    method: 'POST',
    url: '/api/v1/assets/assets/',
    headers: {
      Authorization: `Bearer ${window.localStorage.getItem('auth_token')}`,
    },
    body: data,
  }).then((response) => {
    return response.body.id;
  });
});

Cypress.Commands.add('waitForJob', (jobId: string) => {
  cy.request({
    method: 'GET',
    url: `/api/v1/jobs/${jobId}/`,
    headers: {
      Authorization: `Bearer ${window.localStorage.getItem('auth_token')}`,
    },
  }).then((response) => {
    if (response.body.status === 'running') {
      cy.wait(2000);
      cy.waitForJob(jobId);
    }
  });
});
```

---

## Visual Regression Testing

### Chromatic Setup

**File**: `package.json`

```json
{
  "scripts": {
    "chromatic": "chromatic --project-token=YOUR_TOKEN"
  }
}
```

### Storybook Stories for Visual Testing

**File**: `src/components/Button.stories.tsx`

```typescript
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'Components/Button',
  component: Button,
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
  args: {
    children: 'Button',
    variant: 'contained',
  },
};

export const Secondary: Story = {
  args: {
    children: 'Button',
    variant: 'outlined',
  },
};

export const Disabled: Story = {
  args: {
    children: 'Button',
    disabled: true,
  },
};
```

---

## Accessibility Testing

### jest-axe Setup

**File**: `src/test-utils/accessibility.ts`

```typescript
import { toHaveNoViolations } from 'jest-axe';
import { axe } from 'jest-axe';

expect.extend(toHaveNoViolations);

export async function checkAccessibility(container: HTMLElement) {
  const results = await axe(container);
  expect(results).toHaveNoViolations();
}
```

### Accessibility Test Example

**File**: `src/components/AssetCard.a11y.test.tsx`

```typescript
import { render } from '@/test-utils';
import { checkAccessibility } from '@/test-utils/accessibility';
import { AssetCard } from './AssetCard';

describe('AssetCard Accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = render(
      <AssetCard
        asset={{
          id: '1',
          name: 'Test Asset',
          key: 'test-asset',
          status: 'ACTIVE',
        }}
      />
    );

    await checkAccessibility(container);
  });

  it('is keyboard navigable', async () => {
    const { container } = render(<AssetCard asset={mockAsset} />);
    
    // Tab to card
    const card = container.querySelector('[role="article"]');
    card?.focus();
    expect(card).toHaveFocus();

    // Tab to action buttons
    const buttons = container.querySelectorAll('button');
    buttons.forEach((button) => {
      expect(button).toBeVisible();
    });
  });
});
```

---

## Performance Testing

### Performance Test Example

**File**: `src/components/AssetList.perf.test.tsx`

```typescript
import { render, screen } from '@/test-utils';
import { AssetList } from './AssetList';

describe('AssetList Performance', () => {
  it('renders large lists efficiently', () => {
    const start = performance.now();
    
    render(<AssetList />);
    
    const end = performance.now();
    const renderTime = end - start;

    // Should render in under 100ms
    expect(renderTime).toBeLessThan(100);
  });

  it('handles virtual scrolling for large datasets', () => {
    const { container } = render(<AssetList />);
    
    // Check that only visible items are rendered
    const renderedItems = container.querySelectorAll('[data-testid="asset-item"]');
    expect(renderedItems.length).toBeLessThan(50); // Only visible items
  });
});
```

---

## Test Data Management

### Mock Service Worker (MSW) Setup

**File**: `src/test-utils/msw.ts`

```typescript
import { setupServer } from 'msw/node';
import { rest } from 'msw';

export const server = setupServer(
  // Default handlers
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(
      ctx.json({
        count: 0,
        results: [],
      })
    );
  }),
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

### Test Data Factories

**File**: `src/test-utils/factories.ts`

```typescript
import { faker } from '@faker-js/faker';
import type { Asset, Contract } from '@/types';

export function createMockAsset(overrides?: Partial<Asset>): Asset {
  return {
    id: faker.string.uuid(),
    name: faker.company.name(),
    key: faker.string.alphanumeric(10),
    status: 'ACTIVE',
    description: faker.lorem.sentence(),
    created_at: faker.date.past().toISOString(),
    ...overrides,
  };
}

export function createMockContract(overrides?: Partial<Contract>): Contract {
  return {
    id: faker.string.uuid(),
    version: '1.0.0',
    status: 'VALID',
    ...overrides,
  };
}
```

---

## Mocking Strategies

### API Mocking

**Strategy**: Use MSW for API mocking in tests

```typescript
// Mock successful response
server.use(
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(ctx.json({ count: 1, results: [createMockAsset()] }));
  })
);

// Mock error response
server.use(
  rest.get('/api/v1/assets/assets/', (req, res, ctx) => {
    return res(ctx.status(500), ctx.json({ error: 'Server error' }));
  })
);
```

### Component Mocking

**Strategy**: Mock external dependencies, not components under test

```typescript
// Mock external library
jest.mock('@/lib/api/websocket', () => ({
  wsClient: {
    connect: jest.fn(),
    subscribe: jest.fn(),
    on: jest.fn(),
  },
}));
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/frontend-tests.yml`

```yaml
name: Frontend Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      
      - name: Install dependencies
        run: npm ci
      
      - name: Run unit tests
        run: npm run test:unit
      
      - name: Run component tests
        run: npm run test:component
      
      - name: Run E2E tests
        run: npm run test:e2e
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/lcov.info
```

### Test Scripts

**File**: `package.json`

```json
{
  "scripts": {
    "test": "jest",
    "test:unit": "jest --testPathPattern=test",
    "test:component": "jest --testPathPattern=component",
    "test:e2e": "cypress run",
    "test:e2e:open": "cypress open",
    "test:coverage": "jest --coverage",
    "test:watch": "jest --watch",
    "test:a11y": "jest --testPathPattern=a11y"
  }
}
```

---

## Coverage Goals

**Target Coverage**:
- **Overall**: 80%+
- **Components**: 85%+
- **Hooks**: 90%+
- **Utils**: 95%+
- **Critical Paths**: 100%

**Coverage Exclusions**:
- Test files
- Storybook files
- Type definitions
- Generated code

---

## Best Practices

1. **Test Behavior, Not Implementation**: Test what users see and do
2. **Use Semantic Queries**: Prefer `getByRole`, `getByLabelText` over `getByTestId`
3. **Avoid Testing Implementation Details**: Don't test internal state or methods
4. **Keep Tests Simple**: One assertion per test when possible
5. **Use Descriptive Names**: Test names should describe what they test
6. **Mock External Dependencies**: Mock APIs, WebSockets, etc.
7. **Test Edge Cases**: Test error states, empty states, loading states
8. **Maintain Test Data**: Use factories for consistent test data
9. **Clean Up**: Reset mocks and state between tests
10. **Fast Tests**: Keep unit tests under 100ms

---

**Last Updated**: 2025-12-13  
**Version**: 1.0.0

