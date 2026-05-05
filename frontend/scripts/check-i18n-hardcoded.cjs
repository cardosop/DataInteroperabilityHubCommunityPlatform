#!/usr/bin/env node
/**
 * Phase 250.6.F.1 — Hard-coded user-facing string detector.
 *
 *     # Scan a list of files (CI usage — passes diff'd files).
 *     node frontend/scripts/check-i18n-hardcoded.cjs path/a.tsx path/b.tsx
 *
 *     # Scan everything under src/ (developer pre-commit usage).
 *     node frontend/scripts/check-i18n-hardcoded.cjs --all
 *
 * Companion to ``check-i18n-keys.cjs`` which only verifies that
 * keys-used-in-t-calls exist in the locale catalog. THIS detector
 * complements that by catching the OTHER end of the gap: text
 * content + user-facing attributes that should have been wrapped
 * in ``t(...)`` but weren't.
 *
 * Detection rules
 * ---------------
 * Flagged:
 *
 *   1. JSX text content that is a literal string with letters
 *      (e.g. ``<h2>Welcome</h2>``).
 *   2. String-literal values in user-facing JSX attributes:
 *      ``aria-label``, ``title``, ``alt``, ``placeholder``.
 *
 * NOT flagged:
 *
 *   * ``t('key', 'fallback')`` calls inside ``{...}`` expressions.
 *   * Variable expressions like ``{name}`` or ``{count}`` (the
 *      detector can't statically prove these are non-text, but
 *      the convention is that translatable copy MUST go through
 *      ``t(...)``).
 *   * Whitespace-only / punctuation-only / digit-only content.
 *   * Decorative symbols (×, ✓, →, …) — short non-letter strings.
 *   * className / id / data-* / role / type / name / href / src /
 *      key / for / htmlFor / etc. — structural attributes that
 *      are NEVER user-facing copy.
 *   * Files whose path matches the ``EXCLUDED_PATH_PATTERNS``
 *      list (.test.tsx, .stories.tsx, .d.ts, locales/).
 *   * Lines preceded by a ``// i18n-ignore`` comment (legitimate
 *      brand-name / programmatic-identifier escapes).
 *
 * Why a custom regex parser vs a real AST tool (babel/typescript-
 * estree): the existing i18n catalog check uses the same regex
 * approach, and the detector only needs three heuristics. Pulling
 * in babel-parser would balloon the .cjs tooling layer's
 * dependency surface for marginal accuracy gain.
 */
const fs = require('fs');
const path = require('path');


/** Path patterns that bypass the detector entirely. */
const EXCLUDED_PATH_PATTERNS = [
  /\.test\.tsx?$/,
  /\.stories\.tsx?$/,
  /\.d\.ts$/,
  /\/locales\//,
  /\/i18n\//,
  // Type-only files (no runtime code, no JSX).
  /\/types\//,
  // Build / generated files.
  /\/dist\//,
  /\/node_modules\//,
];


/** User-facing attributes that MUST be wrapped in ``t(...)`` when string-literal. */
const USER_FACING_ATTRIBUTES = new Set([
  'aria-label',
  'aria-description',
  'aria-placeholder',
  'aria-roledescription',
  'aria-valuetext',
  'title',
  'alt',
  'placeholder',
]);


/** Heuristic: is the text translatable? */
function _isTranslatable(text) {
  if (!text) return false;
  const trimmed = text.trim();
  if (!trimmed) return false;
  // Must contain at least one ASCII letter — pure punctuation /
  // digits / whitespace / single decorative symbol is not
  // user-facing translatable copy.
  if (!/[a-zA-Z]/.test(trimmed)) return false;
  // Drop very short strings (single-letter / 2-char codes like
  // "OK" sneak through, but the noise/value tradeoff is OK at
  // this length — we'd rather not produce false positives on
  // ``<X>{':'}</X>`` style content. Translatable copy is
  // virtually always at least 3 characters.)
  if (trimmed.length < 3) return false;
  return true;
}


