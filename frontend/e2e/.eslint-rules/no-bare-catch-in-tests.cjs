/**
 * ESLint rule: `e2e-guards/no-bare-catch-in-tests`
 *
 * Covers 226.A3 (silent-failure elimination). Forbids bare catch
 * blocks whose body is empty (or contains only comments / whitespace).
 *
 *     try { ... }
 *     catch (e) { }
 *
 *     try { ... }
 *     catch { /* ignored *\/ }
 *
 * A bare catch is the strongest form of "silently pass through any
 * error" in the language. Distinct from the `.catch(() => null)`
 * swallow — that fires on rejected promises; this fires on synchronous
 * exceptions, typically wrapping an `await` that could also reject.
 *
 * Escape hatch: `// intentional: <why>` directly above the `catch` or
 * trailing on the `catch {` opening line.
 *
 * Companion to `@typescript-eslint/no-useless-catch` which catches the
 * `catch (e) { throw e; }` pattern (a different flavour — body non-empty
 * but useless). Both belong on at the same time.
 */

'use strict';

const { hasIntentionalJustification: sharedHasIntentional } = require('./_intentional.cjs');

/**
 * A catch block is "silent" when it contains zero AST-level statements
 * (no matter whether the source between the braces is whitespace-only,
 * comment-only, or both). `block.body.length === 0` covers all three —
 * the AST parser discards comments and whitespace into `sourceCode`,
 * not into the block body. If the body is empty, the catch clause
 * executes exactly zero user code when an exception reaches it.
 */
function isCatchBodySilent(block) {
  return !!block && block.type === 'BlockStatement' && block.body.length === 0;
}

function hasIntentionalJustification(catchClauseNode, sourceCode) {
  // Use the shared helper with the catch's empty body as the
  // accept-inside range. Common in-situ annotation shape:
  //   try { ... } catch {
  //     // intentional: <why>
  //   }
  return sharedHasIntentional(catchClauseNode, sourceCode, {
    acceptInsideRange: {
      start: catchClauseNode.body.range[0],
      end: catchClauseNode.body.range[1],
    },
  });
}

/** @type {import('eslint').Rule.RuleModule} */
module.exports = {
  meta: {
    type: 'problem',
    docs: {
      description:
        'Disallow empty / comment-only `catch` blocks in test code — either handle the error or annotate with `// intentional: <why>`.',
      recommended: true,
    },
    schema: [],
    messages: {
      bareCatch:
        'Empty `catch` block silently drops the exception. ' +
        'Either rethrow, log, or assert on the error — OR add `// intentional: <why>` ' +
        'directly above the `catch` for deliberate best-effort paths.',
    },
  },

  create(context) {
    const sourceCode = context.sourceCode || context.getSourceCode();
    return {
      CatchClause(node) {
        if (!isCatchBodySilent(node.body)) return;
        if (hasIntentionalJustification(node, sourceCode)) return;
        context.report({ node, messageId: 'bareCatch' });
      },
    };
  },
};
