/**
 * Self-test for the `no-test-skip-true` rule.
 *
 * Uses ESLint's built-in RuleTester — no extra deps. Runs via
 * `node frontend/e2e/.eslint-rules/no-test-skip-true.test.js`.
 * Exits non-zero on failure; CI invokes it from PR 5's test step.
 */

'use strict';

const { RuleTester } = require('eslint');
const rule = require('./no-test-skip-true.cjs');

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
});

ruleTester.run('no-test-skip-true', rule, {
  valid: [
    // Conditional skip — fine
    { code: "test.skip(process.env.CI === '1', 'CI-only')" },
    { code: "test.skip(!envReady, 'setup failed')" },
    // No args — fine (legitimate at the top of a test body to unconditionally skip)
    { code: 'test.skip()' },
    // Literal `false` is a no-op but not what we're gating against
    { code: "test.skip(false, 'disabled for now')" },
    // Different member — not the method we care about
    { code: 'test.fail(true)' },
    { code: 'expect(x).toBe(true)' },
    { code: 'test.describe.configure({ mode: "serial" })' },
  ],
  invalid: [
    {
      code: "test.skip(true, 'auth redirect is broken')",
      errors: [{ messageId: 'literalTrueSkip' }],
    },
    {
      // Positional-only form
      code: 'test.skip(true)',
      errors: [{ messageId: 'literalTrueSkip' }],
    },
    {
      // Renamed test object — still matches because we check the callee's
      // property, not the object.
      code: "guarded.skip(true, 'still broken')",
      errors: [{ messageId: 'literalTrueSkip' }],
    },
  ],
});

// RuleTester throws on failure; reaching here means everything passed.
console.log('no-test-skip-true: all rule cases passed');
