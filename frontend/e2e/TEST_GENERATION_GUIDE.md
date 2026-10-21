# E2E Test Generation Guide

**Last Updated**: 2026-02-02
**Status**: 📋 **Implementation Guide** (Phase 13 — three dimensions, USE_CASES alternate flows)

## Overview

This guide explains how to generate and implement E2E tests for Phase 10 — Full E2E Coverage. The goal is to cover all 101 journeys, 13 personas, ~109 use cases, and 28 features with comprehensive test dimensions (happy paths, failure scenarios, edge cases).

## Test Structure

### Directory Organization

```
frontend/e2e/
├── personas/              # Persona-based test suites
├── journeys/             # Individual journey tests
│   ├── auth/            # Authentication journeys
│   ├── dpo/             # Data Product Owner journeys
│   ├── de/              # Data Engineer journeys
│   ├── cpo/             # Compliance Officer journeys (CPO per docs/USER_JOURNEYS.md)
│   ├── dc/              # Data Consumer journeys
│   ├── ta/              # Tenant Admin journeys
│   ├── pa/              # Platform Admin journeys
│   ├── dev/             # External Developer journeys (DEV per docs/USER_JOURNEYS.md)
│   ├── aud/             # Auditor journeys (AUD per docs/USER_JOURNEYS.md)
│   ├── ds/              # Data Scientist journeys
│   ├── da/              # Data Analyst journeys
│   ├── cm/              # Community Manager journeys
│   ├── dmo/             # Data Mesh Domain Owner journeys
│   └── marketplace/     # Marketplace journeys
├── use-cases/            # Use case-based tests
├── features/             # Feature-based tests
├── dimensions/           # Test dimension tests (happy paths, failures, edge cases)
├── fixtures/             # Test fixtures and helpers
│   ├── auth.ts          # Authentication helpers
│   └── helpers.ts       # General test helpers
└── templates/            # Test templates
    └── journey-test-template.ts
```

## Test Generation Process

### Step 1: Choose Test Type

Decide which type of test to create:

- **Journey Test**: Tests a specific user journey (e.g., JOURNEY-DPO-001)
- **Persona Test**: Tests all journeys for a persona (e.g., Data Product Owner)
- **Use Case Test**: Tests a specific use case (e.g., UC-AUTH-001)
- **Feature Test**: Tests all functionality for a feature (e.g., Auth feature)

### Step 2: Use Template

1. Copy the appropriate template:

   ```bash
   cp frontend/e2e/templates/journey-test-template.ts frontend/e2e/journeys/{persona-prefix}/JOURNEY-{ID}.spec.ts
   ```

2. Replace placeholders:
   - `{JOURNEY_ID}` → Actual journey ID (e.g., `JOURNEY-DPO-001`)
   - `{JOURNEY_TITLE}` → Journey title (e.g., `Onboard New Asset via Data-First Flow`)
   - `{PERSONA}` → Persona name (e.g., `Data Product Owner`)
   - `{starting-route}` → Starting route (e.g., `/assets`)
   - `{route}` → Route path (e.g., `/assets/create`)

### Step 3: Implement Journey Steps

For each journey step, implement:

1. **Action**: What the user does (navigate, click, fill form, etc.)
2. **Verification**: What should happen (URL change, element visible, API response, etc.)

Example:

```typescript
{
  name: 'Step 1: Navigate to assets page',
  action: async () => {
    await page.goto('/assets', { waitUntil: 'domcontentloaded' });
    await waitForLoadingComplete(page);
  },
  verify: async () => {
    await expect(page).toHaveURL(/\/assets/);
    await assertVisible(page, '.asset-list-page');
  },
}
```

### Step 4: Add Test Dimensions (Phase 13 — three dimensions)

Each journey spec SHALL contain three test dimensions in the same file: `test.describe('Success')`, `test.describe('Failure')`, `test.describe('Edge')`. Reference **Alternate Flows (A1–An)** in `docs/USE_CASES.md` for each covered UC to add missing failure E2E where the UI can trigger the flow.

#### Success (Happy Path)

- All steps complete successfully
- Expected outcomes are achieved
- No errors occur

#### Failure Scenarios

- Invalid input validation
- API error responses (400, 401, 403, 404, 429, 500, 503)
- Duplicate/conflict (e.g. duplicate email, invalid/expired token)
- Network failures, timeout handling

#### Edge Cases

- Empty/null values, empty submit
- Maximum/minimum values
- Concurrent operations
- Special characters, long input
- Large payloads
- Protected route redirect to login; capability-gated redirect to `/unavailable`

### Step 5: Use Test Helpers

Use helpers from `fixtures/helpers.ts`:

