/**
 * ESLint rule: `e2e-guards/no-conditional-count-assertion`
 *
 * Covers 226.A1 (silent-failure elimination). Forbids the
 *
 *     if ((await <x>.count()) > 0) { expect(...) }
 *
 * anti-pattern in Playwright specs. When the guard is on, a missing
 * element turns into "test passed" rather than "test noticed". The
 * spec reads as "if the feature happens to be there, we'll assert on
 * it" — which is indistinguishable from the feature disappearing.
 *
 * Per-case triage (from the task spec):
 *
 *   * Always-present UI           → drop the `if` guard, assert directly.
 *                                   This rule drives that conversion.
 *   * State-dependent presence    → hoist the condition into
 *                                   `test.skip(cond, reason)` + return;
 *                                   the skip counter gate then catches
 *                                   unexpected-skip rates.
 *   * Genuinely-optional UI       → keep the guard, but add an
 *                                   `// intentional: <reason>` comment
 *                                   directly above (or on) the `if`.
 *                                   This rule treats that comment as an
 *                                   explicit escape hatch.
 *
 * Fixed escape-hatch comment
 * --------------------------
 * Using a dedicated magic-string (`intentional:`) rather than
 * `// eslint-disable-next-line` ensures the justification is a
 * human-audit signal rather than a pure suppression — every hit is
 * greppable from a code review.
 *
 * Autofix
 * -------
 * Not provided — the right fix is context-dependent (drop guard / skip /
 * annotate). Humans pick.
 */

'use strict';

/**
 * Does `node` (an expression) contain — anywhere in its syntax tree — a
 * call expression whose callee's property name is exactly `count`?
 *
 * We look for `.count()` specifically because that's the Playwright
 * `Locator.count()` shape. The alternate `.length` on arrays is a
 * different (and often legitimate) pattern and is intentionally out of
 * scope.
 */
function containsCountCall(node) {
  if (!node || typeof node !== 'object') return false;
  if (node.type === 'CallExpression') {
    const callee = node.callee;
    if (
      callee &&
      callee.type === 'MemberExpression' &&
      callee.property &&
      callee.property.type === 'Identifier' &&
      callee.property.name === 'count' &&
      !callee.computed
    ) {
      return true;
    }
  }
  for (const key of Object.keys(node)) {
    // Skip the `parent` backref and any leading underscore metadata.
    if (key === 'parent' || key.startsWith('_')) continue;
    const child = node[key];
    if (Array.isArray(child)) {
      for (const c of child) {
        if (containsCountCall(c)) return true;
      }
    } else if (child && typeof child === 'object' && child.type) {
      if (containsCountCall(child)) return true;
    }
  }
  return false;
}

/**
 * Does the `if` test expression carry a "presence guard" shape — i.e.
 * "count is greater than zero" — versus an "absence guard" shape?
 *
 * Presence guards (flag these):
 *   count > 0          count >= 1          count !== 0         count != 0
 *
 * Absence guards (do NOT flag — they're the invariant-assertion shape,
 * which is always engineering-correct):
 *   count === 0        count == 0          count <= 0          count < 1
 *
 * Compound expressions like `(count > 0) && (something)` still count as
 * presence-guard because the `count > 0` subtree drives the pass path
 * of the `if`.
 */
function hasPresenceGuardShape(testNode) {
  if (!testNode || typeof testNode !== 'object') return false;

  if (testNode.type === 'BinaryExpression') {
    const { operator, left, right } = testNode;
    // Normalise direction so we can reason from the count() side.
    // Match both `count() > 0` and `0 < count()`.
    const leftHasCount = containsCountCall(left);
    const rightHasCount = containsCountCall(right);
    if (!leftHasCount && !rightHasCount) return false;

    const countOnLeft = leftHasCount;
    const other = countOnLeft ? right : left;

    // Only numeric-literal comparisons carry a fixed shape we can
    // classify. Dynamic comparisons (e.g. `count > threshold`) are
    // ambiguous; treat them as presence-guards conservatively because
    // the common-case threshold is >= 1.
    const otherVal = other && other.type === 'Literal' ? other.value : null;

    if (countOnLeft) {
      // left-hand-side: `count() <op> <rhs>`
      if (operator === '>' && otherVal === 0) return true;
      if (operator === '>=' && typeof otherVal === 'number' && otherVal >= 1) return true;
      if ((operator === '!==' || operator === '!=') && otherVal === 0) return true;
      if (typeof otherVal !== 'number') return true;
      return false;
    } else {
      // right-hand-side form: `<lhs> <op> count()`
      if (operator === '<' && otherVal === 0) return true;
      if (operator === '<=' && typeof otherVal === 'number' && otherVal <= -1) return true;
      if ((operator === '!==' || operator === '!=') && otherVal === 0) return true;
      if (typeof otherVal !== 'number') return true;
      return false;
    }
  }

  if (testNode.type === 'LogicalExpression') {
    // `(count > 0) && other` or `other && (count > 0)` — either subtree
    // can be the presence-guard that drives the if's pass path. We are
    // conservative: if ANY subtree is a presence-guard, flag.
    return hasPresenceGuardShape(testNode.left) || hasPresenceGuardShape(testNode.right);
  }

  if (testNode.type === 'AwaitExpression') {
    return hasPresenceGuardShape(testNode.argument);
  }

  // Standalone `if (await x.count())` — truthy check. Treat as
  // presence-guard (count > 0 equivalent in JS).
  if (containsCountCall(testNode)) {
    return true;
  }

  return false;
}

