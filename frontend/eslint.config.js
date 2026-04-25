import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'
import { createRequire } from 'node:module'

// CommonJS rule files; loaded via createRequire because this config is ES modules.
const require = createRequire(import.meta.url)
const noTestSkipTrueRule = require('./e2e/.eslint-rules/no-test-skip-true.cjs')
// 226.A silent-failure elimination rules. See e2e/.eslint-rules/README.md.
const noConditionalCountAssertionRule = require('./e2e/.eslint-rules/no-conditional-count-assertion.cjs')
const noCatchSwallowInTestsRule = require('./e2e/.eslint-rules/no-catch-swallow-in-tests.cjs')
const noBareCatchInTestsRule = require('./e2e/.eslint-rules/no-bare-catch-in-tests.cjs')

export default defineConfig([
  globalIgnores(['dist', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // Disable set-state-in-effect — common pattern for populating form state from fetched data
      // and resetting derived state (e.g. highlighted index on search change)
      'react-hooks/set-state-in-effect': 'off',
      // Phase 34 — Force icon imports through the registry
      'no-restricted-imports': ['error', {
        paths: [
          {
            name: 'lucide-react',
            message: 'Import icons via src/shared/config/iconRegistry.ts or use the Icon component.',
          },
          {
            name: 'axios',
            message: 'axios was removed due to supply chain compromise (UNC1069 RAT in v1.14.1). Use the shared API client: import { apiClient } from "shared/api/client".',
          },
        ],
      }],
      // Phase 56 — Block access_token localStorage writes outside E2E fixtures
      'no-restricted-syntax': ['error', {
        selector: "CallExpression[callee.object.name='localStorage'][callee.property.name='setItem'][arguments.0.value='access_token']",
        message: 'Do not write access_token to localStorage outside E2E test fixtures. Use httpOnly cookies (11.1).',
      }],
    },
  },
  // Allow direct lucide-react imports in Icon.tsx and iconRegistry.ts
  {
    files: ['**/Icon.tsx', '**/iconRegistry.ts'],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
  // Phase 56 — Allow access_token localStorage writes in E2E fixtures
  {
    files: ['e2e/**/*.ts', 'e2e/**/*.tsx'],
    rules: {
      'no-restricted-syntax': 'off',
    },
  },
  // Custom E2E-spec guard rules. Plugin-style so every rule lives under
  // the `e2e-guards/` prefix and can be disabled per-site with a standard
  // `// eslint-disable-next-line e2e-guards/<rule-name>` comment.
  //
  //   no-test-skip-true                 (PR 5) — error
  //   no-conditional-count-assertion    (226.A1) — warn during cleanup cycle,
  //                                                flip to error when the
  //                                                residual count hits the
  //                                                ≤ 30 target
  //   no-catch-swallow-in-tests         (226.A2) — same ramp: warn now,
  //                                                error at the ≤ 120 target
  //   no-bare-catch-in-tests            (226.A3) — warn now, flip to error
  //                                                once the count is 0
  //
  // Warn-level during the cleanup is deliberate: ESLint still surfaces
  // each site in CI output, but the build stays green so the cleanup PRs
  // can land incrementally without being blocked on their own progress.
  // The `// intentional: <why>` escape hatch each rule honours means new
  // well-justified uses do not accrue noise while the backlog drains.
  {
    files: ['e2e/**/*.ts', 'e2e/**/*.spec.ts'],
    plugins: {
      'e2e-guards': {
        rules: {
          'no-test-skip-true': noTestSkipTrueRule,
          'no-conditional-count-assertion': noConditionalCountAssertionRule,
          'no-catch-swallow-in-tests': noCatchSwallowInTestsRule,
          'no-bare-catch-in-tests': noBareCatchInTestsRule,
        },
      },
    },
    rules: {
      'e2e-guards/no-test-skip-true': 'error',
      // 226.A1 flipped to `error` 2026-04-24 once the per-file triage
      // brought the global count below the plan's ≤30 target. Each
      // remaining flagged site (now <30 across the suite) carries a
      // standard `// intentional: <why>` annotation, OR is a real
      // silent-failure that should fail CI. New regressions break the
      // build instead of accruing as warnings.
      'e2e-guards/no-conditional-count-assertion': 'error',
      'e2e-guards/no-catch-swallow-in-tests': 'warn',
      'e2e-guards/no-bare-catch-in-tests': 'warn',
      // Companion core ESLint rule — catches `catch (e) { throw e; }`
      // (body non-empty but useless). Pairs with `no-bare-catch-in-tests`
      // to cover both useless-catch shapes.
      'no-useless-catch': 'error',
    },
  },
])
