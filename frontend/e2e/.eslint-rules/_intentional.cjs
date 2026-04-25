/**
 * Shared `// intentional: <why>` magic-string detection used by every
 * 226.A guard rule. Extracted into one module so the multi-line-block
 * walking logic stays identical across rules — three independent
 * copies drifted in the audit cycle (no-conditional-count-assertion
 * had a more permissive form than the other two), which is how
 * cross-cutting helpers always rot.
 *
 * Two acceptance shapes per call site:
 *
 *   1. **Block above the target node** — a contiguous run of `//`
 *      line-comments OR a single `/* … *\/` block-comment ending on
 *      the line directly above the node, where ANY line in that block
 *      matches `intentional:`. Contiguity is enforced by walking
 *      backward through the comment list and requiring each comment
 *      to abut the next; that prevents a far-away annotation from
 *      licensing downstream nodes.
 *
 *   2. **Trailing comment on the node's start line** — supports the
 *      shorter `something(); // intentional: <why>` shape.
 *
 * For empty-body forms (e.g. `catch {}` whose only content can be
 * a comment), pass `acceptInsideRange: { start, end }` so a comment
 * INSIDE the empty range can also satisfy the rule.
 */

'use strict';

const INTENTIONAL = /^\s*intentional\s*:/i;

/**
 * @param {object} node ESLint AST node to anchor the search at.
 * @param {object} sourceCode SourceCode instance from rule context.
 * @param {object} [options]
 * @param {{start: number, end: number}} [options.acceptInsideRange]
 *   When provided, also accept an `intentional:` comment whose entire
 *   range is strictly between `start` and `end` byte offsets.
 * @returns {boolean}
 */
function hasIntentionalJustification(node, sourceCode, options) {
  const opts = options || {};

  // Case (a) — contiguous block above the node.
  const before = sourceCode.getCommentsBefore(node);
  if (before.length > 0) {
    let prevLineExpected = node.loc.start.line - 1;
    for (let i = before.length - 1; i >= 0; i--) {
      const c = before[i];
      if (c.loc.end.line !== prevLineExpected) break;
      if (INTENTIONAL.test(c.value)) return true;
      if (c.type === 'Block') {
        // /* … */ block — magic-string can appear on any inner line.
        for (const inner of c.value.split('\n')) {
          if (INTENTIONAL.test(inner.replace(/^\s*\*\s?/, ''))) return true;
        }
      }
      prevLineExpected = c.loc.start.line - 1;
    }
  }

  const allComments = sourceCode.getAllComments();

  // Case (b) — trailing same-line comment.
  for (const c of allComments) {
    if (c.loc.start.line === node.loc.start.line && INTENTIONAL.test(c.value)) {
      return true;
    }
  }

  // Case (b'): purely positional check — a `// intentional: …` comment
  // whose END line sits exactly on the line directly above the node.
  // Needed when ESLint attaches the comment to a different AST node
  // (e.g. the comment is wedged inside a multi-line expression like
  // `const x = /* comment */ (await foo.catch(() => null));` — the
  // comment is positionally above the inner `.catch` line, but
  // `getCommentsBefore(callNode)` doesn't return it because it was
  // attached to the outer expression by the parser).
  for (const c of allComments) {
    if (c.loc.end.line === node.loc.start.line - 1) {
      if (INTENTIONAL.test(c.value)) return true;
      if (c.type === 'Block') {
        for (const inner of c.value.split('\n')) {
          if (INTENTIONAL.test(inner.replace(/^\s*\*\s?/, ''))) return true;
        }
      }
    }
  }

  // Case (c) — comment inside an empty-body range (only honoured when
  // the caller explicitly opts in by passing `acceptInsideRange`).
  if (opts.acceptInsideRange) {
    const { start, end } = opts.acceptInsideRange;
    for (const c of allComments) {
      if (c.range[0] > start && c.range[1] < end && INTENTIONAL.test(c.value)) {
        return true;
      }
    }
  }

  return false;
}

module.exports = {
  hasIntentionalJustification,
  INTENTIONAL,
};
