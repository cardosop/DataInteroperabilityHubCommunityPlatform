#!/usr/bin/env node

/**
 * Coverage Threshold Check Script
 *
 * Checks if coverage thresholds are met:
 * - 80% overall
 * - 85% components
 * - 90% hooks
 * - 95% utils
 *
 * Exits with code 1 if thresholds are not met.
 */

import { readFileSync, existsSync } from 'fs'
import { join } from 'path'

// Vitest generates coverage-summary.json in the coverage directory
// Path can be: coverage/coverage-summary.json or coverage/coverage-summary.json
const COVERAGE_SUMMARY_PATH = join(process.cwd(), 'coverage', 'coverage-summary.json')
const COVERAGE_JSON_PATH = join(process.cwd(), 'coverage', 'coverage-final.json')

/**
 * Convert Vitest coverage format to summary format
 * Vitest uses a different structure, so we need to convert it
 */
function convertVitestFormat(vitestData) {
  // Vitest format has a different structure
  // This is a simplified conversion - adjust based on actual Vitest output
  const summary = {
    total: {
      lines: { pct: 0, covered: 0, total: 0 },
      functions: { pct: 0, covered: 0, total: 0 },
      branches: { pct: 0, covered: 0, total: 0 },
      statements: { pct: 0, covered: 0, total: 0 },
    },
  }

  // If already in summary format, return as-is
  if (vitestData.total && vitestData.total.lines && typeof vitestData.total.lines.pct === 'number') {
    return vitestData
  }

  // Otherwise, calculate from file-level data
  // This is a fallback - Vitest should generate coverage-summary.json
  return summary
}

/**
 * Check if value meets threshold
 */
function meetsThreshold(value, threshold, metric) {
  if (value < threshold) {
    console.error(`❌ ${metric} coverage ${value.toFixed(2)}% is below threshold of ${threshold}%`)
    return false
  }
  return true
}

/**
 * Check coverage thresholds
 */
