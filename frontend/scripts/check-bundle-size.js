#!/usr/bin/env node

/**
 * Bundle Size Checker
 *
 * Validates bundle sizes against configured budgets.
 * This script analyzes the build output and reports any violations.
 *
 * Usage:
 *   node scripts/check-bundle-size.js [dist-path]
 *
 * Environment variables:
 *   BUNDLE_SIZE_BUDGET_JSON - Path to budget JSON file (default: bundle-size-budget.json)
 */

import { readFileSync, readdirSync, statSync } from 'fs'
import { join, resolve } from 'path'
import { fileURLToPath } from 'url'
import { gzipSync } from 'zlib'

const __filename = fileURLToPath(import.meta.url)
const __dirname = resolve(__filename, '..')

// Bundle size budgets (in KB)
const BUNDLE_BUDGETS = {
  // Initial load bundle (main entry point)
  initial: {
    maxSize: 200, // 200KB gzipped
    maxUncompressed: 500, // 500KB uncompressed
  },
  // Individual chunk limits
  chunk: {
    maxSize: 500, // 500KB gzipped per chunk
    maxUncompressed: 1200, // 1.2MB uncompressed per chunk
  },
  // Total bundle size
  total: {
    maxSize: 1000, // 1MB gzipped total
    maxUncompressed: 2500, // 2.5MB uncompressed total
  },
  // Vendor chunk limits
  vendor: {
    maxSize: 600, // 600KB gzipped per vendor chunk
    maxUncompressed: 1500, // 1.5MB uncompressed per vendor chunk
  },
}

/**
 * Get file size in bytes
 */
function getFileSize(filePath) {
  try {
    const stats = statSync(filePath)
    return stats.size
  } catch (error) {
    return 0
  }
}

/**
 * Get gzipped size of a file
 */
function getGzippedSize(filePath) {
  try {
    const content = readFileSync(filePath)
    const gzipped = gzipSync(content, { level: 9 })
    return gzipped.length
  } catch (error) {
    return 0
  }
}

/**
 * Format bytes to human-readable size
 */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

/**
 * Analyze bundle directory
 */
function analyzeBundle(distPath) {
  const assetsPath = join(distPath, 'assets')
  const jsPath = join(assetsPath, 'js')

  if (!statSync(jsPath).isDirectory()) {
    throw new Error(`JavaScript assets directory not found: ${jsPath}`)
  }

  const files = readdirSync(jsPath)
    .filter((file) => file.endsWith('.js'))
    .map((file) => ({
      name: file,
      path: join(jsPath, file),
    }))

  const analysis = {
    files: [],
    totals: {
      uncompressed: 0,
      gzipped: 0,
    },
    violations: [],
  }

  for (const file of files) {
    const uncompressed = getFileSize(file.path)
    const gzipped = getGzippedSize(file.path)
    const isVendor = file.name.includes('vendor')
    const isInitial = file.name.includes('index') || file.name.includes('main')

    analysis.files.push({
      name: file.name,
      uncompressed,
      gzipped,
      isVendor,
      isInitial,
    })

    analysis.totals.uncompressed += uncompressed
    analysis.totals.gzipped += gzipped

    // Check budgets
    const budget = isVendor ? BUNDLE_BUDGETS.vendor : BUNDLE_BUDGETS.chunk
    const sizeKB = gzipped / 1024
    const uncompressedKB = uncompressed / 1024

    if (sizeKB > budget.maxSize) {
      analysis.violations.push({
        file: file.name,
        type: 'gzipped',
        actual: sizeKB,
        budget: budget.maxSize,
        message: `Gzipped size ${formatSize(gzipped)} exceeds budget of ${budget.maxSize} KB`,
      })
    }

    if (uncompressedKB > budget.maxUncompressed) {
      analysis.violations.push({
        file: file.name,
        type: 'uncompressed',
        actual: uncompressedKB,
        budget: budget.maxUncompressed,
        message: `Uncompressed size ${formatSize(uncompressed)} exceeds budget of ${budget.maxUncompressed} KB`,
      })
    }
  }

  // Check total budgets
  const totalGzippedKB = analysis.totals.gzipped / 1024
  const totalUncompressedKB = analysis.totals.uncompressed / 1024

  if (totalGzippedKB > BUNDLE_BUDGETS.total.maxSize) {
    analysis.violations.push({
      file: 'TOTAL',
      type: 'total-gzipped',
      actual: totalGzippedKB,
      budget: BUNDLE_BUDGETS.total.maxSize,
      message: `Total gzipped size ${formatSize(analysis.totals.gzipped)} exceeds budget of ${BUNDLE_BUDGETS.total.maxSize} KB`,
    })
  }

  if (totalUncompressedKB > BUNDLE_BUDGETS.total.maxUncompressed) {
    analysis.violations.push({
      file: 'TOTAL',
      type: 'total-uncompressed',
      actual: totalUncompressedKB,
      budget: BUNDLE_BUDGETS.total.maxUncompressed,
      message: `Total uncompressed size ${formatSize(analysis.totals.uncompressed)} exceeds budget of ${BUNDLE_BUDGETS.total.maxUncompressed} KB`,
    })
  }

  return analysis
}

/**
 * Main execution
 */
function main() {
  const distPath = process.argv[2] || resolve(__dirname, '..', 'dist')
  const resolvedPath = resolve(distPath)

  console.log(`\n📦 Analyzing bundle sizes in: ${resolvedPath}\n`)

  try {
    const analysis = analyzeBundle(resolvedPath)

    // Print summary
    console.log('📊 Bundle Size Summary\n')
    console.log(`Total Files: ${analysis.files.length}`)
    console.log(`Total Uncompressed: ${formatSize(analysis.totals.uncompressed)}`)
    console.log(`Total Gzipped: ${formatSize(analysis.totals.gzipped)}`)
    console.log(`\nLargest Files (Gzipped):\n`)

    analysis.files
      .sort((a, b) => b.gzipped - a.gzipped)
      .slice(0, 10)
      .forEach((file) => {
        const size = formatSize(file.gzipped)
        const uncompressed = formatSize(file.uncompressed)
        const type = file.isVendor ? '[Vendor]' : file.isInitial ? '[Initial]' : '[Chunk]'
        console.log(`  ${type} ${file.name}: ${size} (${uncompressed} uncompressed)`)
      })

    // Report violations
    if (analysis.violations.length > 0) {
      console.log(`\n⚠️  Bundle Size Violations: ${analysis.violations.length}\n`)
      analysis.violations.forEach((violation) => {
        console.log(`  ❌ ${violation.file}: ${violation.message}`)
        console.log(`     Actual: ${violation.actual.toFixed(2)} KB, Budget: ${violation.budget} KB`)
      })
      console.log('\n')
      process.exit(1)
    } else {
      console.log(`\n✅ All bundle sizes within budget!\n`)
      process.exit(0)
    }
  } catch (error) {
    console.error(`\n❌ Error analyzing bundle: ${error.message}\n`)
    console.error(error.stack)
    process.exit(1)
  }
}

main()

