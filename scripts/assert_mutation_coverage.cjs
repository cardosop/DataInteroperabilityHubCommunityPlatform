#!/usr/bin/env node
// Phase 226 PR B6 — Mutation-coverage CI gate.
//
// Enforces Principle 9 of the Phase 226 plan: every UI-driven mutation a
// spec triggers must be followed within N lines by verifyViaApi + verifyAuditEvent
// (or carry an inline `// noverify: <reason>` justification).
//
// Plain-Node .cjs (no ts-node dependency; ts-node is not in this repo's
// package.json). Exports are plain JS — pure logic lives in functions
// that the pytest harness at scripts/tests/test_assert_mutation_coverage.py
// exercises via CLI invocation.
//
// Usage:
//   node scripts/assert_mutation_coverage.cjs [--mode=warning|blocking]
//                                             [--allowlist=FILE]
//                                             [--root=DIR]
//                                             [--json]
//                                             [--update]
//                                             [--expiry-days=N]
//
// Modes (per Phase 226 OQ7 resolution — 2026-04-25):
//   - blocking (default)
//       prints findings, exits 1 if any non-allowlisted findings exist.
//       This is the hybrid model: existing untested mutations are
//       grandfathered via the allow-list with per-entry expiry; new files
//       (or expired allow-list entries) hard-block the PR. Industry pattern
//       (knip, eslint-baseline, betterer, ratchet).
//   - warning
//       prints findings, exits 0. Useful for local development / one-off
//       audits. Past-expiry allow-list entries STILL fail.
//   Past-expiry allow-list entries fail the gate in BOTH modes.
//   Malformed allow-list → exit 2.
//
// Update mode (operator workflow — generate / refresh the allow-list):
//   --update            seed the allow-list from current findings.
//   --expiry-days=N     expiry per entry (default 90). Picks a deterministic
//                       date = today + N days. Authors are still expected
//                       to drain the list before expiry.
//   --update writes the file in-place and exits 0. Re-running `--update`
//   regenerates the entire file — manual edits are not preserved (use the
//   reason field to leave context-trail).
//
// Example operator flow:
//   node scripts/assert_mutation_coverage.cjs --update
//   git add scripts/mutation_coverage_allowlist.txt
//   git commit -m "chore(e2e): refresh mutation-coverage allow-list"
//
// See also:
//   /home/ph/.claude/plans/now-pls-create-a-binary-cloud.md §Track B, PR B6
//   openspec/changes/preprod01/specs/e2e-quality-remediation/spec.md

'use strict';

const fs = require('fs');
const path = require('path');

// -------------------------------------------------------------- pure logic
// These functions are intentionally side-effect-free so they can be tested
// by feeding source strings directly. The CLI wrapper at the bottom handles
// all filesystem I/O.

