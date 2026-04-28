/**
 * Phase 226 PR C2 — Flake-annotation reporter.
 *
 * Emits one GitHub Workflow Command (`::warning ...`) per test that PASSED on
 * retry. CI surfaces these as PR-level annotations (an underline on the
 * offending line in the GitHub diff), so a flaky test is impossible to miss
 * even on a green run.
 *
 * Why a reporter (not a `test.afterEach` hook)?
 * - `result.retry > 0` is only known at result-aggregation time; afterEach
 *   runs per-attempt and cannot see the retry count.
 * - Reporters get the file/line of the test definition (clickable in GH)
 *   without needing the test author to thread `__filename` through.
 *
 * The pure logic — `shouldEmitFlakeAnnotation`, `summarizeFlakyError`,
 * `formatGitHubFlakeAnnotation` — is exported so it can be unit-tested
 * without booting Playwright. The Reporter class is the thin I/O layer.
 *
 * Wired in `playwright.config.ts` as the third reporter entry. CI sets
 * `GITHUB_ACTIONS=true`; the reporter still emits in non-CI but with
 * `[FLAKE]` prefixed instead (so local runs surface flakes too).
 */

import type {
  Reporter,
  TestCase,
  TestError,
  TestResult,
} from '@playwright/test/reporter';

// ----------------------------------------------------------- pure types

export type FlakeReporterTestStatus =
  | 'passed'
  | 'failed'
  | 'timedOut'
  | 'skipped'
  | 'interrupted';

export interface FlakeReporterTestRecord {
  /** test.title — the inner-most test name (not the full describe path). */
  title: string;
  /** result.status — Playwright's final status for THIS attempt. */
  status: FlakeReporterTestStatus;
  /** result.retry — 0 for first attempt, 1 for first retry, etc. */
  retry: number;
  /** test.location.file — relative or absolute, used as-is in the annotation. */
  file: string;
  /** test.location.line — 1-indexed, fed to GitHub `line=`. */
  line: number;
  /** test.location.column — captured for completeness but NOT emitted. */
  column: number;
  /** result.duration in ms — captured for log context, not emitted. */
  duration: number;
  /** Optional: extracted from result.error[?].message — single-line summary. */
  errorMessage?: string;
}

// ----------------------------------------------------------- pure logic

/**
 * Returns true iff this record represents a flake — a test that PASSED
 * after at least one retry. Failures, timeouts, skips, and interruptions
 * are NOT flakes (those are real bugs / configuration / cancellation).
 */
export function shouldEmitFlakeAnnotation(rec: FlakeReporterTestRecord): boolean {
  return rec.status === 'passed' && rec.retry > 0;
}

/**
 * Reduce a raw error (Error, string, undefined, or arbitrary object) to a
 * single-line summary suitable for embedding in a GH annotation message.
 * - Strips stack frames (only the first line of `.message` survives).
 * - Truncates to 240 chars with a trailing `…` to stay legible.
 * - Returns a stable fallback (`"no error captured"`) for missing input —
 *   never empty string, so the annotation message slot is never blank.
 */
export function summarizeFlakyError(err: unknown): string {
  if (err === undefined || err === null) return 'no error captured';
  let msg: string;
  if (typeof err === 'string') {
    msg = err;
  } else if (err instanceof Error) {
    msg = err.message ?? '';
  } else if (typeof err === 'object' && err !== null && 'message' in err) {
    msg = String((err as { message: unknown }).message ?? '');
  } else {
    msg = String(err);
  }
  // Single line only — flake reports show one line in the GH PR view; the
  // multi-line stack belongs in the run log, not the annotation.
  msg = msg.split(/\r?\n/, 1)[0]?.trim() ?? '';
  if (msg.length === 0) return 'no error captured';
  const MAX = 240;
  if (msg.length <= MAX) return msg;
  return `${msg.slice(0, MAX - 1)}…`;
}

