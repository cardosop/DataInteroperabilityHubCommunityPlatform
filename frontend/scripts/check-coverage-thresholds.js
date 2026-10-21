#!/usr/bin/env node
/**
 * 308.2 — Frontend coverage threshold check.
 *
 * Reads the Vitest coverage summary JSON and asserts that line, branch,
 * function, and statement coverage meet the configured thresholds.
 *
 * Default: 70% across all metrics.  Target after 1 quarter: 80%.
 *
 * Usage:
 *   node scripts/check-coverage-thresholds.js
 *   node scripts/check-coverage-thresholds.js --threshold 80
 *   node scripts/check-coverage-thresholds.js --coverage-file ./coverage/coverage-summary.json
 */

const fs = require("fs");
const path = require("path");

// ── Configuration ──────────────────────────────────────────────────────

const DEFAULT_THRESHOLD = 70;
const COVERAGE_FILE = path.resolve(
  process.env.COVERAGE_FILE ||
    path.join(__dirname, "..", "coverage", "coverage-summary.json")
);

// ── Parse CLI ──────────────────────────────────────────────────────────

const args = process.argv.slice(2);
let threshold = DEFAULT_THRESHOLD;
let coverageFile = COVERAGE_FILE;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--threshold" && args[i + 1]) {
    threshold = parseInt(args[i + 1], 10);
    i++;
  } else if (args[i] === "--coverage-file" && args[i + 1]) {
    coverageFile = path.resolve(args[i + 1]);
    i++;
  }
}

// ── Main ───────────────────────────────────────────────────────────────

if (!fs.existsSync(coverageFile)) {
  console.error(`Coverage file not found: ${coverageFile}`);
  console.error("Run `npm run test:coverage` first.");
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(coverageFile, "utf-8"));
const total = data.total || {};

const metrics = {
  lines: total.lines?.pct ?? 0,
  branches: total.branches?.pct ?? 0,
  functions: total.functions?.pct ?? 0,
  statements: total.statements?.pct ?? 0,
};

const failures = [];
for (const [metric, pct] of Object.entries(metrics)) {
  const pass = pct >= threshold;
  const icon = pass ? "✓" : "✗";
  console.log(`  ${icon} ${metric}: ${pct.toFixed(2)}% (threshold: ${threshold}%)`);
  if (!pass) {
    failures.push(`${metric}: ${pct.toFixed(2)}% < ${threshold}%`);
  }
}

if (failures.length > 0) {
  console.error(`\nCoverage threshold check FAILED:`);
  for (const f of failures) {
    console.error(`  - ${f}`);
  }
  console.error(`\nThreshold: ${threshold}%. Current coverage is below target.`);
  process.exit(1);
}

console.log(`\nAll coverage metrics ≥ ${threshold}%.`);
process.exit(0);