- `assertSuccessfulLoad()` - **Dual verification (backend + frontend)** — prevents false positives. For success tests: start `page.waitForResponse()` before navigation, then call with `apiResponsePromise` and `successContentSelector`. Asserts API 2xx and no error UI. See `journeys/contracts-odps/contracts-odps-routes.spec.ts`.
- `waitForApiResponse()` - Wait for API call with retry
- `waitForElement()` - Wait for element with retry
- `fillField()` - Fill form field with validation
- `clickElement()` - Click element with retry
- `waitForNavigation()` - Wait for URL change
- `generateUniqueId()` - Generate unique test data
- `verifyHappyPath()` - Verify happy path scenario
- `verifyFailureScenario()` - Verify error handling; pass `expectedError.status` and `expectedError.urlPattern` to assert API HTTP status (see [TEST_ASSERTION_CONVENTIONS](../../docs/TEST_ASSERTION_CONVENTIONS.md))
- `verifyEdgeCase()` - Verify boundary conditions

## Test Implementation Checklist

For each test file, ensure:

- [ ] **Test Structure**
  - [ ] Test file follows naming convention: `JOURNEY-{ID}.spec.ts` or `UC-{ID}.spec.ts`
  - [ ] Test describe block includes journey/use case ID and title
  - [ ] Test timeout is appropriate (default: 180s for journeys, 60s for simple tests)

- [ ] **Setup/Teardown**
  - [ ] `beforeEach` logs in test user
  - [ ] `afterEach` cleans up test data (if needed)
  - [ ] Test data uses unique identifiers (timestamps, UUIDs)

- [ ] **Happy Path**
  - [ ] All journey steps are implemented
  - [ ] Each step has action and verification
  - [ ] Expected outcomes are verified
  - [ ] Performance targets are checked

- [ ] **Failure Scenarios**
  - [ ] Invalid input validation tested
  - [ ] Unauthorized access tested
  - [ ] API error responses tested
  - [ ] Error messages are user-friendly

- [ ] **Edge Cases**
  - [ ] Empty/null values tested
  - [ ] Maximum values tested
  - [ ] Special characters tested
  - [ ] Concurrent operations tested (if applicable)

- [ ] **Real Backend**
  - [ ] No mocks or stubs used
  - [ ] All API calls go through real backend
  - [ ] Test data is created/cleaned up properly

- [ ] **Documentation**
  - [ ] Test includes JSDoc comments
  - [ ] Journey/use case ID and title are documented
  - [ ] Test steps are clearly described

## Example: Creating a Journey Test

### 1. Find Journey Details

From `docs/USER_JOURNEYS.md`, find:

- Journey ID: `JOURNEY-DPO-001`
- Title: `Onboard New Asset via Data-First Flow`
- Persona: `Data Product Owner`
- Steps: Create asset → Upload file → Create dataset → Run compliance → Run DQ → Create contract → Activate

### 2. Create Test File

```bash
cp frontend/e2e/templates/journey-test-template.ts \
   frontend/e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts
```

### 3. Replace Placeholders

```typescript
test.describe('JOURNEY-DPO-001: Onboard New Asset via Data-First Flow', () => {
  // ... implementation
});
```

### 4. Implement Steps

```typescript
await verifyHappyPath(page, [
  {
    name: 'Step 1: Create asset',
    action: async () => {
      await page.goto('/assets/create', { waitUntil: 'domcontentloaded' });
      await fillField(page, 'input#key', generateUniqueId('asset'));
      await fillField(page, 'input#name', 'Test Asset');
      await clickElement(page, 'button[type="submit"]');
    },
    verify: async () => {
      await waitForApiResponse(page, /\/assets\/.*/, { status: 201 });
    },
  },
  // ... more steps
]);
```

### 5. Add Failure Scenarios

When the expected HTTP status is known, pass `expectedError.status` and `expectedError.urlPattern` so the helper intercepts the API call and asserts `response.status() === expectedError.status` (per [TEST_ASSERTION_CONVENTIONS](../../docs/TEST_ASSERTION_CONVENTIONS.md): assert status when known).

```typescript
test('failure scenario: invalid asset key', async ({ page }) => {
  await verifyFailureScenario(
    page,
    async () => {
      await page.goto('/assets/create', { waitUntil: 'domcontentloaded' });
      await fillField(page, 'input#key', 'invalid key with spaces');
      await clickElement(page, 'button[type="submit"]');
    },
    {
      status: 400,
      urlPattern: '/api/v1/assets/',  // API called by submit; intercept and assert status
      message: /invalid.*key/i,
      selector: '.error-message',
    }
  );
});
```

### Failure scenarios: asserting HTTP status

When the expected API response status is known (400, 401, 403, 404, 429, etc.), pass both:

- **`expectedError.status`** – the HTTP status code the API should return.
- **`expectedError.urlPattern`** – string or RegExp matching the request URL to intercept (e.g. `'/api/v1/assets/'`, `/\/api\/v1\/contracts\//`).