function checkCoverageThresholds() {
  try {
    // Try coverage-summary.json first (standard format)
    let coverageData
    if (existsSync(COVERAGE_SUMMARY_PATH)) {
      coverageData = JSON.parse(readFileSync(COVERAGE_SUMMARY_PATH, 'utf-8'))
    } else if (existsSync(COVERAGE_JSON_PATH)) {
      // Fallback to coverage-final.json (Vitest format)
      const finalData = JSON.parse(readFileSync(COVERAGE_JSON_PATH, 'utf-8'))
      // Convert Vitest format to summary format if needed
      coverageData = convertVitestFormat(finalData)
    } else {
      throw new Error('Coverage summary file not found')
    }

    let allPassed = true

    // Check overall thresholds (80%)
    console.log('\n📊 Overall Coverage:')
    const overall = coverageData.total
    const overallThreshold = 80

    if (
      !meetsThreshold(overall.lines.pct, overallThreshold, 'Lines') ||
      !meetsThreshold(overall.functions.pct, overallThreshold, 'Functions') ||
      !meetsThreshold(overall.branches.pct, overallThreshold, 'Branches') ||
      !meetsThreshold(overall.statements.pct, overallThreshold, 'Statements')
    ) {
      allPassed = false
    } else {
      console.log(`  ✅ Lines: ${overall.lines.pct.toFixed(2)}% (threshold: ${overallThreshold}%)`)
      console.log(`  ✅ Functions: ${overall.functions.pct.toFixed(2)}% (threshold: ${overallThreshold}%)`)
      console.log(`  ✅ Branches: ${overall.branches.pct.toFixed(2)}% (threshold: ${overallThreshold}%)`)
      console.log(`  ✅ Statements: ${overall.statements.pct.toFixed(2)}% (threshold: ${overallThreshold}%)`)
    }

    // Check component thresholds (85%)
    console.log('\n📦 Component Coverage:')
    const componentThreshold = 85
    const componentFiles = Object.keys(coverageData).filter(
      (key) =>
        key.includes('components/') &&
        !key.includes('__tests__') &&
        !key.includes('.test.') &&
        !key.includes('.spec.') &&
        key !== 'total'
    )

    if (componentFiles.length > 0) {
      let componentPassed = true
      const failedFiles = []

      for (const file of componentFiles) {
        const fileData = coverageData[file]
        if (!fileData) continue

        const metrics = {
          lines: fileData.lines?.pct || 0,
          functions: fileData.functions?.pct || 0,
          branches: fileData.branches?.pct || 0,
          statements: fileData.statements?.pct || 0,
        }

        if (
          metrics.lines < componentThreshold ||
          metrics.functions < componentThreshold ||
          metrics.branches < componentThreshold ||
          metrics.statements < componentThreshold
        ) {
          componentPassed = false
          failedFiles.push({
            file,
            ...metrics,
          })
        }
      }

      if (componentPassed) {
        console.log(`  ✅ All ${componentFiles.length} component files meet ${componentThreshold}% threshold`)
      } else {
        console.error(`  ❌ ${failedFiles.length} component file(s) below ${componentThreshold}% threshold:`)
        failedFiles.slice(0, 10).forEach(({ file, lines, functions, branches, statements }) => {
          console.error(`    - ${file}`)
          console.error(`      Lines: ${lines.toFixed(2)}%, Functions: ${functions.toFixed(2)}%, Branches: ${branches.toFixed(2)}%, Statements: ${statements.toFixed(2)}%`)
        })
        if (failedFiles.length > 10) {
          console.error(`    ... and ${failedFiles.length - 10} more files`)
        }
        allPassed = false
      }
    } else {
      console.log('  ⚠️ No component files found in coverage')
    }

    // Check hook thresholds (90%)
    console.log('\n🪝 Hook Coverage:')
    const hookThreshold = 90
    const hookFiles = Object.keys(coverageData).filter(
      (key) =>
        (key.includes('hooks/') || key.includes('/use') || key.includes('hook')) &&
        !key.includes('__tests__') &&
        !key.includes('.test.') &&
        !key.includes('.spec.') &&
        key !== 'total'
    )

    if (hookFiles.length > 0) {
      let hookPassed = true
      const failedFiles = []

      for (const file of hookFiles) {
        const fileData = coverageData[file]
        if (!fileData) continue

        const metrics = {
          lines: fileData.lines?.pct || 0,
          functions: fileData.functions?.pct || 0,
          branches: fileData.branches?.pct || 0,
          statements: fileData.statements?.pct || 0,
        }

        if (
          metrics.lines < hookThreshold ||
          metrics.functions < hookThreshold ||
          metrics.branches < hookThreshold ||
          metrics.statements < hookThreshold
        ) {
          hookPassed = false
          failedFiles.push({
            file,
            ...metrics,
          })
        }
      }

      if (hookPassed) {
        console.log(`  ✅ All ${hookFiles.length} hook files meet ${hookThreshold}% threshold`)
      } else {
        console.error(`  ❌ ${failedFiles.length} hook file(s) below ${hookThreshold}% threshold:`)
        failedFiles.slice(0, 10).forEach(({ file, lines, functions, branches, statements }) => {
          console.error(`    - ${file}`)
          console.error(`      Lines: ${lines.toFixed(2)}%, Functions: ${functions.toFixed(2)}%, Branches: ${branches.toFixed(2)}%, Statements: ${statements.toFixed(2)}%`)
        })
        if (failedFiles.length > 10) {
          console.error(`    ... and ${failedFiles.length - 10} more files`)
        }
        allPassed = false
      }
    } else {
      console.log('  ⚠️ No hook files found in coverage')
    }

    // Check utility thresholds (95%)
    console.log('\n🛠️ Utility Coverage:')
    const utilThreshold = 95
    const utilFiles = Object.keys(coverageData).filter(
      (key) =>
        (key.includes('utils/') || key.includes('lib/')) &&
        !key.includes('__tests__') &&
        !key.includes('.test.') &&
        !key.includes('.spec.') &&
        key !== 'total'
    )

    if (utilFiles.length > 0) {
      let utilPassed = true
      const failedFiles = []

      for (const file of utilFiles) {
        const fileData = coverageData[file]
        if (!fileData) continue

        const metrics = {
          lines: fileData.lines?.pct || 0,
          functions: fileData.functions?.pct || 0,
          branches: fileData.branches?.pct || 0,
          statements: fileData.statements?.pct || 0,
        }

        if (
          metrics.lines < utilThreshold ||
          metrics.functions < utilThreshold ||
          metrics.branches < utilThreshold ||
          metrics.statements < utilThreshold
        ) {
          utilPassed = false
          failedFiles.push({
            file,
            ...metrics,
          })
        }
      }

      if (utilPassed) {
        console.log(`  ✅ All ${utilFiles.length} utility files meet ${utilThreshold}% threshold`)
      } else {
        console.error(`  ❌ ${failedFiles.length} utility file(s) below ${utilThreshold}% threshold:`)
        failedFiles.slice(0, 10).forEach(({ file, lines, functions, branches, statements }) => {
          console.error(`    - ${file}`)
          console.error(`      Lines: ${lines.toFixed(2)}%, Functions: ${functions.toFixed(2)}%, Branches: ${branches.toFixed(2)}%, Statements: ${statements.toFixed(2)}%`)
        })
        if (failedFiles.length > 10) {
          console.error(`    ... and ${failedFiles.length - 10} more files`)
        }
        allPassed = false
      }
    } else {
      console.log('  ⚠️ No utility files found in coverage')
    }

    console.log('\n' + '='.repeat(50))
    if (allPassed) {
      console.log('✅ All coverage thresholds met!')
      process.exit(0)
    } else {
      console.log('❌ Some coverage thresholds not met')
      process.exit(1)
    }
  } catch (error) {
    console.error('❌ Error checking coverage thresholds:', error.message)
    console.error('⚠️ Coverage summary file not found or invalid')
    process.exit(1)
  }
}

// Run check
checkCoverageThresholds()