// Regex for mutation detection. False-positives are tolerated (handled by
// the allow-list + `// noverify:` escape hatch); false-negatives would be
// the silent-coverage-gap this gate exists to prevent.
const PAGE_REQUEST_PATTERN =
  /page\.request\.(post|put|patch|delete)\s*\(/i;

const UI_MUTATION_PATTERN =
  /\.click\(\)|submitButton\.click|['"`]Create\s|['"`]Save\s|['"`]Delete\s|['"`]Publish\s|['"`]Activate\s|['"`]Retire\s|['"`]Submit/;

const VERIFY_HELPER_PATTERN =
  /\b(verifyViaApi|verifyAuditEvent|verifyViaApiAbsent|verifyViaApiForbidden|verifySemanticIri|verifySearchable)\b/;

const NOVERIFY_PATTERN = /\/\/\s*noverify\s*:\s*(.+)$/;

/**
 * Parse a spec source string and extract mutation sites / verification
 * helper calls / `// noverify:` comments.
 * @param {string} source
 * @returns {{mutations: Array, verifications: Array, noverifyComments: Array}}
 */
function analyzeSpec(source) {
  const lines = source.split('\n');
  const out = { mutations: [], verifications: [], noverifyComments: [] };

  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    const lineNo = i + 1;

    const prMatch = ln.match(PAGE_REQUEST_PATTERN);
    if (prMatch) {
      out.mutations.push({
        line: lineNo,
        method: prMatch[1].toUpperCase(),
        urlPathSnippet: ln.trim().slice(0, 160),
      });
    }

    if (
      !prMatch &&
      UI_MUTATION_PATTERN.test(ln) &&
      !VERIFY_HELPER_PATTERN.test(ln)
    ) {
      if (/\.click\(\)/.test(ln) || /submitButton\.click/.test(ln)) {
        out.mutations.push({
          line: lineNo,
          method: 'UI_CLICK',
          urlPathSnippet: ln.trim().slice(0, 160),
        });
      }
    }

    const vMatch = ln.match(VERIFY_HELPER_PATTERN);
    if (vMatch) {
      out.verifications.push({ line: lineNo, helper: vMatch[1] });
    }

    const nMatch = ln.match(NOVERIFY_PATTERN);
    if (nMatch) {
      out.noverifyComments.push({ line: lineNo, reason: nMatch[1].trim() });
    }
  }

  return out;
}

/**
 * Given a spec analysis, return the list of mutation sites that DO NOT
 * have both a verifyViaApi (or negative variant) AND a verifyAuditEvent
 * call within `windowLines` lines after the mutation.
 *
 * A `// noverify: <reason>` comment within the window acts as an escape
 * hatch (the mutation is considered intentionally unverified).
 *
 * @param {string} file
 * @param {{mutations, verifications, noverifyComments}} analysis
 * @param {number} [windowLines=30]
 * @returns {Array<{file,mutationLine,mutationSnippet,missing:string[]}>}
 */
// `// noverify:` comments commonly sit immediately above the mutation they
// justify — the standard "comment-then-code" pattern in TS/JS. The forward
// verification window starts at the mutation line, but noverify lookup must
// also see comments a few lines above. Three lines tolerates a multi-line
// rationale block ("// noverify: …\n// (see ADR-12)\n// for context") without
// being so generous that it accidentally suppresses unrelated nearby mutations.
const NOVERIFY_LOOKBACK_LINES = 3;

function findMutationGaps(file, analysis, windowLines = 30) {
  const findings = [];
  for (const m of analysis.mutations) {
    const windowStart = m.line;
    const windowEnd = m.line + windowLines;

    const hasNoverify = analysis.noverifyComments.some(
      (n) => n.line >= m.line - NOVERIFY_LOOKBACK_LINES && n.line <= windowEnd,
    );
    if (hasNoverify) continue;

    const helpersInWindow = analysis.verifications
      .filter((v) => v.line >= windowStart && v.line <= windowEnd)
      .map((v) => v.helper);

    const missing = [];
    if (
      !helpersInWindow.includes('verifyViaApi') &&
      !helpersInWindow.includes('verifyViaApiAbsent') &&
      !helpersInWindow.includes('verifyViaApiForbidden')
    ) {
      missing.push('verifyViaApi|verifyViaApiAbsent|verifyViaApiForbidden');
    }
    if (!helpersInWindow.includes('verifyAuditEvent')) {
      missing.push('verifyAuditEvent');
    }
    if (missing.length > 0) {
      findings.push({
        file,
        mutationLine: m.line,
        mutationSnippet: m.urlPathSnippet,
        missing,
      });
    }
  }
  return findings;
}

/**
 * Parse the allow-list file contents. Lines starting with `#` are
 * comments. Non-comment lines are `path:YYYY-MM-DD:reason`.
 *
 * @param {string} contents
 * @throws Error on malformed entry or invalid date.
 */
function parseAllowlist(contents) {
  const out = [];
  const lines = contents.split('\n');
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const firstColon = line.indexOf(':');
    const secondColon = firstColon === -1 ? -1 : line.indexOf(':', firstColon + 1);
    if (firstColon === -1 || secondColon === -1) {
      throw new Error(
        `Malformed allow-list entry (expected path:YYYY-MM-DD:reason): ${line}`,
      );
    }
    const specPath = line.slice(0, firstColon).trim();
    const expiryStr = line.slice(firstColon + 1, secondColon).trim();
    const reason = line.slice(secondColon + 1).trim();

    const expiry = new Date(`${expiryStr}T23:59:59Z`);
    if (Number.isNaN(expiry.getTime())) {
      throw new Error(`Invalid expiry date in allow-list: ${line}`);
    }
    out.push({ specPath, expiry, reason });
  }
  return out;
}

