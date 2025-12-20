# Playwright E2E Testing

Comprehensive end-to-end testing setup for the Data Interoperability Hub frontend using Playwright.

## Overview

Playwright provides:
- **Cross-browser testing**: Chromium, Firefox, WebKit
- **Mobile testing**: Android Chrome, iOS Safari
- **Auto-waiting**: Automatic waiting for elements
- **Network interception**: Mock API responses
- **Visual testing**: Screenshot comparison
- **CI/CD integration**: GitHub Actions ready

## Installation

Playwright is already installed. To install browser binaries:

```bash
# Install all browsers
npm run test:e2e:install

# Install specific browser
npx playwright install chromium
npx playwright install firefox
npx playwright install webkit

# Install system dependencies (Linux)
npx playwright install-deps
```

## Configuration

### Main Configuration

The main configuration is in `playwright.config.ts` at the project root. Key features:

- **Browsers**: Chromium, Firefox, WebKit
- **Mobile**: Pixel 5 (Android), iPhone 12 (iOS), iPad Pro
- **Timeouts**: Configurable per test type
- **Retries**: Automatic retry on failure (2x in CI)
- **Reporting**: HTML, JUnit, GitHub Actions
- **Auto-server**: Automatically starts dev server

### Environment Variables

```bash
# Base URL for tests (default: http://localhost:3000)
PLAYWRIGHT_BASE_URL=http://localhost:3000

# Test environment (development, staging, production)
TEST_ENV=development

# CI mode (auto-detected from CI env var)
CI=true
```

## Usage

### Running Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run in UI mode (interactive)
npm run test:e2e:ui

# Run in debug mode (step through)
npm run test:e2e:debug

# Run in headed mode (see browser)
npm run test:e2e:headed

# Run specific browser
npm run test:e2e:chromium
npm run test:e2e:firefox
npm run test:e2e:webkit

# Run mobile tests
npm run test:e2e:mobile

# Run specific test file
npx playwright test auth.spec.ts

# Run tests matching pattern
npx playwright test --grep "login"
```

### Test Code Generation

Generate test code by recording interactions:

```bash
npm run test:e2e:codegen
```

This opens Playwright Inspector where you can:
1. Navigate to your app
2. Perform actions
3. Copy generated test code

### Viewing Reports

```bash
# View HTML report
npm run test:e2e:report

# Reports are saved to: playwright/reports/html/
```

## Test Structure

```
playwright/
├── config/              # Configuration files
│   └── fixtures.ts      # Test fixtures and utilities
├── tests/               # E2E test files
│   ├── auth.spec.ts     # Authentication tests
│   ├── navigation.spec.ts
│   └── ...
├── pages/               # Page Object Models
│   ├── LoginPage.ts
│   └── ...
├── utils/               # Test utilities
│   └── helpers.ts
├── global-setup.ts      # Global setup (runs once)
└── global-teardown.ts   # Global teardown (runs once)
```

## Writing Tests

### Basic Test Example

```typescript
import { test, expect } from '@playwright/test'

test('user can login', async ({ page }) => {
  await page.goto('/login')
  await page.fill('[name="email"]', 'user@example.com')
  await page.fill('[name="password"]', 'password123')
  await page.click('button[type="submit"]')

  await expect(page).toHaveURL('/dashboard')
  await expect(page.locator('text=Welcome')).toBeVisible()
})
```

### Page Object Model

```typescript
// playwright/pages/LoginPage.ts
import { Page, Locator } from '@playwright/test'

export class LoginPage {
  readonly page: Page
  readonly emailInput: Locator
  readonly passwordInput: Locator
  readonly submitButton: Locator

  constructor(page: Page) {
    this.page = page
    this.emailInput = page.locator('[name="email"]')
    this.passwordInput = page.locator('[name="password"]')
    this.submitButton = page.locator('button[type="submit"]')
  }

  async goto() {
    await this.page.goto('/login')
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email)
    await this.passwordInput.fill(password)
    await this.submitButton.click()
  }
}

