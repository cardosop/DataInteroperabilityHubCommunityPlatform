# Test Coverage Guide

**Last Updated**: 2025-01-27
**Version**: 1.0.0

---

## Overview

This document describes the test coverage configuration and requirements for the Data Interoperability Hub frontend application.

**Note**: The project uses **Vitest** (not Jest) for test coverage because:
- Seamless integration with Vite
- Faster test execution
- Better performance with v8 coverage provider
- Native ESM support

---

## Coverage Requirements

### Thresholds

The project enforces the following coverage thresholds:

| Category | Threshold | Metric |
|----------|-----------|--------|
| **Overall** | 80% | Lines, Functions, Branches, Statements |
| **Components** | 85% | Lines, Functions, Branches, Statements |
| **Hooks** | 90% | Lines, Functions, Branches, Statements |
| **Utils/Lib** | 95% | Lines, Functions, Branches, Statements |

### Rationale

- **Overall (80%)**: Ensures good baseline coverage across the entire codebase
- **Components (85%)**: Components are user-facing and critical for functionality
- **Hooks (90%)**: Hooks contain business logic and state management
- **Utils/Lib (95%)**: Utility functions are foundational and should be highly tested

---

## Running Coverage

### Basic Commands

```bash
# Run tests with coverage
npm run test:coverage

# Run tests with coverage in watch mode
npm run test:coverage:watch

# Run tests with coverage and check thresholds
npm run test:coverage:check

# Run tests with coverage and open HTML report
npm run test:coverage:html
```

### Coverage Reports

Coverage reports are generated in the `coverage/` directory:

- **HTML Report**: `coverage/index.html` - Interactive HTML report
- **JSON Summary**: `coverage/coverage-summary.json` - Machine-readable summary
- **LCOV Report**: `coverage/lcov.info` - For CI/CD integration
- **Text Summary**: Console output with summary

---

## Coverage Configuration

### Vitest Configuration

Coverage is configured in `vitest.config.ts`:

```typescript
coverage: {
  provider: 'v8',
  reporter: ['text', 'text-summary', 'json', 'json-summary', 'html', 'lcov'],
  include: ['src/**/*.{js,jsx,ts,tsx}'],
  exclude: [
    'src/**/*.d.ts',
    'src/**/*.stories.{js,jsx,ts,tsx}',
    'src/**/*.test.{js,jsx,ts,tsx}',
    'src/**/*.spec.{js,jsx,ts,tsx}',
    'src/**/__tests__/**',
    'src/test-utils/**',
  ],
  thresholds: {
    // Global: 80%
    lines: 80,
    functions: 80,
    branches: 80,
    statements: 80,

    // Components: 85%
    'src/components/**/*.{ts,tsx}': {
      lines: 85,
      functions: 85,
      branches: 85,
      statements: 85,
    },

    // Hooks: 90%
    'src/hooks/**/*.{ts,tsx}': {
      lines: 90,
      functions: 90,
      branches: 90,
      statements: 90,
    },

    // Utils: 95%
    'src/utils/**/*.{ts,tsx}': {
      lines: 95,
      functions: 95,
      branches: 95,
      statements: 95,
    },
  },
}
```

---

## Checking Coverage Thresholds

### Automated Check

The `check-coverage-thresholds.js` script validates all thresholds:

```bash
node scripts/check-coverage-thresholds.js
```

This script:
- Reads `coverage/coverage-summary.json`
- Checks overall coverage (80%)
- Checks component coverage (85%)
- Checks hook coverage (90%)
- Checks utility coverage (95%)
- Exits with code 1 if any threshold is not met

### Manual Check

View the HTML report:

```bash
open coverage/index.html
```

Or check the JSON summary:

```bash
cat coverage/coverage-summary.json | jq '.total'
```

---

## CI/CD Integration

### GitHub Actions

Coverage is automatically:
1. **Generated** during test runs
2. **Checked** against thresholds
3. **Uploaded** as artifacts
4. **Reported** to Codecov
5. **Commented** on PRs