/**
 * True when `node` (a block / expression) contains an `expect(...)`
 * call anywhere in its subtree.
 */
function containsExpectCall(node) {
  if (!node || typeof node !== 'object') return false;
  if (node.type === 'CallExpression') {
    const callee = node.callee;
    // Matches `expect(x)` and `expect(x).toXYZ(...)` (the latter is a
    // member expression whose object is the expect call — still has an
    // `expect` Identifier we can find by recursion).
    if (callee && callee.type === 'Identifier' && callee.name === 'expect') {
      return true;
    }
  }
  for (const key of Object.keys(node)) {
    if (key === 'parent' || key.startsWith('_')) continue;
    const child = node[key];
    if (Array.isArray(child)) {
      for (const c of child) {
        if (containsExpectCall(c)) return true;
      }
    } else if (child && typeof child === 'object' && child.type) {
      if (containsExpectCall(child)) return true;
    }
  }
  return false;
}

/**
 * True iff there's an `// intentional: <anything>` (case-insensitive,
 * whitespace-forgiving) comment either
 *   a) on the line directly preceding the `if` statement, or
 *   b) on the same line as the `if`'s block-open brace (trailing comment).
 *
 * We scope strictly so a far-away `// intentional:` doesn't accidentally
 * license every `if` below it.
 */
function hasIntentionalJustification(node, sourceCode) {
  const INTENTIONAL = /^\s*intentional\s*:/i;

  // Case (a): leading comment on the line directly above.
  const before = sourceCode.getCommentsBefore(node);
  if (before.length > 0) {
    const last = before[before.length - 1];
    if (
      last.loc.end.line === node.loc.start.line - 1 &&
      INTENTIONAL.test(last.value)
    ) {
      return true;
    }
  }

  // Case (b): trailing comment on the same line as the `if`.
  // `getComments` is ESLint 8+ -preserved API via SourceCode; but the
  // cross-version-safe approach is to scan all comments in the file
  // once and match line numbers.
  const allComments = sourceCode.getAllComments();
  for (const c of allComments) {
    if (c.loc.start.line === node.loc.start.line && INTENTIONAL.test(c.value)) {
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
        'Disallow `if (count() > 0) { expect(...) }` — use `test.skip` for state-dependent paths, drop the guard for always-present UI, or annotate with `// intentional: <why>` for genuinely-optional UI.',
      recommended: true,
    },
    schema: [],
    messages: {
      conditionalCountExpect:
        'Conditional `expect(...)` inside an `if (count() > 0)` guard hides missing UI as test-pass. ' +
        'Fix: drop the guard if the element is always present, convert to `test.skip(cond, reason)` ' +
        'if state-dependent, or annotate with `// intentional: <why>` above the `if` when the UI is ' +
        'genuinely optional.',
    },
  },

  create(context) {
    const sourceCode = context.sourceCode || context.getSourceCode();
    return {
      IfStatement(node) {
        if (!containsCountCall(node.test)) return;
        // Only flag presence-guarded shapes (`count > 0` / `>= 1` / `!== 0` /
        // truthy). Absence-guarded shapes (`count === 0`, `count <= 0`) are
        // the invariant-assertion pattern and are always correct.
        if (!hasPresenceGuardShape(node.test)) return;
        // Only flag `if` guards whose body exercises `expect`.
        if (!containsExpectCall(node.consequent)) return;
        if (hasIntentionalJustification(node, sourceCode)) return;
        context.report({ node, messageId: 'conditionalCountExpect' });
      },
    };
  },
};