/** Strip line / block comments out of a source string. */
function _stripComments(source) {
  // Remove block comments first (greedy across newlines).
  let out = source.replace(/\/\*[\s\S]*?\*\//g, '');
  // Then line comments (per-line; preserve newlines).
  out = out.replace(/\/\/[^\n]*/g, '');
  return out;
}


/** Find every comment range in the source. Returns ``[{start, end}]`` offsets.
 *
 * Used by the detector to skip matches whose ``>`` is inside a
 * comment. Without this, code comments containing JSX-shaped
 * examples (e.g. ``// like <button>X</button> for accessibility``)
 * would produce false positives — the regex sees the ``>`` and
 * ``<`` and treats the surrounding text as JSX content.
 */
function _findCommentRanges(source) {
  const ranges = [];
  // Block comments first.
  const blockRe = /\/\*[\s\S]*?\*\//g;
  let bm;
  while ((bm = blockRe.exec(source)) !== null) {
    ranges.push({ start: bm.index, end: bm.index + bm[0].length });
  }
  // Line comments — match ``//`` to end-of-line.
  const lineRe = /\/\/[^\n]*/g;
  let lm;
  while ((lm = lineRe.exec(source)) !== null) {
    // Don't double-count ``//`` patterns that fall inside an
    // already-recorded block comment.
    const inside = ranges.some(
      (r) => lm.index >= r.start && lm.index < r.end,
    );
    if (!inside) {
      ranges.push({ start: lm.index, end: lm.index + lm[0].length });
    }
  }
  return ranges;
}


function _isOffsetInRange(offset, ranges) {
  for (const r of ranges) {
    if (offset >= r.start && offset <= r.end) return true;
  }
  return false;
}


/** Lines preceded by ``// i18n-ignore`` — record their start positions. */
function _findIgnoredOffsets(source) {
  const ignored = [];
  // Pattern: line containing ``// i18n-ignore`` (anywhere in the
  // comment), then capture the offset of the start of the NEXT
  // non-blank line (the JSX expression that's being ignored).
  const re = /\/\/\s*i18n-ignore[^\n]*\n/g;
  let m;
  while ((m = re.exec(source)) !== null) {
    // The IGNORED span starts at the position right after the
    // i18n-ignore comment line and extends to either the next
    // closing ``}`` of the JSX expression OR to the next blank
    // line — whichever comes first. We approximate with "next
    // 500 chars" which covers the common cases without an AST.
    const startOfNextLine = m.index + m[0].length;
    ignored.push({ start: startOfNextLine, end: startOfNextLine + 500 });
  }
  return ignored;
}


function _isOffsetIgnored(offset, ignoredRanges) {
  for (const range of ignoredRanges) {
    if (offset >= range.start && offset <= range.end) return true;
  }
  return false;
}


/**
 * Pure detector — scans a single source string for hardcoded user-facing
 * literals. Exported for unit-test purposes.
 *
 * Returns an array of violation objects, each shaped:
 *
 *     {
 *       kind: 'jsx-text' | 'attribute',
 *       text: <the literal string that was flagged>,
 *       attribute?: <attribute name when kind=='attribute'>,
 *       line: <1-indexed line number in the source>
 *     }
 */
function scanSource(source, filePath) {
  // Excluded path → no scan.
  if (EXCLUDED_PATH_PATTERNS.some((re) => re.test(filePath))) {
    return [];
  }
  // Non-JSX files — heuristic: only .tsx / .jsx files contain JSX.
  if (!/\.(tsx|jsx)$/.test(filePath)) {
    return [];
  }

  const violations = [];
  const ignoredRanges = _findIgnoredOffsets(source);
  const commentRanges = _findCommentRanges(source);
  // We don't STRIP comments — that would invalidate the
  // ``i18n-ignore`` offset table. Instead we track comment
  // ranges and skip matches whose ``>`` is inside one. Comment
  // content frequently contains JSX-shaped examples (e.g.
  // ``// switches to a <div role="radio">``); without this
  // guard those produce false positives.
  const stripped = source;

  // ---- Rule 1 — JSX text content between tags ----
  //
  // Match ``>TEXT<`` where TEXT contains at least one letter and
  // doesn't start with ``{`` (a {expression}).
  //
  // The exclusion set ``[^<>{};=()\[\]]`` widens what we DON'T
  // accept inside TEXT — beyond the structural ``<>{}`` we add
  // ``;``, ``=``, parens and brackets. Reason: TypeScript generic
  // syntax (``useState<string>(null);``) produces a ``>...<``
  // pattern that spans multiple lines of code; without these
  // exclusions every ``useState<X>`` followed by a later
  // ``<Component>`` would be flagged as hardcoded JSX text. None
  // of those characters appear in normal user-facing JSX copy
  // (an exclamation point or apostrophe in copy is fine; ``;``
  // and ``=`` strongly imply we're inside JS code, not JSX
  // text). The tradeoff is: copy with embedded ``=`` or ``;``
  // (rare — usually programmatic/code-snippet copy that should
  // be ``<code>...</code>`` anyway) gets a false negative, which
  // is acceptable.
  const jsxTextRe = />([^<>{};=()\[\]]*?)</g;
  let textMatch;
  while ((textMatch = jsxTextRe.exec(stripped)) !== null) {
    const raw = textMatch[1];
    if (!_isTranslatable(raw)) continue;
    if (_isOffsetIgnored(textMatch.index, ignoredRanges)) continue;
    if (_isOffsetInRange(textMatch.index, commentRanges)) continue;
    const line = (stripped.slice(0, textMatch.index).match(/\n/g) || []).length + 1;
    violations.push({
      kind: 'jsx-text',
      text: raw.trim(),
      line,
    });
  }

  // ---- Rule 2 — user-facing JSX attribute string literals ----
  //
  // Match ``ATTR="VALUE"`` or ``ATTR='VALUE'`` where ATTR is one
  // of the user-facing attributes. We skip ``ATTR={...}`` (an
  // expression, presumed to be a t() call or computed value) by
  // requiring the value to start with a quote. The pattern uses
  // a non-greedy capture so multi-attribute lines split correctly.
  for (const attr of USER_FACING_ATTRIBUTES) {
    const escaped = attr.replace(/-/g, '\\-');
    const re = new RegExp(`\\b${escaped}\\s*=\\s*("([^"]*?)"|'([^']*?)')`, 'g');
    let attrMatch;
    while ((attrMatch = re.exec(stripped)) !== null) {
      const value = attrMatch[2] !== undefined ? attrMatch[2] : attrMatch[3];
      if (!_isTranslatable(value)) continue;
      if (_isOffsetIgnored(attrMatch.index, ignoredRanges)) continue;
      if (_isOffsetInRange(attrMatch.index, commentRanges)) continue;
      const line = (stripped.slice(0, attrMatch.index).match(/\n/g) || []).length + 1;
      violations.push({
        kind: 'attribute',
        attribute: attr,
        text: value,
        line,
      });
    }
  }

  return violations;
}


function _walk(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue;
      _walk(p, files);
    } else if (/\.(ts|tsx|jsx)$/.test(entry.name)) {
      files.push(p);
    }
  }
  return files;
}


