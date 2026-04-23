/**
 * ESLint rule: `e2e-guards/no-test-skip-true`
 *
 * Forbids `test.skip(true, ...)` and `test.skip.true-ish-literal` patterns
 * where the first argument is the literal boolean `true`. The guidance
 * from the dual-channel verification roll-out (PR 5 of the plan) is:
 *
 *   * Permanent env blockers → use `test.fail(true, 'reason')` instead,
 *     so when the underlying issue is fixed the test flips from expected-
 *     fail to unexpected-pass and surfaces as a cleanup signal.
 *   * Fixed / resurrected paths → delete the skip call entirely.
 *   * Genuinely-flaky env checks → keep `test.skip(<condition>, 'reason')`
 *     with the boolean replaced by an env-driven check.
 *
 * This rule catches REGRESSIONS only — it does not retroactively
 * reformat the 430-odd existing `test.skip(true, ...)` call sites. That
 * full audit is the "PR 5 cleanup" work noted in the plan.
 *
 * Autofix
 * -------
 * Not provided. The right replacement is context-dependent: fail-true,
 * delete, or convert to a conditional skip. Humans pick; a naive autofix
 * would just produce noise and lose the cleanup signal the rule exists
 * to create.
 */

'use strict';

/** @type {import('eslint').Rule.RuleModule} */
module.exports = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Disallow `test.skip(true, ...)` in Playwright specs — use test.fail(true) for known-failing paths, delete for fixed, or convert to a conditional skip.',
      recommended: true,
    },
    schema: [],
    messages: {
      literalTrueSkip:
        "Forbidden: `test.skip(true, ...)`. Use `test.fail(true, 'reason (TICKET-N)')` for known-failing paths, delete the call if the path is actually working, or convert to a conditional `test.skip(<condition>, 'reason')`.",
    },
  },

  create(context) {
    /**
     * Match `test.skip(<first-arg>, ...)` call expressions where the
     * first argument is the boolean literal `true`.
     * Also catches `someTest.skip(true, ...)` where `someTest` is the
     * renamed base object from `test.extend`.
     */
    return {
      CallExpression(node) {
        const callee = node.callee;
        if (
          !callee ||
          callee.type !== 'MemberExpression' ||
          callee.property.type !== 'Identifier' ||
          callee.property.name !== 'skip' ||
          callee.computed
        ) {
          return;
        }

        const first = node.arguments[0];
        if (
          first &&
          first.type === 'Literal' &&
          first.value === true
        ) {
          context.report({ node, messageId: 'literalTrueSkip' });
        }
      },
    };
  },
};