/** Look up a spec path in the allow-list + check expiry. */
function checkAllowlist(file, allowlist, now) {
  const when = now ?? new Date();
  const entry = allowlist.find((e) => file.endsWith(e.specPath));
  if (!entry) return { isAllowlisted: false, isPastExpiry: false, entry: null };
  return {
    isAllowlisted: true,
    isPastExpiry: when.getTime() > entry.expiry.getTime(),
    entry,
  };
}

// ------------------------------------------------------------ CLI wrapper

function parseArgs(argv) {
  // Default mode is `blocking` post-OQ7. To intentionally fall back to
  // warning (e.g. local audit), pass --mode=warning explicitly.
  const args = {
    mode: 'blocking',
    allowlist: 'scripts/mutation_coverage_allowlist.txt',
    root: 'frontend/e2e',
    json: false,
    update: false,
    expiryDays: 90,
  };
  for (const a of argv) {
    if (a.startsWith('--mode=')) args.mode = a.slice(7);
    else if (a.startsWith('--allowlist=')) args.allowlist = a.slice(12);
    else if (a.startsWith('--root=')) args.root = a.slice(7);
    else if (a === '--json') args.json = true;
    else if (a === '--update') args.update = true;
    else if (a.startsWith('--expiry-days=')) {
      const n = Number.parseInt(a.slice(14), 10);
      if (!Number.isFinite(n) || n <= 0) {
        process.stderr.write(`assert_mutation_coverage: --expiry-days must be a positive integer (got ${a})\n`);
        process.exit(2);
      }
      args.expiryDays = n;
    }
  }
  return args;
}

/**
 * Format a Date as YYYY-MM-DD in UTC (deterministic across CI shards).
 * Pure helper — exported for unit tests.
 */