/**
 * Encode a string for the property-value slot of a GH workflow command.
 *
 * Per the GitHub Actions spec the value can contain `,`, `:`, and any other
 * characters as long as `,` is escaped (it separates properties) and `\r` /
 * `\n` are escaped (they delimit the command from the message body).
 *
 * https://docs.github.com/actions/learn-github-actions/workflow-commands
 */
function escapeProperty(value: string): string {
  return value
    .replace(/%/g, '%25')
    .replace(/\r/g, '%0D')
    .replace(/\n/g, '%0A')
    .replace(/:/g, '%3A')
    .replace(/,/g, '%2C');
}

/**
 * Encode a string for the message body of a GH workflow command. The body
 * lives after `::` and runs to end-of-line; `\r`, `\n`, and `%` must be
 * escaped (per the spec) so the message renders on a single line in the
 * PR annotation.
 */
function escapeMessageBody(value: string): string {
  return value
    .replace(/%/g, '%25')
    .replace(/\r/g, '%0D')
    .replace(/\n/g, '%0A');
}

/**
 * Build the `::warning ...::<msg>` line that GitHub Actions parses into a
 * PR annotation. The output is exactly one line with no trailing newline —
 * the caller decides whether to write a newline separator.
 */
export function formatGitHubFlakeAnnotation(rec: FlakeReporterTestRecord): string {
  const summary = rec.errorMessage ?? 'no error captured';
  const props = [
    `file=${escapeProperty(rec.file)}`,
    `line=${rec.line}`,
    `title=${escapeProperty(`Flaky test (passed on retry ${rec.retry})`)}`,
  ].join(',');
  const body = escapeMessageBody(`${rec.title} — ${summary}`);
  return `::warning ${props}::${body}`;
}

// ------------------------------------------------------- I/O wiring

/**
 * Lightweight projection of `@playwright/test`'s TestResult — only the fields
 * the pure logic actually reads. Defining our own shape makes the buffer logic
 * unit-testable without constructing a full TestResult mock.
 */
export interface FlakeReporterResultProjection {
  status: FlakeReporterTestStatus;
  retry: number;
  duration: number;
  /** Latest single-line error summary, if any. */
  errorSummary: string | null;
}

/**
 * Pull a single-line error summary off a Playwright result. Result.errors
 * is sometimes empty even when result.error is set (older Playwright);
 * we check both. Returns null when no usable error message is found, so
 * the caller can fall back to a buffered prior-attempt error.
 */
export function extractErrorSummary(result: {
  error?: TestError;
  errors?: ReadonlyArray<TestError>;
}): string | null {
  const errors: TestError[] = [];
  if (result.error) errors.push(result.error);
  if (Array.isArray(result.errors)) errors.push(...result.errors);
  for (const e of errors) {
    const summary = summarizeFlakyError(e?.message ?? e);
    if (summary && summary !== 'no error captured') return summary;
  }
  return null;
}

/**
 * Build the buffer key from a TestCase. testId is preferred (stable per test
 * across attempts) and falls back to file:line:title for older Playwright
 * versions that did not expose testId on TestCase.
 */
export function bufferKeyForTest(test: {
  id?: string;
  title: string;
  location: { file: string; line: number };
}): string {
  if (typeof test.id === 'string' && test.id.length > 0) return test.id;
  return `${test.location.file}:${test.location.line}:${test.title}`;
}

/**
 * Pure decision function: given the current per-test failed-attempt error
 * buffer plus the next attempt's projection, return the next buffer state
 * and (optionally) a fully-resolved record to emit.
 *
 * Semantics:
 *   - non-passing attempt → store its summary in the buffer (for the eventual
 *     passing-on-retry attempt to surface), do not emit.
 *   - passing on first attempt (retry=0) → drop any stale buffer entry, do not emit.
 *   - passing on retry (retry>0) → consume the buffered failure summary,
 *     produce a record, drop the buffer entry.
 *
 * The function is referentially transparent: it returns a NEW Map and never
 * mutates the input.
 */
