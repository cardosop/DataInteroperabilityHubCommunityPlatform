# Test Data Factories

**Last Updated**: 2025-01-27
**Version**: 1.0.0

---

## Overview

Comprehensive test data factories for the Data Interoperability Hub frontend. These factories provide type-safe, realistic test data generation for all major entities in the system.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Factory Usage](#factory-usage)
3. [Available Factories](#available-factories)
4. [Persona Factories](#persona-factories)
5. [Cleanup Utilities](#cleanup-utilities)
6. [Seeding Utilities](#seeding-utilities)
7. [Best Practices](#best-practices)

---

## Quick Start

### In-Memory Test Data (Unit Tests)

```tsx
import { assetFactory, userFactory, tenantFactory } from '@/tests/factories'

// Create a single asset
const asset = assetFactory.build()

// Create multiple assets
const assets = assetFactory.buildMany(5)

// Create with custom overrides
const customAsset = assetFactory.build({
  overrides: { name: 'Custom Asset', status: 'ACTIVE' }
})

// Use factory methods
const activeAsset = assetFactory.active()
const publicAsset = assetFactory.public()
```

### API-Based Test Data (Integration Tests)

```tsx
import { seedTestDataViaAPI, seedMinimalTestDataViaAPI } from '@/tests/factories'
import { createTestCleanup } from '@/tests/factories/cleanup'

// Seed test data via API (creates real data in API server)
beforeAll(async () => {
  const testData = await seedTestDataViaAPI({
    assetCount: 5,
    contractCount: 3,
  })
  // testData.assets, testData.contracts contain real API responses
})

// Cleanup after tests
afterAll(async () => {
  const cleanup = createTestCleanup()
  // Cleanup automatically handles registered test data
  await cleanup.cleanup()
})
```

---

## Factory Usage

### Basic Usage

All factories follow the same pattern:

```tsx
// Build a single instance
const instance = factory.build()

// Build with overrides
const custom = factory.build({ overrides: { field: 'value' } })

// Build multiple instances
const many = factory.buildMany(10)

// Build sequence with custom builder
const sequence = factory.buildSequence((index) => ({
  name: `Item ${index}`,
  // Return null/undefined to stop
}))
```

### Factory Methods

Most factories provide convenience methods for common scenarios:

```tsx
// Asset factory
assetFactory.draft()      // DRAFT status
assetFactory.active()      // ACTIVE status
assetFactory.public()      // PUBLIC visibility
assetFactory.complianceFailed()  // FAILED compliance

// User factory
userFactory.active()       // ACTIVE status
userFactory.invited()      // INVITED status
userFactory.platformAdmin() // Platform admin

// Job factory
jobFactory.pending()       // PENDING status
jobFactory.running()       // RUNNING status
jobFactory.completed()     // COMPLETED status
jobFactory.failed()        // FAILED status
```

---

## Available Factories

### Asset Factory

```tsx
import { assetFactory } from '@/tests/factories'

// Basic usage
const asset = assetFactory.build()

// With contract
const assetWithContract = assetFactory.withContract('contract-id')

// With dataset
const assetWithDataset = assetFactory.withDataset('dataset-id')

// Multiple assets
const assets = assetFactory.buildMany(10)
```

### Contract Factory

```tsx
import { contractFactory } from '@/tests/factories'

const contract = contractFactory.build()
const draftContract = contractFactory.draft()
const invalidContract = contractFactory.invalid()
```

### Dataset Factory

```tsx
import { datasetFactory } from '@/tests/factories'

const dataset = datasetFactory.build()
const csvDataset = datasetFactory.csv()
const jsonDataset = datasetFactory.json()
const parquetDataset = datasetFactory.parquet()
```

### User Factory

```tsx
import { userFactory } from '@/tests/factories'

const user = userFactory.build()
const admin = userFactory.platformAdmin()
const userWithRoles = userFactory.withRoles([role1, role2])
```

### Tenant Factory

```tsx
import { tenantFactory } from '@/tests/factories'

const tenant = tenantFactory.build()
const activeTenant = tenantFactory.active()
const suspendedTenant = tenantFactory.suspended()
```

### Job Factory

```tsx
import { jobFactory } from '@/tests/factories'

const job = jobFactory.build()
const runningJob = jobFactory.running()
const dqJob = jobFactory.ofType('DQ_RUN')
```

### Listing Factory

```tsx
import { listingFactory } from '@/tests/factories'

const listing = listingFactory.build()
const publishedListing = listingFactory.published()
const freeListing = listingFactory.free()
```

---

## Persona Factories

Persona factories create realistic, interconnected test data sets representing specific user roles:

```tsx
import {
  createDataProducerPersona,
  createDataConsumerPersona,
  createPlatformAdminPersona,
  createDataQualityEngineerPersona,
  createComplianceOfficerPersona,
  createMarketplacePublisherPersona,
} from '@/tests/factories'

// Data Producer - creates and publishes data
const producer = createDataProducerPersona()
// Returns: { user, tenant, assets, contracts, datasets, listings }

// Data Consumer - consumes marketplace data
const consumer = createDataConsumerPersona(producer.assets)

// Platform Admin - manages all tenants
const admin = createPlatformAdminPersona()

// Data Quality Engineer - focuses on data quality
const dqEngineer = createDataQualityEngineerPersona()

// Compliance Officer - focuses on compliance
const complianceOfficer = createComplianceOfficerPersona()

// Marketplace Publisher - publishes to marketplace
const publisher = createMarketplacePublisherPersona()
```

---

## Cleanup Utilities

### Automatic Cleanup

```tsx
import { cleanupTestData } from '@/tests/factories/cleanup'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanupTestData()
})
```

### Manual Cleanup

```tsx
import { createTestCleanup } from '@/tests/factories/cleanup'

const cleanup = createTestCleanup()

const asset = assetFactory.build()
cleanup.registerAsset(asset.id)

// After test
await cleanup.cleanup()
```

### Registry

```tsx
import { testDataRegistry } from '@/tests/factories/cleanup'

// Register items
testDataRegistry.registerAsset('asset-id')
testDataRegistry.registerUser('user-id')

// Get all registered IDs
const ids = testDataRegistry.getAllIds()

// Clear registry
testDataRegistry.clear()
```

---

## Seeding Utilities

### Comprehensive Seeding

```tsx
import { seedTestData } from '@/tests/factories/seeding'

beforeAll(async () => {
  const testData = await seedTestData({
    tenantCount: 3,
    usersPerTenant: 5,
    assetsPerTenant: 10,
    contractsPerTenant: 8,
    datasetsPerTenant: 10,
    jobsPerTenant: 15,
    listingsPerTenant: 5,
  })

  // Use testData in tests
  console.log(testData.tenants)
  console.log(testData.assets)
})
```

### Minimal Seeding

```tsx
import { seedMinimalTestData } from '@/tests/factories/seeding'

const minimalData = await seedMinimalTestData()
```

### Persona-Based Seeding

```tsx
import { seedPersonaTestData } from '@/tests/factories/seeding'

const producerData = await seedPersonaTestData('dataProducer')
const consumerData = await seedPersonaTestData('dataConsumer')
```

---

## Best Practices

### 1. Use Factories Instead of Manual Objects

✅ **Good**:
```tsx
const asset = assetFactory.build()
```

❌ **Bad**:
```tsx
const asset = {
  id: 'test-1',
  name: 'Test Asset',
  // ... many more fields
}
```

### 2. Use Factory Methods for Common Scenarios

✅ **Good**:
```tsx
const activeAsset = assetFactory.active()
const failedJob = jobFactory.failed()
```

❌ **Bad**:
```tsx
const activeAsset = assetFactory.build({
  overrides: { status: 'ACTIVE' }
})
```

### 3. Clean Up After Tests

✅ **Good**:
```tsx
import { cleanupTestData } from '@/tests/factories/cleanup'

afterEach(() => {
  cleanupTestData()
})
```

### 4. Use Personas for Complex Scenarios

✅ **Good**:
```tsx
const producer = createDataProducerPersona()
// Use producer.assets, producer.contracts, etc.
```

❌ **Bad**:
```tsx
const asset = assetFactory.build()
const contract = contractFactory.build()
// Manually link them...
```

### 5. Register Test Data for Cleanup

✅ **Good**:
```tsx
const cleanup = createTestCleanup()
const asset = assetFactory.build()
cleanup.registerAsset(asset.id)
// ... test code ...
await cleanup.cleanup()
```

### 6. Use Seeding for E2E Tests

✅ **Good**:
```tsx
beforeAll(async () => {
  const testData = await seedTestData()
  // Use testData throughout E2E tests
})
```

---

## Examples

### Unit Test Example

```tsx
import { describe, it, expect, afterEach } from 'vitest'
import { assetFactory, cleanupTestData } from '@/tests/factories'

describe('Asset Component', () => {
  afterEach(() => {
    cleanupTestData()
  })

  it('renders active asset', () => {
    const asset = assetFactory.active()
    // Test with asset
  })
})
```

### Integration Test Example

```tsx
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { createDataProducerPersona, cleanupTestData } from '@/tests/factories'

describe('Asset Management', () => {
  let producer: ReturnType<typeof createDataProducerPersona>

  beforeAll(() => {
    producer = createDataProducerPersona()
  })

  afterAll(() => {
    cleanupTestData()
  })

  it('manages assets', () => {
    // Use producer.assets, producer.contracts, etc.
  })
})
```

### E2E Test Example

```tsx
import { describe, it, expect, beforeAll } from 'vitest'
import { seedTestData } from '@/tests/factories/seeding'

describe('E2E: Marketplace', () => {
  let testData: Awaited<ReturnType<typeof seedTestData>>

  beforeAll(async () => {
    testData = await seedTestData({
      tenantCount: 2,
      assetsPerTenant: 5,
      listingsPerTenant: 3,
    })
  })

  it('browses marketplace', () => {
    // Use testData.listings, testData.assets, etc.
  })
})
```

---

## Summary

- ✅ Use factories for all test data creation
- ✅ Use factory methods for common scenarios
- ✅ Use personas for complex, interconnected data
- ✅ Clean up test data after tests
- ✅ Use seeding utilities for E2E tests
- ✅ Register test data for proper cleanup
- ✅ Follow factory patterns consistently

For questions or issues, refer to the factory source code or consult the development team.

