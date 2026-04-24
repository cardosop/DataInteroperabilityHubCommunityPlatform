/**
 * Self-test for the `no-bare-catch-in-tests` rule.
 *
 * Covers 226.A3 — bare `} catch { }` blocks. An empty catch body drops
 * the error on the floor. The rule accepts a body of only
 * line-or-block comments (counted as empty) and flags those too, since
 * the same silent-failure argument applies.
 *
 * Escape hatch: `// intentional: <why>` directly above the `catch` or
 * trailing on the `catch {` line.
 */

'use strict';

const { RuleTester } = require('eslint');
const rule = require('./no-bare-catch-in-tests.cjs');

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
});

ruleTester.run('no-bare-catch-in-tests', rule, {
  valid: [
    // Non-empty catch — rethrow, log, assign, call.
    {
      code: `try { f(); } catch (e) { throw e; }`,
    },
    {
      code: `try { f(); } catch (e) { console.error(e); }`,
    },
    {
      code: `try { f(); } catch (e) { errors.push(e); }`,
    },
    // Justified via `intentional:` leading comment.
    {
      code: `
        try { f(); }
        // intentional: best-effort teardown, failures handled by pref check
        catch { }
      `,
    },
    // Trailing-same-line justification.
    {
      code: `try { f(); } catch { } // intentional: race with auto-logout`,
    },
    // Justification INSIDE the empty catch body — common, readable
    // in-situ form where the author annotates the swallow next to the
    // site. Only honoured when the body is otherwise code-free.
    {
      code: `
        try { f(); } catch {
          // intentional: best-effort teardown, failures handled by pref check
        }
      `,
    },
    // Multi-line explanation comment starting with intentional:
    {
      code: `
        try { f(); } catch {
          // intentional: fall-through for missing-UI path; the caller's
          // subsequent visibility assertion produces the red on actual
          // breakage, not us.
        }
      `,
    },
    // No catch at all — fine.
    {
      code: `try { f(); } finally { g(); }`,
    },
  ],
  invalid: [
    // Empty catch with binding.
    {
      code: `try { f(); } catch (e) { }`,
      errors: [{ messageId: 'bareCatch' }],
    },
    // Empty catch without binding (ES2019+).
    {
      code: `try { f(); } catch { }`,
      errors: [{ messageId: 'bareCatch' }],
    },
    // Comment-only body — still silent.
    {
      code: `try { f(); } catch (e) { /* ignored */ }`,
      errors: [{ messageId: 'bareCatch' }],
    },
    {
      code: `try { f(); } catch {\n  // swallow\n}`,
      errors: [{ messageId: 'bareCatch' }],
    },
    // TODO-style comment isn't the escape hatch.
    {
      code: `
        // TODO: handle this
        try { f(); } catch { }
      `,
      errors: [{ messageId: 'bareCatch' }],
    },
  ],
});

console.log('no-bare-catch-in-tests: all rule cases passed');
