/**
 * Plugin-wiring tests for the Phase T.1 anti-pattern rules.
 *
 * Runs the REAL eslint flat config (frontend/eslint.config.js) through the
 * ESLint API against synthetic offenders — no mocks. Picked up
 * automatically by run-tests.cjs (same discovery as the custom rules).
 *
 * The contract under test:
 *   - Playwright specs (e2e/): `playwright/no-focused-test` (.only — NO
 *     baseline allowance; a focused test silently drops its siblings),
 *     `playwright/no-skipped-test`, `playwright/no-force-option`,
 *     `playwright/no-conditional-in-test`.
 *   - Vitest unit tests (src test files): `vitest/no-focused-tests`,
 *     `vitest/no-disabled-tests`, `vitest/expect-expect`.
 */

'use strict';

const path = require('node:path');
const { ESLint } = require('eslint');

const FRONTEND_DIR = path.resolve(__dirname, '..', '..');

async function lintSnippet(text, filePath) {
  const eslint = new ESLint({
    cwd: FRONTEND_DIR,
    overrideConfigFile: path.join(FRONTEND_DIR, 'eslint.config.js'),
  });
  const [result] = await eslint.lintText(text, { filePath });
  return result && result.messages ? result.messages : [];
}

const E2E_HEADER = "import { test, expect } from '@playwright/test';\n";
const UNIT_HEADER = "import { test, expect } from 'vitest';\n";

const cases = [
  // ── Playwright e2e ────────────────────────────────────────────────
  {
    label: 'e2e .only fails (no baseline allowance)',
    filePath: 'e2e/fake-spec.ts',
    text:
      E2E_HEADER +
      "test.only('focused', async ({ page }) => {\n  await page.goto('/');\n});\n",
    rule: 'playwright/no-focused-test',
    shouldFlag: true,
  },
  {
    label: 'e2e test.skip fails',
    filePath: 'e2e/fake-spec.ts',
    text: E2E_HEADER + "test.skip(true, 'not implemented');\n",
    rule: 'playwright/no-skipped-test',
    shouldFlag: true,
  },
  {
    label: 'e2e force option fails',
    filePath: 'e2e/fake-spec.ts',
    text: E2E_HEADER + "test('x', async ({ page }) => {\n  await page.click('#btn', { force: true });\n});\n",
    rule: 'playwright/no-force-option',
    shouldFlag: true,
  },
  {
    label: 'e2e conditional assertion fails',
    filePath: 'e2e/fake-spec.ts',
    text:
      E2E_HEADER +
      "test('x', async ({ page }) => {\n  if (Math.random() > 0.5) {\n    await expect(page).toHaveTitle('Dashboard');\n  }\n});\n",
    rule: 'playwright/no-conditional-in-test',
    shouldFlag: true,
  },
  {
    label: 'e2e clean spec stays clean',
    filePath: 'e2e/fake-spec.ts',
    text:
      E2E_HEADER +
      "test('x', async ({ page }) => {\n  await page.goto('/');\n  await expect(page).toHaveTitle('Dashboard');\n});\n",
    rule: 'playwright/no-focused-test',
    shouldFlag: false,
  },
  // ── Vitest unit ───────────────────────────────────────────────────
  {
    label: 'unit .only fails',
    filePath: 'src/fake.test.ts',
    text: UNIT_HEADER + "test.only('focused', () => {\n  expect(1).toBe(1);\n});\n",
    rule: 'vitest/no-focused-tests',
    shouldFlag: true,
  },
  {
    label: 'unit test.skip fails',
    filePath: 'src/fake.test.ts',
    text: UNIT_HEADER + "test.skip('disabled', () => {\n  expect(1).toBe(1);\n});\n",
    rule: 'vitest/no-disabled-tests',
    shouldFlag: true,
  },
  {
    label: 'unit test without expect fails',
    filePath: 'src/fake.test.ts',
    text: UNIT_HEADER + "test('vacuous', () => {\n  const x = 1;\n});\n",
    rule: 'vitest/expect-expect',
    shouldFlag: true,
  },
  {
    label: 'unit clean test stays clean',
    filePath: 'src/fake.test.ts',
    text: UNIT_HEADER + "test('ok', () => {\n  expect(1).toBe(1);\n});\n",
    rule: 'vitest/no-focused-tests',
    shouldFlag: false,
  },
];

// Rules that must be `error` (severity 2) — zero tolerance, no baseline.
const ZERO_TOLERANCE_RULES = new Set([
  'playwright/no-focused-test',
  'playwright/no-force-option',
  'vitest/no-focused-tests',
  'vitest/no-disabled-tests',
  'vitest/expect-expect',
]);

(async () => {
  let failed = 0;
  for (const { label, filePath, text, rule, shouldFlag } of cases) {
    const messages = await lintSnippet(text, filePath);
    const rules = messages.map((m) => m.ruleId);
    const present = rules.includes(rule);
    if (present !== shouldFlag) {
      failed += 1;
      console.error(
        `✗ ${label}: expected ${rule} to be ${shouldFlag ? 'FLAGGED' : 'CLEAN'}; ` +
          `got [${rules.join(', ')}]`
      );
      continue;
    }
    if (present && ZERO_TOLERANCE_RULES.has(rule)) {
      const severity = messages.find((m) => m.ruleId === rule).severity;
      if (severity !== 2) {
        failed += 1;
        console.error(
          `✗ ${label}: ${rule} fired with severity ${severity}, expected 2 (error) — ` +
            'zero-tolerance rules get no warn-level allowance'
        );
        continue;
      }
    }
    console.log(`✓ ${label}`);
  }
  if (failed > 0) {
    console.error(`\neslint-plugins-wiring: ${failed} case(s) failed`);
    process.exit(1);
  }
  console.log('eslint-plugins-wiring: all cases passed');
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
