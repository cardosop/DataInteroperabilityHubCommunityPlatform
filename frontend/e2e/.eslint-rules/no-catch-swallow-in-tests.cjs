/**
 * ESLint rule: `e2e-guards/no-catch-swallow-in-tests`
 *
 * Covers 226.A2 (silent-failure elimination). Forbids the silent-fallback
 * pattern
 *
 *     someAsync().catch(() => null)        // or undefined / 0 / false / '' / [] / {}
 *     someAsync().catch(() => { return null; })
 *
 * — where a failed promise is silently converted to a constant, so a
 * real regression becomes a test-pass.
 *
 * Escape hatch: the author can justify a legitimate surviving use by
 * writing an `// intentional: <reason>` comment either on the line
 * directly above the `.catch(...)` call expression, OR as a trailing
 * comment on the same line as the call. This is a deliberately narrow
 * magic-string (not `eslint-disable-next-line`) so every suppression
 * shows up in grep/PR review.
 *
 * Allowed handler shapes (not flagged):
 *   - Identifier reference:         `.catch(logError)`
 *   - Arrow that throws or logs:    `.catch((e) => { throw ... })`,
 *                                   `.catch((e) => console.warn(e))`
 *   - Arrow whose body calls into a user function (dynamic):
 *                                   `.catch((e) => handleError(e))`
 *
 * Flagged shapes:
 *   - Arrow returning a falsy / empty literal:
 *                                   `.catch(() => null)`,
 *                                   `.catch(() => undefined)`,
 *                                   `.catch(() => 0)`,
 *                                   `.catch(() => false)`,
 *                                   `.catch(() => '')`,
 *                                   `.catch(() => [])`,
 *                                   `.catch(() => ({}))`
 *     …and their block-body equivalents (`{ return null; }`, etc.).
 *
 * Autofix
 * -------
 * Not provided. Each site needs a human decision:
 *   a) remove the `.catch` entirely (let the rejection fail the test), or
 *   b) add `// intentional: <why>` with a real justification.
 */

'use strict';

/**
 * Returns true if the given arrow-function node is a "constant silent
 * fallback" — its body resolves statically to one of:
 *   null | undefined | 0 | false | '' | [] | {}
 *
 * Both expression-body arrows (`() => null`) and block-body arrows
 * whose only statement is `return <constant>` are considered.
 */
function isConstantSilentFallback(arrowNode) {
  if (!arrowNode) return false;
  if (arrowNode.type !== 'ArrowFunctionExpression') return false;

  // Expression-body form: `() => <expr>`
  if (arrowNode.body.type !== 'BlockStatement') {
    return isSilentConstantExpression(arrowNode.body);
  }

  // Block-body form: `() => { ... }` — only a single `return <expr>`
  // qualifies as silent.
  const body = arrowNode.body.body;
  if (body.length !== 1) return false;
  const stmt = body[0];
  if (stmt.type !== 'ReturnStatement') return false;
  if (!stmt.argument) return true; // `return;` is undefined → silent
  return isSilentConstantExpression(stmt.argument);
}

/**
 * Is this expression a statically-resolvable silent-fallback value?
 */
function isSilentConstantExpression(expr) {
  if (!expr) return false;
  // null / 0 / false / '' / numeric / string / regex literals
  if (expr.type === 'Literal') {
    return expr.value === null || expr.value === 0 || expr.value === false || expr.value === '';
  }
  // `undefined` — represented as an Identifier in AST.
  if (expr.type === 'Identifier' && expr.name === 'undefined') {
    return true;
  }
  // []
  if (expr.type === 'ArrayExpression' && expr.elements.length === 0) {
    return true;
  }
  // {} — ObjectExpression with no properties (arrow `() => ({})` wraps in
  // parens but the AST node is still ObjectExpression).
  if (expr.type === 'ObjectExpression' && expr.properties.length === 0) {
    return true;
  }
  return false;
}

/**
 * True iff an `// intentional: …` comment sits immediately above the
 * `.catch(...)` call expression or trails on the same line.
 */
function hasIntentionalJustification(callNode, sourceCode) {
  const INTENTIONAL = /^\s*intentional\s*:/i;

  // The call-expression's statement-level ancestor is usually what
  // users put the comment above — but ESLint's `getCommentsBefore`
  // on the call node itself also captures a leading-line comment when
  // the call sits at the top of a line. We check both the call node
  // and its closest enclosing statement.
  const candidates = [callNode];
  let p = callNode.parent;
  for (let i = 0; i < 4 && p; i++, p = p.parent) {
    if (
      p.type === 'ExpressionStatement' ||
      p.type === 'VariableDeclaration' ||
      p.type === 'ReturnStatement' ||
      p.type === 'AwaitExpression'
    ) {
      candidates.push(p);
    }
  }

  for (const cand of candidates) {
    const before = sourceCode.getCommentsBefore(cand);
    if (before.length > 0) {
      const last = before[before.length - 1];
      if (
        last.loc.end.line === cand.loc.start.line - 1 &&
        INTENTIONAL.test(last.value)
      ) {
        return true;
      }
    }
  }

  // Trailing comment on the same line as the `.catch(` start.
  const allComments = sourceCode.getAllComments();
  for (const c of allComments) {
    if (
      c.loc.start.line === callNode.loc.start.line &&
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
        'Disallow `.catch(() => <falsy/empty constant>)` silent fallbacks in test code — delete the .catch to let the error surface, or annotate with `// intentional: <why>`.',
      recommended: true,
    },
    schema: [],
    messages: {
      silentFallback:
        "Silent `.catch(() => <constant>)` hides real failures as test-pass. " +
        "Remove the `.catch` so the rejection surfaces, OR if the fallback is deliberate, " +
        "add `// intentional: <why>` directly above the call.",
    },
  },

  create(context) {
    const sourceCode = context.sourceCode || context.getSourceCode();
    return {
      CallExpression(node) {
        const callee = node.callee;
        if (
          !callee ||
          callee.type !== 'MemberExpression' ||
          callee.computed ||
          callee.property.type !== 'Identifier' ||
          callee.property.name !== 'catch'
        ) {
          return;
        }
        // Must have exactly one arg (the handler).
        if (node.arguments.length !== 1) return;
        const handler = node.arguments[0];
        if (!isConstantSilentFallback(handler)) return;
        if (hasIntentionalJustification(node, sourceCode)) return;
        context.report({ node, messageId: 'silentFallback' });
      },
    };
  },
};
