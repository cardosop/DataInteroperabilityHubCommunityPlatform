/**
 * Self-test for the `no-catch-swallow-in-tests` rule.
 *
 * Covers 226.A2 — the `.catch(() => null | undefined | 0 | false | '' | [] | {})`
 * silent-fallback pattern. When a spec writer chains a Promise with a
 * no-op `.catch`, a failing promise rejection becomes indistinguishable
 * from "test passed" — the exact silent-failure class the audit exists
 * to kill.
 *
 * Escape hatch: author justifies the survival with an
 * `// intentional: <why>` comment directly preceding (or on) the
 * `.catch(...)` call.
 */

'use strict';

const { RuleTester } = require('eslint');
const rule = require('./no-catch-swallow-in-tests.cjs');

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
});

ruleTester.run('no-catch-swallow-in-tests', rule, {
  valid: [
    // Identifier handler — throws, logs, assigns, etc. The rule only
    // targets hard-coded constant-returning arrow fallbacks.
    {
      code: `promise.catch((err) => { throw new Error(err.message); });`,
    },
    {
      code: `promise.catch(logError);`,
    },
    // Fallback that is NOT a constant — dynamic, therefore not a
    // silent-swallow.
    {
      code: `promise.catch((e) => handleError(e));`,
    },
    // Block-body that does real work (more than one return).
    {
      code: `promise.catch((err) => { console.warn(err); return null; });`,
    },
    // Justified fallback — `// intentional:` comment directly above.
    {
      code: `
        // intentional: background polling; stale tokens are expected here
        page.request.get(url).catch(() => null);
      `,
    },
    // Trailing justification on the same line.
    {
      code: `page.request.get(url).catch(() => null); // intentional: stale-token tolerance`,
    },
    // Not a `.catch` — `.then` with error arg is also valid sometimes.
    {
      code: `promise.then(onOk, onErr);`,
    },
    // No arg at all — fine.
    {
      code: `promise.catch();`,
    },
  ],
  invalid: [
    // () => null
    {
      code: `const x = await page.request.get(url).catch(() => null);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => undefined
    {
      code: `const x = await fetch(url).catch(() => undefined);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => 0
    {
      code: `const c = await locator.count().catch(() => 0);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => false
    {
      code: `const ok = await fetch(url).then(() => true).catch(() => false);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => ''
    {
      code: `const s = await el.textContent().catch(() => '');`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => []
    {
      code: `const arr = await api.list().catch(() => []);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => ({})
    {
      code: `const d = await api.get().catch(() => ({}));`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // () => { return null; } block form — equivalent silent swallow.
    {
      code: `await api.get().catch(() => { return null; });`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // .catch((err) => null) — still a silent swallow, the err binding
    // doesn't change the semantics.
    {
      code: `await api.get().catch((err) => null);`,
      errors: [{ messageId: 'silentFallback' }],
    },
    // Non-matching comment ('// TODO') must not be treated as intentional.
    {
      code: `
        // TODO: tighten this
        const x = await api.get().catch(() => null);
      `,
      errors: [{ messageId: 'silentFallback' }],
    },
  ],
});

console.log('no-catch-swallow-in-tests: all rule cases passed');