// Usage in test
test('user can login', async ({ page }) => {
  const loginPage = new LoginPage(page)
  await loginPage.goto()
  await loginPage.login('user@example.com', 'password123')
  await expect(page).toHaveURL('/dashboard')
})
```

### Authentication

For authenticated tests, use storage state:

```typescript
// playwright/global-setup.ts
import { chromium, FullConfig } from '@playwright/test'

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch()
  const context = await browser.newContext()
  const page = await context.newPage()

  // Login
  await page.goto('/login')
  await page.fill('[name="email"]', 'test@example.com')
  await page.fill('[name="password"]', 'password')
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard')

  // Save auth state
  await context.storageState({ path: 'playwright/.auth/user.json' })
  await browser.close()
}

// In test
test('authenticated user can access dashboard', async ({ page }) => {
  // Use saved auth state
  await page.goto('/dashboard', {
    storageState: 'playwright/.auth/user.json'
  })

  await expect(page.locator('text=Dashboard')).toBeVisible()
})
```

## Best Practices

### 1. Use Page Object Model

- Encapsulate page logic in classes
- Reuse across tests
- Easier maintenance

### 2. Use Data Test IDs

```typescript
// In component
<button data-testid="submit-button">Submit</button>

// In test
await page.click('[data-testid="submit-button"]')
```

### 3. Wait for Elements

Playwright auto-waits, but be explicit:

```typescript
// Good
await expect(page.locator('button')).toBeVisible()
await page.click('button')

// Better - explicit wait
await page.waitForSelector('button', { state: 'visible' })
await page.click('button')
```

### 4. Use Fixtures

```typescript
// playwright/fixtures.ts
import { test as base } from '@playwright/test'
import { LoginPage } from './pages/LoginPage'

type TestFixtures = {
  loginPage: LoginPage
  authenticatedPage: Page
}

export const test = base.extend<TestFixtures>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page))
  },

  authenticatedPage: async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: 'playwright/.auth/user.json'
    })
    const page = await context.newPage()
    await use(page)
    await context.close()
  },
})

// Usage
test('test with fixtures', async ({ loginPage, authenticatedPage }) => {
  // Use fixtures
})
```

### 5. Test Isolation

- Each test should be independent
- Clean up test data
- Don't rely on test execution order

### 6. Error Handling

```typescript
test('handles API error', async ({ page }) => {
  // Intercept API call
  await page.route('**/api/assets', route => {
    route.fulfill({
      status: 500,
      body: JSON.stringify({ error: 'Server error' })
    })
  })

  await page.goto('/assets')
  await expect(page.locator('text=Error')).toBeVisible()
})
```

## CI/CD Integration

### GitHub Actions

The workflow is configured in `.github/workflows/playwright.yml`:

- Runs on push/PR to main/develop
- Tests all browsers in parallel
- Uploads reports and artifacts
- Mobile tests in separate job

### Local CI Simulation

```bash
# Run tests as in CI
CI=true npm run test:e2e
```

## Debugging

### Debug Mode

```bash
npm run test:e2e:debug
```

This opens Playwright Inspector where you can:
- Step through tests
- Inspect page state
- View console logs
- Take screenshots

### Screenshots and Videos

- Screenshots: Saved on failure to `playwright/test-results/`
- Videos: Saved on failure to `playwright/test-results/`
- Traces: Saved on retry to `playwright/test-results/`

View traces:
```bash
npx playwright show-trace trace.zip
```

### Console Logs

```typescript
// Listen to console
page.on('console', msg => console.log(msg.text()))

// Listen to network
page.on('request', request => console.log(request.url()))
page.on('response', response => console.log(response.status()))
```

## Performance Testing

```typescript
test('page loads quickly', async ({ page }) => {
  const startTime = Date.now()
  await page.goto('/dashboard')
  const loadTime = Date.now() - startTime

  expect(loadTime).toBeLessThan(3000) // 3 seconds
})
```

## Visual Testing

```typescript
test('page looks correct', async ({ page }) => {
  await page.goto('/dashboard')
  await expect(page).toHaveScreenshot('dashboard.png')
})
```

## Troubleshooting

### Tests are flaky

1. Increase timeouts
2. Use explicit waits
3. Check for race conditions
4. Review retry configuration

### Browser not found

```bash
npx playwright install
```

### Port already in use

```bash
# Kill process on port 3000
lsof -ti:3000 | xargs kill -9
```

### Tests timeout

Increase timeout in `playwright.config.ts`:
```typescript
timeout: 60 * 1000, // 60 seconds
```

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Playwright API](https://playwright.dev/docs/api/class-playwright)