function formatExpiryDate(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

/**
 * Build the new allow-list contents from a list of spec paths that have
 * findings. Pure: takes inputs, returns string. The CLI wrapper handles
 * file I/O. Each spec gets ONE allow-list entry (file-level, matching the
 * reader logic in `checkAllowlist`).
 *
 * @param {string[]} specPaths    repo-relative spec paths with findings
 * @param {string} expiryDateStr  YYYY-MM-DD
 * @param {string} reasonText     reason field
 * @returns {string} new allow-list file contents
 */
function buildAllowlistContents(specPaths, expiryDateStr, reasonText) {
  const header = [
    '# Phase 226 PR B6 — mutation-coverage allow-list',
    '#',
    '# Format:',
    '#   <path/relative/to/repo-root>:<YYYY-MM-DD>:<reason>',
    '#',
    '# Entries grandfather pre-existing mutation-triggering specs that do not yet',
    '# have the required verifyViaApi + verifyAuditEvent pair within 30 lines.',
    '# Each entry MUST carry an expiry date; past-expiry entries fail CI in both',
    '# warning and blocking modes.',
    '#',
    '# OQ7 (2026-04-25) flipped the gate to hybrid-blocking: this list grandfathers',
    '# the pre-existing state, new specs must verify, and per-entry expiry forces',
    '# the list to shrink over time. Regenerate with:',
    '#',
    '#   node scripts/assert_mutation_coverage.cjs --update',
    '',
  ].join('\n');

  const entries = [...specPaths].sort().map(
    (p) => `${p}:${expiryDateStr}:${reasonText}`,
  );
  return `${header}\n${entries.join('\n')}${entries.length > 0 ? '\n' : ''}`;
}

function walkSpecs(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walkSpecs(full));
    else if (entry.isFile() && full.endsWith('.spec.ts')) out.push(full);
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv.slice(2));

  let allowlist = [];
  if (fs.existsSync(args.allowlist)) {
    try {
      allowlist = parseAllowlist(fs.readFileSync(args.allowlist, 'utf8'));
    } catch (err) {
      process.stderr.write(
        `assert_mutation_coverage: failed to parse allow-list: ${err.message}\n`,
      );
      return 2;
    }
  }

  if (!fs.existsSync(args.root)) {
    process.stderr.write(`assert_mutation_coverage: root not found: ${args.root}\n`);
    return 2;
  }

  const specs = walkSpecs(args.root);
  const now = new Date();

  // --update mode: write the allow-list from current findings and exit.
  // We deliberately do NOT consult the existing allow-list here — the goal
  // is a clean snapshot of "what's actually missing right now", with a
  // fresh expiry. Reasons are collapsed to a single canonical string;
  // authors should add per-entry context via separate edits if needed.
  if (args.update) {
    const specsWithFindings = new Set();
    for (const spec of specs) {
      const source = fs.readFileSync(spec, 'utf8');
      const analysis = analyzeSpec(source);
      const findings = findMutationGaps(spec, analysis);
      if (findings.length > 0) {
        // Canonicalize to forward slashes so the file is identical on Win/Linux.
        specsWithFindings.add(spec.split(path.sep).join('/'));
      }
    }
    const expiryDate = new Date(now.getTime() + args.expiryDays * 24 * 60 * 60 * 1000);
    const expiryStr = formatExpiryDate(expiryDate);
    const contents = buildAllowlistContents(
      [...specsWithFindings],
      expiryStr,
      'grandfathered by --update; replace with verifyViaApi + verifyAuditEvent before expiry',
    );
    fs.writeFileSync(args.allowlist, contents, 'utf8');
    process.stdout.write(
      `assert_mutation_coverage: wrote ${specsWithFindings.size} entries to ${args.allowlist} (expiry ${expiryStr}).\n`,
    );
    return 0;
  }

  const allFindings = [];

  for (const spec of specs) {
    const source = fs.readFileSync(spec, 'utf8');
    const analysis = analyzeSpec(source);
    const findings = findMutationGaps(spec, analysis);
    if (findings.length === 0) continue;
    const check = checkAllowlist(spec, allowlist, now);
    for (const f of findings) {
      allFindings.push({
        ...f,
        allowlisted: check.isAllowlisted,
        pastExpiry: check.isPastExpiry,
        reason: check.entry?.reason ?? '',
      });
    }
  }

  const nonAllowed = allFindings.filter((f) => !f.allowlisted || f.pastExpiry);
  const allowedButExpired = allFindings.filter((f) => f.allowlisted && f.pastExpiry);

  if (args.json) {
    process.stdout.write(
      JSON.stringify(
        {
          total: allFindings.length,
          nonAllowed: nonAllowed.length,
          allowedButExpired: allowedButExpired.length,
          findings: allFindings,
        },
        null,
        2,
      ),
    );
    process.stdout.write('\n');
  } else {
    process.stdout.write(
      `assert_mutation_coverage: scanned ${specs.length} spec files.\n`,
    );
    if (allFindings.length === 0) {
      process.stdout.write(
        '  ✓ all mutations have verifyViaApi + verifyAuditEvent in range\n',
      );
      return 0;
    }
    process.stdout.write(
      `  ${allFindings.length} mutation site${allFindings.length === 1 ? '' : 's'} without the required verification pair.\n`,
    );
    process.stdout.write(
      `  ${nonAllowed.length} are NOT allow-listed (or have expired past the listed date).\n`,
    );
    for (const f of nonAllowed.slice(0, 50)) {
      process.stdout.write(
        `    ${f.file}:${f.mutationLine} missing=${f.missing.join('+')}${
          f.pastExpiry ? ` [EXPIRED allow-list entry: ${f.reason}]` : ''
        }\n`,
      );
    }
    if (nonAllowed.length > 50) {
      process.stdout.write(`    ... and ${nonAllowed.length - 50} more.\n`);
    }
  }

  if (args.mode === 'blocking' && nonAllowed.length > 0) return 1;
  if (allowedButExpired.length > 0) return 1;
  return 0;
}

// Exports for the pytest harness + any future consumers.
module.exports = {
  analyzeSpec,
  findMutationGaps,
  parseAllowlist,
  checkAllowlist,
  formatExpiryDate,
  buildAllowlistContents,
};

if (require.main === module) {
  process.exit(main());
}
