import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

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
])