export function processTestEndForFlake(
  buffer: ReadonlyMap<string, string>,
  key: string,
  testMeta: { title: string; file: string; line: number; column: number },
  result: FlakeReporterResultProjection,
): {
  buffer: Map<string, string>;
  emit: FlakeReporterTestRecord | null;
} {
  const next = new Map(buffer);

  if (result.status !== 'passed') {
    if (result.errorSummary) next.set(key, result.errorSummary);
    return { buffer: next, emit: null };
  }

  if (result.retry === 0) {
    next.delete(key);
    return { buffer: next, emit: null };
  }

  const buffered = buffer.get(key);
  const errorMessage = result.errorSummary ?? buffered ?? 'no error captured';
  next.delete(key);

  const rec: FlakeReporterTestRecord = {
    title: testMeta.title,
    status: result.status,
    retry: result.retry,
    file: testMeta.file,
    line: testMeta.line,
    column: testMeta.column,
    duration: result.duration,
    errorMessage,
  };

  if (!shouldEmitFlakeAnnotation(rec)) return { buffer: next, emit: null };
  return { buffer: next, emit: rec };
}

/**
 * Reporter implementation. The class itself is intentionally thin — every
 * decision lives in pure functions above. Side effects: a single
 * `process.stdout.write` per flake-passing test, and a final summary line.
 *
 * IMPORTANT — flake-error capture model:
 * `onTestEnd` fires once per attempt. A flaky test produces, in order:
 *   1. retry=0, status="failed", errors=[<actual cause>]
 *   2. retry=1, status="passed", errors=[]   (or further retries)
 * The passing-attempt result contains NO error — the cause lives in step (1).
 * We therefore buffer the most recent failed-attempt summary keyed by testId
 * and read it back when the test eventually passes. Without this, every flake
 * annotation would say "no error captured" and the reporter's value would be
 * limited to the test name.
 */
class FlakeAnnotationReporter implements Reporter {
  private flakes: FlakeReporterTestRecord[] = [];
  private failedAttemptErrors = new Map<string, string>();

  onTestEnd(test: TestCase, result: TestResult): void {
    const key = bufferKeyForTest(test);
    const projection: FlakeReporterResultProjection = {
      status: result.status as FlakeReporterTestStatus,
      retry: result.retry,
      duration: result.duration,
      errorSummary: extractErrorSummary(result),
    };
    const decision = processTestEndForFlake(
      this.failedAttemptErrors,
      key,
      {
        title: test.title,
        file: test.location.file,
        line: test.location.line,
        column: test.location.column,
      },
      projection,
    );
    this.failedAttemptErrors = decision.buffer;
    if (!decision.emit) return;

    this.flakes.push(decision.emit);

    const inGitHub =
      process.env.GITHUB_ACTIONS === 'true' || process.env.GITHUB_ACTIONS === '1';
    const line = inGitHub
      ? formatGitHubFlakeAnnotation(decision.emit)
      : `[FLAKE] ${decision.emit.file}:${decision.emit.line} — ${decision.emit.title} (retry ${decision.emit.retry}): ${decision.emit.errorMessage}`;
    process.stdout.write(`${line}\n`);
  }

  onEnd(): void {
    if (this.flakes.length === 0) return;
    const inGitHub =
      process.env.GITHUB_ACTIONS === 'true' || process.env.GITHUB_ACTIONS === '1';
    const totals = `${this.flakes.length} flaky test${
      this.flakes.length === 1 ? '' : 's'
    } (passed on retry)`;
    if (inGitHub) {
      process.stdout.write(`::warning title=Flake summary::${escapeMessageBody(totals)}\n`);
    } else {
      process.stdout.write(`[FLAKE-SUMMARY] ${totals}\n`);
    }
  }
}

export default FlakeAnnotationReporter;