function _printViolations(file, violations) {
  for (const v of violations) {
    if (v.kind === 'jsx-text') {
      console.error(
        `${file}:${v.line}: hardcoded JSX text — "${v.text}" (wrap in t('...'))`,
      );
    } else {
      console.error(
        `${file}:${v.line}: hardcoded ${v.attribute}="${v.text}" (wrap in t('...'))`,
      );
    }
  }
}


function main() {
  const args = process.argv.slice(2);
  const all = args.includes('--all');
  const explicitPaths = args.filter((a) => !a.startsWith('--'));

  const ROOT = path.resolve(__dirname, '..');
  const SRC_DIR = path.join(ROOT, 'src');

  let files;
  if (all) {
    files = _walk(SRC_DIR);
  } else if (explicitPaths.length > 0) {
    files = explicitPaths.map((p) => (path.isAbsolute(p) ? p : path.join(ROOT, p)));
  } else {
    console.error(
      'check-i18n-hardcoded: pass file paths OR --all (no scan target given)',
    );
    process.exit(2);
  }

  let totalViolations = 0;
  for (const f of files) {
    if (!fs.existsSync(f) || !fs.statSync(f).isFile()) continue;
    const source = fs.readFileSync(f, 'utf8');
    const violations = scanSource(source, f);
    if (violations.length > 0) {
      _printViolations(path.relative(ROOT, f), violations);
      totalViolations += violations.length;
    }
  }

  if (totalViolations > 0) {
    console.error(
      `\ncheck-i18n-hardcoded: ${totalViolations} hardcoded ` +
        `user-facing string(s) found across ${files.length} scanned file(s).`,
    );
    console.error(
      "Wrap each in `t('<key>')` and add the key to " +
        '`frontend/src/shared/i18n/locales/en.ts`. To explicitly ' +
        'exempt a non-translatable literal, prefix the line with ' +
        '`// i18n-ignore`.',
    );
    process.exit(1);
  }

  console.log(
    `check-i18n-hardcoded: 0 violations across ${files.length} file(s).`,
  );
}


// CLI entry — only when invoked directly. Importing for tests
// must not run main().
if (require.main === module) {
  main();
}


module.exports = {
  scanSource,
  EXCLUDED_PATH_PATTERNS,
  USER_FACING_ATTRIBUTES,
};
