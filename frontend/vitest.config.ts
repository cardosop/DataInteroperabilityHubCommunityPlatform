import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

/**
 * Vitest Configuration
 *
 * Comprehensive testing configuration for the Data Interoperability Hub frontend.
 * Vitest is used instead of Jest because it:
 * - Integrates seamlessly with Vite
 * - Uses the same configuration as Vite
 * - Provides faster test execution
 * - Has Jest-compatible API
 * - Supports ESM natively
 */

export default defineConfig({
  plugins: [react()],
  test: {
    // Test environment - use jsdom for DOM testing
    environment: 'jsdom',

    // Global test setup file
    setupFiles: ['./src/test-utils/setup.ts'],

    // Glob patterns for test files
    include: [
      'src/**/*.{test,spec}.{js,mjs,cjs,ts,mts,cts,jsx,tsx}',
      'src/**/__tests__/**/*.{js,mjs,cjs,ts,mts,cts,jsx,tsx}',
    ],

    // Exclude patterns
    exclude: [
      '**/node_modules/**',
      '**/dist/**',
      '**/cypress/**',
      '**/.{idea,git,cache,output,temp}/**',
      '**/playwright/**',
      '**/storybook-static/**',
      '**/test-utils.{ts,tsx,js,jsx}', // Exclude test utility files
      '**/__tests__/test-utils.{ts,tsx,js,jsx}', // Exclude test utility files in __tests__ directories
    ],

    // Global test timeout (in milliseconds)
    testTimeout: 10000,

    // Hook timeout (in milliseconds)
    hookTimeout: 10000,

    // Coverage configuration
    coverage: {
      // Coverage provider - use v8 for better performance
      provider: 'v8',

      // Coverage reporter
      reporter: [
        'text',
        'text-summary',
        'json',
        'json-summary',
        'html',
        'lcov',
      ],

      // Files to include in coverage
      include: [
        'src/**/*.{js,jsx,ts,tsx}',
      ],

      // Files to exclude from coverage
      exclude: [
        'src/**/*.d.ts',
        'src/**/*.stories.{js,jsx,ts,tsx}',
        'src/**/*.test.{js,jsx,ts,tsx}',
        'src/**/*.spec.{js,jsx,ts,tsx}',
        'src/**/__tests__/**',
        'src/**/__mocks__/**',
        'src/test-utils/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        'src/routes/**', // Route configuration files
        'src/types/**', // Type definition files
      ],

      // Coverage thresholds - enforce minimum coverage
      // Requirements: 80% overall, 85% components, 90% hooks, 95% utils
      // Note: Project uses Vitest (not Jest) for better Vite integration
      thresholds: {
        // Global thresholds (80% overall)
        lines: 80,
        functions: 80,
        branches: 80,
        statements: 80,

        // Component thresholds (85%)
        'src/components/**/*.{ts,tsx}': {
          lines: 85,
          functions: 85,
          branches: 85,
          statements: 85,
        },

        // Hook thresholds (90%)
        'src/**/*hooks*.{ts,tsx}': {
          lines: 90,
          functions: 90,
          branches: 90,
          statements: 90,
        },
        'src/hooks/**/*.{ts,tsx}': {
          lines: 90,
          functions: 90,
          branches: 90,
          statements: 90,
        },

        // Utility thresholds (95%)
        'src/utils/**/*.{ts,tsx}': {
          lines: 95,
          functions: 95,
          branches: 95,
          statements: 95,
        },
        'src/lib/**/*.{ts,tsx}': {
          lines: 95,
          functions: 95,
          branches: 95,
          statements: 95,
        },
      },

      // Coverage output directory
      reportsDirectory: './coverage',

      // Report coverage even if thresholds are not met
      reportOnFailure: true,

      // Skip full coverage report on watch mode for performance
      reportOnFailureOnly: false,

      // Check coverage against thresholds
      all: true,

      // Clean coverage results before running
      clean: true,

      // Clean coverage on watch mode
      cleanOnRerun: true,
    },

    // Globals - enable global test APIs (describe, it, expect, etc.)
    globals: true,

    // Mock reset between tests
    mockReset: true,

    // Restore mocks between tests
    restoreMocks: true,

    // Clear mocks between tests
    clearMocks: true,

    // Isolate test environment
    isolate: true,

    // Number of threads to use (0 = use all available cores)
    threads: true,

    // Maximum number of concurrent test files
    maxConcurrency: 5,

    // Retry failed tests (useful for flaky tests)
    retry: 0,

    // Bail on first test failure (useful for CI)
    bail: 0,

    // Silent mode (suppress console output)
    silent: false,

    // Verbose output
    verbose: true,

    // Reporter configuration
    reporters: ['verbose', 'json', 'junit'],

    // Output file for JSON reporter
    outputFile: {
      json: './test-results/results.json',
      junit: './test-results/junit.xml',
    },

    // Watch mode configuration
    watch: false,

    // Update snapshots
    update: false,

    // Snapshot options
    snapshotFormat: {
      escapeString: true,
      printBasicPrototype: false,
    },
  },

  // Resolve configuration (shared with Vite)
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  // Define environment variables for tests
  define: {
    // Mock environment variables for testing
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://localhost:8000'),
    'import.meta.env.VITE_WS_URL': JSON.stringify('ws://localhost:8000'),
    'import.meta.env.VITE_GRAPHQL_URL': JSON.stringify('http://localhost:8000/graphql'),
    'import.meta.env.VITE_ENV': JSON.stringify('development'),
    'import.meta.env.VITE_DEBUG': JSON.stringify('true'),
    'import.meta.env.DEV': JSON.stringify('true'),
    'import.meta.env.PROD': JSON.stringify('false'),
    'import.meta.env.MODE': JSON.stringify('development'),
  },
})