### Coverage Artifacts

The following artifacts are uploaded:
- `coverage/` - Full coverage directory (30 days retention)
- HTML reports for interactive viewing
- JSON summaries for programmatic access
- LCOV files for CI/CD integration

### Codecov Integration

Coverage is uploaded to Codecov with:
- **Flag**: `frontend`
- **Target**: 80%
- **Threshold**: 1%

View coverage on Codecov:
- Project dashboard
- PR comments with coverage diff
- Coverage trends over time

---

## Improving Coverage

### Identifying Gaps

1. **View HTML Report**: Open `coverage/index.html` to see uncovered lines
2. **Check Threshold Script**: Run `npm run test:coverage:check` to see failing files
3. **Review PR Comments**: CI/CD comments show coverage changes

### Best Practices

1. **Test Critical Paths First**: Focus on user-facing functionality
2. **Test Edge Cases**: Cover error conditions and boundary cases
3. **Test Utilities Thoroughly**: Utils are reused and should be highly tested
4. **Test Hooks Completely**: Hooks contain business logic
5. **Maintain Component Tests**: Components are user-facing

### Common Issues

#### Coverage Below Threshold

**Problem**: Coverage is below required threshold

**Solution**:
1. Identify uncovered lines in HTML report
2. Write tests for uncovered code
3. Re-run coverage check
4. Verify thresholds are met

#### False Positives

**Problem**: Coverage shows uncovered code that's actually tested

**Solution**:
1. Check test file is in correct location
2. Verify test is actually running
3. Check for dynamic imports or code splitting
4. Review coverage exclusions

#### Slow Coverage Generation

**Problem**: Coverage generation is slow

**Solution**:
1. Use `--coverage` flag only when needed
2. Use watch mode for faster feedback
3. Exclude unnecessary files from coverage
4. Use `reportOnFailureOnly` in watch mode

---

## Coverage Metrics

### Understanding Metrics

- **Lines**: Percentage of executable lines covered
- **Functions**: Percentage of functions called
- **Branches**: Percentage of conditional branches taken
- **Statements**: Percentage of statements executed

### Target Metrics

All metrics must meet thresholds:
- Overall: 80% for all metrics
- Components: 85% for all metrics
- Hooks: 90% for all metrics
- Utils: 95% for all metrics

---

## Troubleshooting

### Coverage Not Generated

1. **Check Provider**: Ensure `@vitest/coverage-v8` is installed
2. **Check Config**: Verify coverage config in `vitest.config.ts`
3. **Check Files**: Ensure files are in `include` patterns
4. **Check Exclusions**: Verify files aren't in `exclude` patterns

### Thresholds Not Enforced

1. **Check Script**: Run `npm run test:coverage:check`
2. **Check CI**: Verify CI/CD runs coverage check
3. **Check Config**: Verify thresholds in `vitest.config.ts`
4. **Check Reports**: View HTML report for details

### Coverage Inaccurate

1. **Check Exclusions**: Review excluded files
2. **Check Source Maps**: Ensure source maps are generated
3. **Check Instrumentation**: Verify code is instrumented
4. **Check Reports**: Compare HTML and JSON reports

---

## Resources

### Documentation

- [Vitest Coverage](https://vitest.dev/guide/coverage.html)
- [v8 Coverage Provider](https://github.com/vitest-dev/vitest/tree/main/packages/coverage-v8)
- [Codecov Documentation](https://docs.codecov.com/)

### Tools

- **HTML Report**: Interactive coverage visualization
- **Codecov**: Coverage tracking and reporting
- **Threshold Script**: Automated threshold checking

---

## Summary

- ✅ Coverage configured with Vitest (v8 provider)
- ✅ Thresholds enforced: 80% overall, 85% components, 90% hooks, 95% utils
- ✅ CI/CD integration with automated checks
- ✅ Codecov integration for tracking
- ✅ PR comments with coverage reports

For questions or issues, refer to the troubleshooting section or consult the development team.

