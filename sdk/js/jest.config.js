module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/src'],
  testMatch: ['**/__tests__/**/*.ts', '**/?(*.)+(spec|test).ts'],
  // W6.1 — test-env-config.ts is a shared HELPER imported by the e2e
  // suites, not a test suite; the bare __tests__ glob collected it as a
  // suite and failed with "Your test suite must contain at least one
  // test", which broke the prepublishOnly chain (build && test).
  // W6.2 — helpers/ holds the shared real-server helpers (same reason).
  testPathIgnorePatterns: ['/node_modules/', 'test-env-config\.ts$', 'helpers/'],
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/*.d.ts',
    '!src/generated/**',
    '!src/__tests__/**',
  ],
  coverageDirectory: 'coverage',
  coverageReporters: ['text', 'lcov', 'html', 'json'],
  coverageThreshold: {
    global: {
      branches: 100,
      functions: 100,
      lines: 100,
      statements: 100,
    },
  },
  testTimeout: 30000,
  verbose: true,
};

