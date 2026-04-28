/**
 * Shared a11y audit fixture — Phase 226.F5.
 *
 * Wraps `@axe-core/playwright` with project-wide defaults (WCAG 2 AA tag
 * set, common false-positive disables) and produces a structured result
 * the spec can either expect-empty or filter further. Every audit has
 * a label so a violation message points back to a specific spec
 * location, not a generic "axe found 3 issues" line.
 *
 * Two layers:
 *
 *   - `runAxeAudit(page, label, opts?)` — the browser-side glue.
 *     Spawns an AxeBuilder, awaits results, returns the raw axe
 *     violations so callers can inspect.
 *
 *   - Pure helpers (`summarizeViolations`, `filterByImpact`) — testable
 *     in `_guards.spec.ts` without booting a browser. The browser glue
 *     delegates to these for any logic above raw network plumbing.
 *
 * Sprinkle convention (Phase 226.F5):
 *   - Audit AFTER each significant UI state change (modal open,
 *     form-validation error, toast, picker open, list-page load).
 *   - Use `expectNoSeriousViolations(audit)` for hard gates.
 *   - Use `audit.serious.length` + `console.warn` for soft signals.
 */

import type { Page } from '@playwright/test';
import { AxeBuilder } from '@axe-core/playwright';

export interface AxeViolation {
  id: string;
  impact?: 'minor' | 'moderate' | 'serious' | 'critical' | null;
  description?: string;
  help?: string;
  helpUrl?: string;
  nodes?: Array<{ html?: string; target?: unknown; failureSummary?: string }>;
}

export interface AxeAuditResult {
  /** Identifier passed in by the caller — typically the spec test name + state. */
  label: string;
  /** Total violation count returned by axe. */
  totalCount: number;
  /** Critical-impact subset (single-axis filter for spec-level gating). */
  critical: AxeViolation[];
  /** Serious-impact subset. */
  serious: AxeViolation[];
  /** Moderate / minor subset, kept for completeness but typically logged-only. */
  moderate: AxeViolation[];
  minor: AxeViolation[];
  /** All violations, untyped. Useful if the spec wants to do its own filter. */
  raw: AxeViolation[];
}

export interface AxeAuditOptions {
  /** WCAG tag set — defaults to ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']. */
  tags?: string[];
  /** Rule IDs to disable (e.g. ['color-contrast'] for a marketing page that fails by design). */
  disableRules?: string[];
  /** CSS selectors to include in the audit; default: whole document. */
  include?: string;
  /** CSS selectors to exclude (e.g. third-party iframes). */
  exclude?: string[];
}

const DEFAULT_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/**
 * Run an axe audit at the current page state. Returns a structured
 * result with critical / serious / moderate / minor buckets so the
 * caller can decide the gate strictness.
 */
export async function runAxeAudit(
  page: Page,
  label: string,
  opts: AxeAuditOptions = {},
): Promise<AxeAuditResult> {
  let builder = new AxeBuilder({ page }).withTags(opts.tags ?? DEFAULT_TAGS);
  if (opts.disableRules && opts.disableRules.length > 0) {
    builder = builder.disableRules(opts.disableRules);
  }
  if (opts.include) {
    builder = builder.include(opts.include);
  }
  if (opts.exclude) {
    for (const sel of opts.exclude) {
      builder = builder.exclude(sel);
    }
  }
  const results = await builder.analyze();
  const violations = (results.violations ?? []) as AxeViolation[];
  return {
    label,
    totalCount: violations.length,
    critical: filterByImpact(violations, 'critical'),
    serious: filterByImpact(violations, 'serious'),
    moderate: filterByImpact(violations, 'moderate'),
    minor: filterByImpact(violations, 'minor'),
    raw: violations,
  };
}

/**
 * Filter a violations array by axe impact level. Pure logic — exported
 * for unit testing in `_guards.spec.ts`.
 */
export function filterByImpact(
  violations: AxeViolation[],
  impact: 'minor' | 'moderate' | 'serious' | 'critical',
): AxeViolation[] {
  return violations.filter((v) => v.impact === impact);
}

/**
 * Format an audit result into a single human-readable string —
 * useful for `expect.fail()` messages and PR-time diagnostics.
 *
 * Pure logic — exported for unit testing.
 */
export function summarizeViolations(audit: AxeAuditResult, maxNodes = 3): string {
  if (audit.totalCount === 0) return `[a11y:${audit.label}] no violations.`;
  const lines: string[] = [
    `[a11y:${audit.label}] ${audit.totalCount} violation(s) ` +
      `(critical=${audit.critical.length} serious=${audit.serious.length} ` +
      `moderate=${audit.moderate.length} minor=${audit.minor.length})`,
  ];
  for (const v of audit.raw) {
    lines.push(
      `  - [${v.impact ?? 'unknown'}] ${v.id}: ${v.description ?? '(no description)'}`,
    );
    const nodes = v.nodes ?? [];
    for (const n of nodes.slice(0, maxNodes)) {
      const html = (n.html ?? '').slice(0, 140).replace(/\s+/g, ' ').trim();
      if (html) lines.push(`      • ${html}${(n.html ?? '').length > 140 ? '…' : ''}`);
    }
    if (nodes.length > maxNodes) {
      lines.push(`      … and ${nodes.length - maxNodes} more node(s)`);
    }
  }
  return lines.join('\n');
}

/**
 * Convenience: throw a single descriptive error if any critical OR
 * serious violation surfaced. Moderate / minor stay logged-only.
 *
 * Use as the default gate; specs that need a stricter or laxer
 * threshold should inspect `audit.raw` directly.
 */
export function expectNoSeriousViolations(audit: AxeAuditResult): void {
  if (audit.critical.length === 0 && audit.serious.length === 0) return;
  throw new Error(summarizeViolations(audit));
}
