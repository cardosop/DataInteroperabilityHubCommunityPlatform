#!/usr/bin/env node
/**
 * Phase 250.6.F.1 — TDD spec for ``check-i18n-hardcoded.cjs``.
 *
 * Uses Node's built-in test runner (``node:test``) so the test
 * stays runnable without adding Jest / Vitest deps to the .cjs
 * tooling layer. Run via:
 *
 *     node --test frontend/scripts/check-i18n-hardcoded.test.cjs
 *
 * Each test feeds a known-violation OR known-clean snippet to the
 * detector's pure ``scanSource(source, filePath)`` function and
 * asserts the violation list. Fixtures live inline so the test
 * is self-describing — the canonical input + expected output sit
 * next to each other.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');

const { scanSource } = require('./check-i18n-hardcoded.cjs');


// ---------------------------------------------------------------------------
// Positive cases — the detector MUST flag these.
// ---------------------------------------------------------------------------

test('flags JSX text content that is a literal string', () => {
  const src = `
    function X() { return <h2>Welcome to Meshant</h2>; }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.equal(violations.length, 1);
  assert.match(violations[0].text, /Welcome to Meshant/);
  assert.equal(violations[0].kind, 'jsx-text');
});

test('flags multi-line JSX text content', () => {
  const src = `
    function X() {
      return (
        <p>
          Some literal copy spread across multiple lines.
        </p>
      );
    }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.equal(violations.length, 1);
  assert.match(violations[0].text, /literal copy/);
});

test('flags string literals in user-facing aria-label attribute', () => {
  const src = `
    function X() { return <button aria-label="Close modal">X</button>; }
  `;
  const violations = scanSource(src, 'X.tsx');
  // Two violations: the aria-label literal AND the JSX text "X".
  // Our detector is allowed to flag both — but we test for the
  // aria-label specifically here.
  const ariaViolation = violations.find((v) => v.kind === 'attribute');
  assert.ok(ariaViolation, 'aria-label literal MUST be flagged');
  assert.equal(ariaViolation.attribute, 'aria-label');
  assert.match(ariaViolation.text, /Close modal/);
});

test('flags string literals in placeholder attribute', () => {
  const src = `
    function X() { return <input placeholder="Search assets..." />; }
  `;
  const violations = scanSource(src, 'X.tsx');
  const placeholder = violations.find((v) => v.kind === 'attribute');
  assert.ok(placeholder);
  assert.equal(placeholder.attribute, 'placeholder');
});

test('flags string literals in title attribute', () => {
  const src = `
    function X() { return <button title="Save changes">Save</button>; }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.ok(violations.some((v) => v.kind === 'attribute' && v.attribute === 'title'));
});

test('flags string literals in alt attribute', () => {
  const src = `
    function X() { return <img src={x} alt="Hero illustration" />; }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.ok(violations.some((v) => v.kind === 'attribute' && v.attribute === 'alt'));
});


// ---------------------------------------------------------------------------
// Negative cases — the detector MUST NOT flag these.
// ---------------------------------------------------------------------------

test('does NOT flag t() calls in JSX text', () => {
  const src = `
    function X() { return <h2>{t('greetings.hello')}</h2>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag variable expressions in JSX text', () => {
  const src = `
    function X({ name }) { return <h2>{name}</h2>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag t() in user-facing attributes', () => {
  const src = `
    function X() { return <button aria-label={t('close.label')}>X</button>; }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.equal(violations.filter((v) => v.kind === 'attribute').length, 0);
});

test('does NOT flag non-user-facing attributes', () => {
  // className, id, data-testid, role, href, src, type, name etc. are
  // structural — they're not user-visible copy and should never be
  // wrapped in t(). The detector must whitelist these.
  const src = `
    function X() {
      return (
        <button
          className="primary-btn"
          id="submit-btn"
          data-testid="submit"
          data-kind="data"
          role="button"
          type="submit"
          name="submit"
        >{t('submit.label')}</button>
      );
    }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.equal(violations.filter((v) => v.kind === 'attribute').length, 0);
});

test('does NOT flag empty / whitespace-only JSX text', () => {
  const src = `
    function X() {
      return (
        <div>
          {' '}
          <span>{t('a')}</span>
          {' '}
          <span>{t('b')}</span>
        </div>
      );
    }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag punctuation-only JSX text expressions', () => {
  const src = `
    function X() { return <span>{':'}</span>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag string literals in className', () => {
  const src = `
    function X() { return <div className="my-class with-modifier">{t('a')}</div>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag content inside i18n-ignore comment scope', () => {
  // Contract: a single-line comment ``// i18n-ignore`` immediately
  // BEFORE the JSX silences hardcoded-string detection for the
  // following expression (used for legitimate edge cases like
  // brand names or programmatic identifiers that aren't translatable).
  const src = `
    function X() {
      // i18n-ignore — brand name; copyright says it's untranslatable
      return <h2>Meshant</h2>;
    }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag JSX text containing only digits', () => {
  const src = `
    function X({ count }) { return <span>{count}</span>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag .ts / non-JSX files', () => {
  const src = `
    export const greeting = "Hello world";
    export function f() { return "literal"; }
  `;
  // .ts files don't contain JSX, so the detector returns []. We
  // pin this to make sure non-JSX files don't get false-positives.
  assert.deepEqual(scanSource(src, 'helpers.ts'), []);
});


// ---------------------------------------------------------------------------
// Edge cases — corners that distinguish a sloppy detector from a sharp one.
// ---------------------------------------------------------------------------

test('does NOT flag short symbolic strings in JSX text (×, ✓, →)', () => {
  // Decorative symbols carry no translatable meaning. The detector
  // treats them as non-text.
  const src = `
    function X() { return <span>×</span>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('flags long-enough text content even when adjacent to children', () => {
  const src = `
    function X() {
      return (
        <div>
          Static literal copy
          <Button>{t('a')}</Button>
        </div>
      );
    }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.equal(violations.length, 1);
  assert.match(violations[0].text, /Static literal copy/);
});

test('does NOT flag .test.tsx files (test fixtures often contain inline strings)', () => {
  const src = `
    test('renders', () => {
      render(<h2>Inline test fixture</h2>);
    });
  `;
  assert.deepEqual(scanSource(src, 'X.test.tsx'), []);
});

test('does NOT flag .stories.tsx files (Storybook args use literal copy)', () => {
  const src = `
    export const Default = { args: { label: 'Click me' } };
    export const X = () => <h2>Storybook fixture</h2>;
  `;
  assert.deepEqual(scanSource(src, 'X.stories.tsx'), []);
});

test('does NOT flag TypeScript-generic syntax across lines (regression)', () => {
  // 250.6.F.1 audit-pass — the original regex ``/>([^<>{}]*?)</g``
  // matched the ``>`` of ``useState<string>`` followed by a
  // multi-line span of JS code, then the ``<`` of a later JSX
  // element — flagging real source files with false positives.
  // The exclusion set widened to ``[^<>{};=()\\[\\]]`` so JS
  // syntax (``;``, ``=``, parens, brackets) terminates the match
  // and TypeScript generics no longer masquerade as JSX text.
  const src = `
    function X() {
      const [createdAssetId, setCreatedAssetId] = useState<string | null>(null);
      // also bad UX
      return <h2>{t('assets.create.heading')}</h2>;
    }
  `;
  const violations = scanSource(src, 'X.tsx');
  assert.deepEqual(
    violations,
    [],
    'TS generic + JSX combination must not produce a false positive',
  );
});

test('does NOT flag JSX-shaped patterns inside comments (regression)', () => {
  // 250.6.F.1 audit-pass — code comments frequently contain
  // JSX-shaped examples (``// like <div role="radio">``). The
  // detector must skip matches whose ``>`` is inside a comment
  // range; otherwise documentation comments produce false
  // positives indistinguishable from real JSX.
  const src = `
    function X() {
      // Native <button> already triggers click on Enter+Space
      // useful if someone later switches to a <div role="radio"> shape
      return <button>{t('a')}</button>;
    }
  `;
  assert.deepEqual(
    scanSource(src, 'X.tsx'),
    [],
    'JSX-shaped comment content must not produce a false positive',
  );
});

test('does NOT flag JSX-shaped patterns inside block comments', () => {
  const src = `
    function X() {
      /* Example: <h2>{t('greetings.hello')}</h2> renders the heading. */
      return <h2>{t('greetings.hello')}</h2>;
    }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag user-facing attribute literals inside comments', () => {
  // The block-or-line-comment guard also covers attribute
  // matches: a ``// aria-label="example"`` line in a comment
  // mustn't be flagged.
  const src = `
    function X() {
      // aria-label="example" is the legacy a11y pattern
      return <button aria-label={t('close')}>X</button>;
    }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});

test('does NOT flag TypeScript-generic syntax in module-level code', () => {
  // Variants of the previous case to harden the regex against
  // common TS-generic patterns.
  const src = `
    type Foo = Map<string, number>;
    type Bar = Array<{a: string}>;
    const m = new Map<string, number>();
    function X() { return <span>{t('a')}</span>; }
  `;
  assert.deepEqual(scanSource(src, 'X.tsx'), []);
});
