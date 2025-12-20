#!/usr/bin/env node

/**
 * Import Analysis Utility
 *
 * Analyzes import patterns in the codebase to identify optimization opportunities.
 *
 * Usage:
 *   node scripts/analyze-imports.js [src-path]
 *
 * Reports:
 * - Barrel export usage
 * - Deep import opportunities
 * - Large library imports
 * - Potential tree-shaking issues
 */

import { readFileSync, readdirSync, statSync } from 'fs'
import { join, resolve, extname } from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = resolve(__filename, '..')

// Libraries that should use direct imports
const LARGE_LIBRARIES = {
  '@mui/material': {
    preferred: 'direct',
    message: 'Use direct imports: import Button from "@mui/material/Button"',
  },
  '@mui/icons-material': {
    preferred: 'direct',
    message: 'Use direct imports: import Icon from "@mui/icons-material/Icon"',
  },
  'lodash': {
    preferred: 'named',
    message: 'Use named imports: import { debounce } from "lodash-es"',
  },
  'lodash-es': {
    preferred: 'named',
    message: 'Use named imports: import { debounce } from "lodash-es"',
  },
}

// Patterns to identify
const PATTERNS = {
  barrelExport: /export\s+\*\s+from/,
  defaultImport: /import\s+\w+\s+from\s+['"]([^'"]+)['"]/,
  namedImport: /import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]/,
  namespaceImport: /import\s+\*\s+as\s+\w+\s+from\s+['"]([^'"]+)['"]/,
}

/**
 * Check if file is a TypeScript/JavaScript file
 */
function isSourceFile(file) {
  const ext = extname(file)
  return ['.ts', '.tsx', '.js', '.jsx'].includes(ext)
}

/**
 * Check if path should be ignored
 */
function shouldIgnore(path) {
  const ignorePatterns = [
    'node_modules',
    'dist',
    '.git',
    'coverage',
    'scripts',
    'docs',
    'test-utils',
  ]
  return ignorePatterns.some((pattern) => path.includes(pattern))
}

/**
 * Analyze a single file
 */
function analyzeFile(filePath) {
  const issues = []

  try {
    const content = readFileSync(filePath, 'utf-8')
    const lines = content.split('\n')

    lines.forEach((line, index) => {
      const lineNum = index + 1

      // Check for barrel exports
      if (PATTERNS.barrelExport.test(line)) {
        issues.push({
          type: 'barrel-export',
          line: lineNum,
          content: line.trim(),
          severity: 'info',
          message: 'Barrel export detected - ensure tree shaking works correctly',
        })
      }

      // Check for large library imports
      for (const [library, config] of Object.entries(LARGE_LIBRARIES)) {
        if (line.includes(`from '${library}'`) || line.includes(`from "${library}"`)) {
          if (config.preferred === 'direct') {
            issues.push({
              type: 'large-library-import',
              line: lineNum,
              content: line.trim(),
              severity: 'warning',
              message: config.message,
              library,
            })
          }
        }
      }

      // Check for namespace imports (may prevent tree shaking)
      if (PATTERNS.namespaceImport.test(line)) {
        const match = line.match(PATTERNS.namespaceImport)
        if (match && !shouldIgnore(match[1])) {
          issues.push({
            type: 'namespace-import',
            line: lineNum,
            content: line.trim(),
            severity: 'warning',
            message: 'Namespace import may prevent tree shaking - prefer named imports',
          })
        }
      }

      // Check for default imports from large libraries
      const defaultMatch = line.match(PATTERNS.defaultImport)
      if (defaultMatch) {
        const importPath = defaultMatch[1]
        if (LARGE_LIBRARIES[importPath]?.preferred === 'direct') {
          issues.push({
            type: 'default-import-large-lib',
            line: lineNum,
            content: line.trim(),
            severity: 'info',
            message: `Consider using direct import for ${importPath}`,
            library: importPath,
          })
        }
      }
    })
  } catch (error) {
    // Skip files that can't be read
  }

  return issues
}

/**
 * Recursively analyze directory
 */
function analyzeDirectory(dirPath, results = { files: 0, issues: [] }) {
  try {
    const entries = readdirSync(dirPath)

    for (const entry of entries) {
      const fullPath = join(dirPath, entry)

      if (shouldIgnore(fullPath)) {
        continue
      }

      const stats = statSync(fullPath)

      if (stats.isDirectory()) {
        analyzeDirectory(fullPath, results)
      } else if (stats.isFile() && isSourceFile(fullPath)) {
        results.files++
        const issues = analyzeFile(fullPath)
        if (issues.length > 0) {
          results.issues.push({
            file: fullPath,
            issues,
          })
        }
      }
    }
  } catch (error) {
    // Skip directories that can't be read
  }

  return results
}

/**
 * Format and print results
 */
function printResults(results) {
  console.log('\n📊 Import Analysis Results\n')
  console.log(`Files analyzed: ${results.files}`)
  console.log(`Files with issues: ${results.issues.length}\n`)

  if (results.issues.length === 0) {
    console.log('✅ No import optimization issues found!\n')
    return 0
  }

  // Group by severity
  const bySeverity = {
    warning: [],
    info: [],
  }

  results.issues.forEach((fileResult) => {
    fileResult.issues.forEach((issue) => {
      if (!bySeverity[issue.severity]) {
        bySeverity[issue.severity] = []
      }
      bySeverity[issue.severity].push({
        file: fileResult.file,
        ...issue,
      })
    })
  })

  // Print warnings
  if (bySeverity.warning.length > 0) {
    console.log(`⚠️  Warnings: ${bySeverity.warning.length}\n`)
    bySeverity.warning.forEach((issue) => {
      const relativePath = issue.file.replace(process.cwd() + '/', '')
      console.log(`  ${relativePath}:${issue.line}`)
      console.log(`    ${issue.message}`)
      console.log(`    ${issue.content}\n`)
    })
  }

  // Print info
  if (bySeverity.info.length > 0) {
    console.log(`ℹ️  Info: ${bySeverity.info.length}\n`)
    bySeverity.info.slice(0, 20).forEach((issue) => {
      const relativePath = issue.file.replace(process.cwd() + '/', '')
      console.log(`  ${relativePath}:${issue.line}`)
      console.log(`    ${issue.message}\n`)
    })

    if (bySeverity.info.length > 20) {
      console.log(`  ... and ${bySeverity.info.length - 20} more info items\n`)
    }
  }

  // Summary
  console.log('\n📋 Summary\n')
  console.log(`Total issues: ${results.issues.reduce((sum, f) => sum + f.issues.length, 0)}`)
  console.log(`Warnings: ${bySeverity.warning.length}`)
  console.log(`Info: ${bySeverity.info.length}\n`)

  if (bySeverity.warning.length > 0) {
    console.log('💡 Consider optimizing imports marked as warnings for better tree shaking.\n')
  }

  return bySeverity.warning.length > 0 ? 1 : 0
}

/**
 * Main execution
 */
function main() {
  const srcPath = process.argv[2] || resolve(__dirname, '..', 'src')
  const resolvedPath = resolve(srcPath)

  console.log(`\n🔍 Analyzing imports in: ${resolvedPath}\n`)

  try {
    const results = analyzeDirectory(resolvedPath)
    const exitCode = printResults(results)
    process.exit(exitCode)
  } catch (error) {
    console.error(`\n❌ Error analyzing imports: ${error.message}\n`)
    console.error(error.stack)
    process.exit(1)
  }
}

main()

