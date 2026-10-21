/**
 * Self-test for the `no-conditional-count-assertion` rule.
 *
 * Covers 226.A1 — convert the `if ((await x.count()) > 0) { expect(...) }`
 * pattern to one of:
 *   - always-present UI → drop the `if` guard (rule catches this)
 *   - state-dependent presence → `test.skip(cond, reason)` + `return`
 *   - genuinely-optional UI → keep, annotate with `// intentional: <why>`
 *     comment which the rule respects as an escape hatch.
 *
 * Runs with ESLint's built-in RuleTester — no extra deps.
 */

'use strict';

const { RuleTester } = require('eslint');
const rule = require('./no-conditional-count-assertion.cjs');

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
});

ruleTester.run('no-conditional-count-assertion', rule, {
  valid: [
    // Unconditional expect — the canonical shape we want.
    {
      code: `async function t() {
        await expect(page.locator('.foo')).toBeVisible();
      }`,
    },
    // Conditional skip is the alternate form the rule nudges people toward.
    {
      code: `async function t() {
        const count = await page.locator('.foo').count();
        test.skip(count === 0, 'feature disabled in this tenant');
        await expect(page.locator('.foo').first()).toBeVisible();
      }`,
    },
    // `if (count > 0)` without an expect inside — loop logic, iteration, etc.
    // Not what the rule targets.
    {
      code: `async function t() {
        const rows = page.locator('.row');
        if ((await rows.count()) > 0) {
          await rows.first().click();
        }
      }`,
    },
    // Escape hatch: author justifies with \`// intentional:\` comment on the
    // same or preceding line. This covers genuinely-optional UI.
    {
      code: `async function t() {
        // intentional: banner only renders for beta tenants
        if ((await banner.count()) > 0) {
          await expect(banner).toContainText('Beta');
        }
      }`,
    },
    {
      // Alternate placement on the if line itself.
      code: `async function t() {
        if ((await banner.count()) > 0) { // intentional: optional help text
          await expect(banner).toBeVisible();
        }
      }`,
    },
    // Multi-line `// intentional:` block above the if — the magic-string
    // is on the FIRST line of the block; the LAST line is continuation
    // prose. The shared helper walks the whole contiguous block.
    {
      code: `async function t() {
        // intentional: first dataset row is genuinely optional — the test
        // runs against shared staging where dataset presence varies per
        // tenant. A missing row is a legitimate empty-list signal.
        if ((await firstDataset.count()) > 0) {
          await expect(firstDataset).toBeVisible();
        }
      }`,
    },
    // /* … */ block-comment with intentional on an inner line.
    {
      code: `async function t() {
        /*
         * intentional: optional pagination control
         * (only renders when the list overflows a single page)
         */
        if ((await pager.count()) > 0) {
          await expect(pager).toBeVisible();
        }
      }`,
    },
    // .length check (not .count()) — out of scope for this rule.
    {
      code: `function t() {
        if (arr.length > 0) { expect(arr[0]).toBe(1); }
      }`,
    },
    // Loop iteration — `while (count > 0)` walks rows and is NOT an
    // assertion-guard. Must not be flagged even though both count() and
    // expect() appear nearby.
    {
      code: `async function t() {
        while ((await rows.count()) > 0) {
          await rows.first().click();
        }
        await expect(page.locator('.done')).toBeVisible();
      }`,
    },
    // For-loop over a count() value — same category (iteration).
    {
      code: `async function t() {
        const n = await rows.count();
        for (let i = 0; i < n; i++) {
          await rows.nth(i).click();
        }
      }`,
    },
    // Inverted form: `if (count === 0)` is "assert absence" — the
    // opposite of the silent-skip anti-pattern. Legitimate usage.
    {
      code: `async function t() {
        if ((await banner.count()) === 0) {
          await expect(page.locator('.no-banner-state')).toBeVisible();
        }
      }`,
    },
    // `count <= 0` — also an absence guard. Must not flag.
    {
      code: `async function t() {
        if ((await banner.count()) <= 0) {
          await expect(emptyState).toBeVisible();
        }
      }`,
    },
    // `0 === count()` — flipped operand order, still absence. Not flagged.
    {
      code: `async function t() {
        if (0 === (await banner.count())) {
          await expect(emptyState).toBeVisible();
        }
      }`,
    },
  ],
  invalid: [
    // The canonical bug: guard + expect, no justification.
    {
      code: `async function t() {
        if ((await page.locator('.foo').count()) > 0) {
          await expect(page.locator('.foo')).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Non-parenthesised form still matches.
    {
      code: `async function t() {
        if (await page.locator('.foo').count() > 0) {
          await expect(page.locator('.foo')).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Non-zero comparison (>= 1, !== 0, etc.) — still the same pattern.
    {
      code: `async function t() {
        if ((await foo.count()) >= 1) {
          await expect(foo).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Expect nested inside an await, chained, still flagged.
    {
      code: `async function t() {
        if ((await page.locator('.foo').count()) > 0) {
          const text = await page.locator('.foo').textContent();
          expect(text).toContain('hi');
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Comment that isn't the `intentional:` escape hatch — still flagged.
    {
      code: `async function t() {
        // TODO: figure out why this is conditional
        if ((await banner.count()) > 0) {
          await expect(banner).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Flipped operand order for presence guard: `0 < count()`.
    {
      code: `async function t() {
        if (0 < (await banner.count())) {
          await expect(banner).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Truthy test (no comparison operator) — also a presence guard in JS
    // semantics because `0` is falsy.
    {
      code: `async function t() {
        if (await banner.count()) {
          await expect(banner).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
    // Compound `&& other-check` — the count > 0 branch still drives the
    // presence-guarded pass path.
    {
      code: `async function t() {
        if ((await banner.count()) > 0 && ready) {
          await expect(banner).toBeVisible();
        }
      }`,
      errors: [{ messageId: 'conditionalCountExpect' }],
    },
  ],
});

console.log('no-conditional-count-assertion: all rule cases passed');
