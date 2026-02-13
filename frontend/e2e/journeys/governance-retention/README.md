# Governance Retention Policy E2E Tests

## Overview

Comprehensive E2E Playwright tests for Governance Retention Policy CRUD operations (Phase 15.5.3).

## Test File

`governance-retention-crud.spec.ts` - Complete CRUD flow testing

## Test Coverage

### List Page Tests

- ✅ List page loads correctly
- ✅ Create button navigation
- ✅ Empty state handling
- ✅ Table display with policies

### Create Page Tests

- ✅ Form fields rendering
- ✅ Form validation (required fields)
- ✅ Successful policy creation with API integration
- ✅ Error handling

### Detail Page Tests

- ✅ Policy details display
- ✅ Edit and Delete buttons
- ✅ Error handling for non-existent policies

### Edit Page Tests

- ✅ Form pre-population with policy data
- ✅ Form updates and submission
- ✅ API integration for updates
- ✅ Error handling

### Delete Operation Tests

- ✅ Confirmation dialog handling
- ✅ Delete flow

### Complete CRUD Flow Test

- ✅ End-to-end journey: list → create → view → edit → delete
- ✅ Full API integration
- ✅ Navigation verification

## Prerequisites

1. **Docker Compose Services Running:**

   ```bash
   docker compose up -d
   ```

2. **Frontend Dev Server Running:**

   ```bash
   cd frontend && npm run dev
   ```

3. **Backend API Available:**
   - API should be accessible at `http://localhost:8000/api/v1`
   - Health endpoint: `http://localhost:8000/health/`

## Running Tests

### Run All Retention Policy E2E Tests

```bash
cd frontend
npm run test:e2e -- e2e/journeys/governance-retention/governance-retention-crud.spec.ts
```

### Run with Authentication (Recommended)

```bash
cd frontend
npx playwright test e2e/journeys/governance-retention/governance-retention-crud.spec.ts --project=chromium-routes --timeout=120000
```

### Run Specific Test

```bash
cd frontend
npx playwright test e2e/journeys/governance-retention/governance-retention-crud.spec.ts --grep "retention policies list page loads"
```

### Run in Headed Mode (for debugging)

```bash
cd frontend
npx playwright test e2e/journeys/governance-retention/governance-retention-crud.spec.ts --project=visible
```

## Test Features

- **Real Backend Integration**: Tests use actual API endpoints (no mocks)
- **Authentication**: Uses authenticated session from `e2e/.auth/user.json`
- **Error Handling**: Gracefully handles both success and error scenarios
- **Wait Logic**: Proper waits for API responses and page loading
- **Timeout Handling**: 120s timeout for slow operations

## Test Structure

```
Governance Retention Policy CRUD
├── List Page
│   ├── retention policies list page loads
│   └── create button navigates to create page
├── Create Page
│   ├── create page loads with form fields
│   ├── create form validation works
│   └── create form can be filled and submitted
├── Detail Page
│   ├── detail page loads for existing policy
│   └── detail page shows edit and delete buttons
├── Edit Page
│   ├── edit page loads for existing policy
│   └── edit form can be updated and submitted
├── Delete Operation
│   └── delete button triggers confirmation
└── Complete CRUD Flow
    └── complete flow: list → create → view → edit → delete
```

## Notes

- Tests are designed to be resilient and handle both success and error scenarios
- Some tests use conditional logic to handle cases where policies don't exist
- The complete CRUD flow test creates a real policy and can optionally delete it
- All tests verify API responses and navigation flows
