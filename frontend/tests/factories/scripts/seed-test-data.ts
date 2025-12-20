#!/usr/bin/env tsx
/**
 * Test Data Seeding Script
 *
 * Script for seeding test data via API calls.
 * This can be run standalone or as part of test setup.
 *
 * Usage:
 *   tsx tests/factories/scripts/seed-test-data.ts [options]
 *
 * Options:
 *   --minimal    Seed minimal test data
 *   --count N    Seed N items of each type
 *   --cleanup    Clean up seeded data after seeding (for testing)
 */

import { seedTestDataViaAPI, seedMinimalTestDataViaAPI } from '../api-seeding'
import { cleanupTestDataByType, testDataRegistry } from '../cleanup'

async function main() {
  const args = process.argv.slice(2)
  const isMinimal = args.includes('--minimal')
  const cleanupIndex = args.indexOf('--cleanup')
  const shouldCleanup = cleanupIndex !== -1
  const countIndex = args.indexOf('--count')
  const count = countIndex !== -1 && args[countIndex + 1]
    ? parseInt(args[countIndex + 1], 10)
    : undefined

  console.log('🌱 Seeding test data via API...')

  try {
    let seededData

    if (isMinimal) {
      console.log('   Using minimal seeding configuration')
      seededData = await seedMinimalTestDataViaAPI()
    } else if (count) {
      console.log(`   Seeding ${count} items of each type`)
      seededData = await seedTestDataViaAPI({
        assetCount: count,
        contractCount: count,
        datasetCount: 0, // Skip datasets as they require file upload
      })
    } else {
      console.log('   Using default seeding configuration')
      seededData = await seedTestDataViaAPI()
    }

    console.log('✅ Test data seeded successfully:')
    console.log(`   - Assets: ${seededData.assets.length}`)
    console.log(`   - Contracts: ${seededData.contracts.length}`)
    console.log(`   - Datasets: ${seededData.datasets.length}`)

    const registry = testDataRegistry.getAllIds()
    console.log('\n📋 Registered for cleanup:')
    console.log(`   - Assets: ${registry.assets.length}`)
    console.log(`   - Contracts: ${registry.contracts.length}`)
    console.log(`   - Datasets: ${registry.datasets.length}`)

    if (shouldCleanup) {
      console.log('\n🧹 Cleaning up seeded data...')

      if (registry.contracts.length > 0) {
        await cleanupTestDataByType('contracts', registry.contracts)
      }
      if (registry.assets.length > 0) {
        await cleanupTestDataByType('assets', registry.assets)
      }

      console.log('✅ Cleanup completed')
    } else {
      console.log('\n💡 Tip: Use --cleanup flag to clean up seeded data')
      console.log('   Or use the cleanup utilities in your test teardown')
    }
  } catch (error) {
    console.error('❌ Failed to seed test data:', error)
    process.exit(1)
  }
}

// Run if executed directly
if (require.main === module) {
  main().catch((error) => {
    console.error('Fatal error:', error)
    process.exit(1)
  })
}

export { main as seedTestDataScript }

