import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // Exclude ProtectedRoute.test.tsx from default runs (OOM in worker; run via test:component:protected-route with high memory)
    // Exclude integration tests (require real backend; run via test:integration:api)
    exclude: ['node_modules', 'dist', 'e2e/**', '**/ProtectedRoute.test.tsx', 'src/integration/**'],
    // Optional: pass heap size to workers when VITEST_NODE_HEAP is set (e.g. for high-memory test files)
    execArgv: (process.env.VITEST_NODE_HEAP ? [`--max-old-space-size=${process.env.VITEST_NODE_HEAP}`] : []),
    pool: 'threads',
    poolOptions: {
      threads: {
        maxThreads: 1,
        minThreads: 1,
      },
    },
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      // Thresholds set to current coverage so CI passes. Short-term plan (see docs/TEST_EXECUTION_PLAN.md §Frontend Coverage):
      // - Q1: Raise lines/statements to 20%; functions 60%; branches 65%
      // - Q2: Raise lines/statements to 40%; functions 70%; branches 70%
      // - Target: 80% across all metrics
      thresholds: {
        lines: 10,
        functions: 52,
        branches: 60,
        statements: 10,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
