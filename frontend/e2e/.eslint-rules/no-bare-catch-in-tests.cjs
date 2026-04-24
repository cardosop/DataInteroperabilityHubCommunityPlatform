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
  const INTENTIONAL = /^\s*intentional\s*:/i;
  // Preceding-line comment attached to the `catch` clause or the
  // enclosing try statement (if the comment is right before the `try`
  // it's probably about the try, not the catch — we only accept
  // comments between `}` of try and `catch`).
  const before = sourceCode.getCommentsBefore(catchClauseNode);
  if (before.length > 0) {
    const last = before[before.length - 1];
    if (
      last.loc.end.line === catchClauseNode.loc.start.line - 1 &&
      INTENTIONAL.test(last.value)
    ) {
      return true;
    }
  }

  // Trailing comment on the same line as `catch` start.
  const allComments = sourceCode.getAllComments();
  for (const c of allComments) {
    if (
      c.loc.start.line === catchClauseNode.loc.start.line &&
      INTENTIONAL.test(c.value)
    ) {
      return true;
    }
  }

  // Inside the empty block body. A catch body that holds a comment
  // starting with `intentional:` is a common, readable shape — the
  // author annotates the swallow in situ rather than above the clause.
  // Only honour this when the body is otherwise code-free (which is
  // always the case when this function is called, since we only reach
  // here for silent bodies).
  const blockStart = catchClauseNode.body.range[0];
  const blockEnd = catchClauseNode.body.range[1];
  for (const c of allComments) {
    if (
      c.range[0] > blockStart &&
      c.range[1] < blockEnd &&
      INTENTIONAL.test(c.value)
    ) {
      return true;
    }
  }
  return false;
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