The helper will wait for a response matching `urlPattern` triggered by the action, then assert `response.status() === expectedError.status`. This follows [TEST_ASSERTION_CONVENTIONS](../../docs/TEST_ASSERTION_CONVENTIONS.md): use strict status assertion when the outcome is known. See `fixtures/helpers.ts` `verifyFailureScenario` JSDoc.

## Batch Test Generation

For generating multiple tests at once:

### Option 1: Manual Generation

1. Extract journey IDs from `docs/USER_JOURNEYS.md`
2. For each journey, create test file using template
3. Implement journey-specific steps

### Option 2: Script Generation (Future)

A script could be created to:

1. Parse `docs/USER_JOURNEYS.md` to extract journey details
2. Generate test files from template
3. Populate basic structure (needs manual implementation of steps)

## Test Execution

### Run Single Test

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  npx playwright test e2e/journeys/dpo/JOURNEY-DPO-001.spec.ts
```

### Run All Journey Tests

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  npx playwright test e2e/journeys/
```

### Run Tests by Persona

```bash
cd frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1 \
  npx playwright test e2e/journeys/dpo/
```

## Coverage Tracking

### Current Coverage

- **Journeys**: 4/101 (4%) - Auth journeys implemented
- **Personas**: 1/13 (8%) - Visitor persona implemented
- **Use Cases**: 4/~109 (4%) - Auth use cases implemented
- **Features**: 1/28 (4%) - Auth feature implemented

### Target Coverage

- **Journeys**: 101/101 (100%)
- **Personas**: 13/13 (100%)
- **Use Cases**: ~109/~109 (100%)
- **Features**: 28/28 (100%)

## Best Practices

1. **Test Isolation**: Each test should be independent and not rely on other tests
2. **Unique Data**: Use unique identifiers (timestamps, UUIDs) for test data
3. **Cleanup**: Clean up test data after tests (use `cleanupTestData()` helper)
4. **Error Handling**: Tests should handle errors gracefully and provide clear failure messages
5. **Performance**: Verify performance targets are met
6. **Real Backend**: Always use real backend API (no mocks/stubs)
7. **Rate Limiting**: Handle rate limiting gracefully (add delays, retries)
8. **Timeouts**: Set appropriate timeouts for each test (longer for complex journeys)

## Troubleshooting

### Test Fails with Timeout

- Increase test timeout: `test.setTimeout(300000)` // 5 minutes
- Check if backend services are running
- Verify API is accessible: `curl http://localhost:8000/health/`

### Test Fails with Rate Limit (429)

- Add delay between tests: `await page.waitForTimeout(2000)`
- Use sequential execution: `--workers=1`
- Retry logic is handled in `loginUser()` fixture

### Test Fails to Find Element

- Check selector is correct (use browser DevTools)
- Increase wait timeout: `{ timeout: 20000 }`
- Verify page loaded: `await waitForLoadingComplete(page)`

### Test Data Conflicts

- Use unique identifiers: `generateUniqueId('prefix')`
- Clean up test data: `await cleanupTestData(page, 'assets', [assetId])`

## Backend-Not-Implemented Handling

For use cases listed as **Not implemented (Backend)** in `docs/USE_CASES.md` (e.g. UC-CM-004, UC-CPO-006, UC-CPO-007, UC-CPO-008, UC-CPO-010, UC-DE-011, UC-DEV-002, UC-TA-007, UC-SOCIAL-005), E2E SHALL:

- **Skip** the test with `test.skip()` and a comment referencing the UC ID, or
- **Assert** that the app shows `/unavailable` or a clear "not available" message when the user attempts the flow.

Do not mock missing endpoints. See [E2E Full Coverage Plan — Backend-not-implemented handling](./E2E_FULL_COVERAGE_PLAN.md#backend-not-implemented-handling).

## CI (Phase 13 — 15.10.3)

- **Main E2E job**: Use headless project (e.g. `--project=chromium`) for the main E2E job.
- **Visible run**: Optional job or manual trigger for visible run with video/trace artifact for debugging (e.g. `--project=visible`, `trace: 'on'`, `video: 'on'`).

## References

- **[E2E Full Coverage Plan](./E2E_FULL_COVERAGE_PLAN.md)** - Complete test matrix
- **[E2E Pipeline Documentation](./E2E_PIPELINE_DOCUMENTATION.md)** - Test infrastructure
- **[User Journeys](../../docs/USER_JOURNEYS.md)** - Journey documentation
- **[Use Cases](../../docs/USE_CASES.md)** - Use case documentation
- **[Features](../../docs/FEATURES.md)** - Feature documentation

---

**Last Updated**: 2026-02-02
**Status**: 📋 **Implementation Guide** — Phase 13: three dimensions, USE_CASES alternate flows, CI headless/visible
