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

const { hasIntentionalJustification: sharedHasIntentional } = require('./_intentional.cjs');

/**
 * Returns true if the given handler node is a "constant silent
 * fallback" — its body resolves statically to one of:
 *   null | undefined | 0 | false | '' | [] | {}  (or `void <expr>`,
 *   which evaluates to undefined)
 *
 * Covers both ArrowFunctionExpression and FunctionExpression
 * (`.catch(function () { return null; })`), and both expression-body
 * and block-body forms whose only statement is `return <constant>`.
 */
function isConstantSilentFallback(fnNode) {
  if (!fnNode) return false;
  if (fnNode.type !== 'ArrowFunctionExpression' && fnNode.type !== 'FunctionExpression') {
    return false;
  }

  // Expression-body arrow: `() => <expr>`. FunctionExpression always
  // has a block body per JS grammar.
  if (fnNode.type === 'ArrowFunctionExpression' && fnNode.body.type !== 'BlockStatement') {
    return isSilentConstantExpression(fnNode.body);
  }

  // Block-body form: `{ ... }` — only a single `return <expr>` qualifies
  // as silent.
  const body = fnNode.body.body;
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
  // `void <anything>` — unary `void` always evaluates to undefined,
  // so `.catch(() => void 0)` or `() => void e` are silent fallbacks
  // (returning undefined) regardless of the argument.
  if (expr.type === 'UnaryExpression' && expr.operator === 'void') {
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
 *
 * Delegates the actual matching to the shared helper, BUT also walks
 * the statement-level ancestors of the call expression — a `.catch`
 * mid-chain often sits inside an `await` / variable-declaration /
 * expression-statement whose start line is what the author actually
 * placed the comment above. The shared helper's
 * `acceptInsideRange` is not used here because `.catch` calls are
 * never empty-bodied containers.
 */
function hasIntentionalJustification(callNode, sourceCode) {
  // Walk up the parent chain collecting ancestors that could legitimately
  // carry a leading `// intentional: <why>` annotation. We accept:
  //   * the call expression itself (for trailing or leading-line comments
  //     that abut the `.catch(...)` line)
  //   * any AwaitExpression / VariableDeclaration / ReturnStatement
  //     directly wrapping it (the most common shape — comment goes above
  //     `const x = await foo.catch(...)`)
  //   * the closest enclosing **statement** of ANY kind (IfStatement,
  //     ForStatement, ExpressionStatement, etc.) — handles the natural
  //     `// intentional: …  /  if (cond) await foo.catch(...)` shape
  //     where the comment licenses the entire conditional including the
  //     mid-chain swallow.
  // We bound the walk depth to keep the search cheap and prevent a
  // far-away annotation from licensing distant inner code.
  // Real statement nodes only — AwaitExpression is an expression, not a
  // statement, so it must NOT short-circuit the walk to the enclosing
  // IfStatement / ForStatement / TryStatement etc. (those are where
  // a `// intentional: …` annotation typically lives).
  const STATEMENT_TYPES = new Set([
    'ExpressionStatement',
    'VariableDeclaration',
    'ReturnStatement',
    'IfStatement',
    'ForStatement',
    'ForOfStatement',
    'ForInStatement',
    'WhileStatement',
    'DoWhileStatement',
    'TryStatement',
    'SwitchStatement',
    'BlockStatement',
    'ThrowStatement',
  ]);

  const candidates = [callNode];
  let p = callNode.parent;
  for (let i = 0; i < 8 && p; i++, p = p.parent) {
    if (
      p.type === 'ExpressionStatement' ||
      p.type === 'VariableDeclaration' ||
      p.type === 'ReturnStatement' ||
      p.type === 'AwaitExpression'
    ) {
      candidates.push(p);
    }
    // Collect every enclosing statement within the bounded walk depth.
    // Each is a place an author might legitimately put a leading
    // `// intentional: …` comment (above the `if`, above the outer
    // `try`, above the function-body's open brace, etc.). The first
    // candidate whose preceding-comment matches wins; we don't stop
    // at "first enclosing statement" because the annotation may be
    // outside the inner-most one (e.g. above an outer `try { ... }`).
    if (STATEMENT_TYPES.has(p.type)) {
      candidates.push(p);
    }
  }
  for (const cand of candidates) {
    if (sharedHasIntentional(cand, sourceCode)) return true;
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
