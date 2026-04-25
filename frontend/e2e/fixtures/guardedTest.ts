/**
 * `guardedTest` — Playwright test.extend wrapper that installs global page
 * listeners for three classes of hidden failures and fails the test at
 * teardown if any are caught.
 *
 *   * page.on('pageerror')   — uncaught JS exceptions in the browser
 *   * page.on('console')     — console.error entries (filtered through
 *                              fixtures/console-utils.ts::isBenignConsoleError
 *                              so known-benign noise stays quiet)
 *   * page.on('response')    — server responses with HTTP 5xx
 *
 * Landed in PR 2 unused. Tier-1 specs swap their `import { test } from
 * '@playwright/test'` to `from '../fixtures/guardedTest'` in PR 7a-7d.
 *
 * Design note — retry-proof artifact logging
 * --------------------------------------------
 * Playwright is configured with `retries: 2` in CI. If the guard threw only
 * via `throw new Error(...)` in teardown, a flaky retry could pass without
 * the original caught error being visible in the job outcome. To prevent
 * that, each caught error is additionally appended to a JSONL artifact at
 * `${testInfo.project.outputDir}/../guard-failures/guard-failures.jsonl`.
 * A post-run CI step (added in PR 8's strict workflow) fails the job when
 * that file is non-empty, regardless of per-test retry success.
 *
 * Design note — annotation timing
 * --------------------------------------------
 * `testInfo.annotations` is populated as the test body runs, not at fixture
 * setup. The opt-out check MUST happen after `await use(g)`, not before.
 * Tests that legitimately exercise transient 5xx (e.g. failure-path specs
 * that assert on 500 responses) annotate themselves as:
 *
 *     test.info().annotations.push({ type: 'allow-transient-5xx',
 *                                    description: 'why' });
 *
 * The guard reads that annotation during teardown and skips the 5xx check.
 */

import { test as base, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { randomBytes } from 'node:crypto';

import { isBenignConsoleError } from './console-utils';

type ServerError = { url: string; status: number };

export type GuardBuffer = {
  pageErrors: Error[];
  consoleErrors: string[];
  serverErrors: ServerError[];
};

export interface EvaluateGuardOptions {
  allowTransient5xx: boolean;
}

// ------------------------- correlation-ID guard (Phase 226 B4) -------------
//
// Platform guarantee: every API response echoes back the request's
// `X-Correlation-ID` so incident forensics can join request → response →
// audit → log. The guard generates a fresh ID per request (or reads the
// client's if it already set one), captures the response header, and
// flags mismatches + missing headers. Runs on every spec using
// `guardedTest`. Env-var kill switch `E2E_DISABLE_CORRELATION_GUARD=true`
// disables the whole guard without reverting the fixture.

const CORRELATION_HEADER = 'x-correlation-id';

export type CorrelationMismatch = { url: string; sent: string; echoed: string };
export type CorrelationMissing = { url: string; sent: string };

export type CorrelationBuffer = {
  mismatches: CorrelationMismatch[];
  missing: CorrelationMissing[];
};

export interface CorrelationEvaluateOptions {
  /** If true, suppress "response did not echo the header" problems. Mismatch
   * problems are NOT suppressed — an incorrect echo is a different bug
   * class than no echo at all. */
  allowMissing: boolean;
  /** If true (kill switch), suppress every problem. */
  guardDisabled: boolean;
}

/** Pure problem-generator. Branches covered by `_guards.spec.ts`. */
export function evaluateCorrelationProblems(
  buffer: CorrelationBuffer,
  options: CorrelationEvaluateOptions,
): string[] {
  if (options.guardDisabled) return [];
  const out: string[] = [];
  for (const m of buffer.mismatches) {
    out.push(
      `correlation-id mismatch on ${m.url}: sent=${m.sent}, echoed=${m.echoed}`,
    );
  }
  if (!options.allowMissing) {
    for (const m of buffer.missing) {
      out.push(`correlation-id missing on response from ${m.url}: sent=${m.sent}`);
    }
  }
  return out;
}

/** Env-var kill switch check. Accepts "true" or "1" (case-insensitive). */
export function isCorrelationGuardDisabled(
  env: Record<string, string | undefined>,
): boolean {
  const raw = env['E2E_DISABLE_CORRELATION_GUARD'];
  if (!raw) return false;
  const normalized = raw.trim().toLowerCase();
  return normalized === 'true' || normalized === '1';
}

/** Generate a test-scoped correlation ID. Prefix + 16 random hex chars. */
export function generateCorrelationId(): string {
  return `e2e-${randomBytes(8).toString('hex')}`;
}

/** Header-name-insensitive lookup. Playwright lowercases header keys but
 * callers sometimes pass objects with original-case keys; normalize both. */
function findHeaderCaseInsensitive(
  headers: Record<string, string> | undefined,
  name: string,
): string | undefined {
  if (!headers) return undefined;
  const target = name.toLowerCase();
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === target) return v;
  }
  return undefined;
}

/**
 * Pure function that maps a populated GuardBuffer + options into a list of
 * human-readable problem strings. Factored out of the fixture body so the
 * self-test suite can verify the branch logic without spinning up a browser.
 */
export function evaluateGuard(
  buffer: GuardBuffer,
  options: EvaluateGuardOptions,
): string[] {
  return [
    ...buffer.pageErrors.map((e) => `pageerror: ${e.message}`),
    ...buffer.consoleErrors.map((s) => `console.error: ${s}`),
    ...(options.allowTransient5xx
      ? []
      : buffer.serverErrors.map((s) => `HTTP ${s.status}: ${s.url}`)),
  ];
}

const GUARD_FAILURES_DIR_NAME = 'guard-failures';
const GUARD_FAILURES_FILE_NAME = 'guard-failures.jsonl';

function appendFailureArtifact(params: {
  outputDir: string;
  testFile: string;
  testTitle: string;
  testRetry: number;
  problems: string[];
}): void {
  // Writing sibling-of-project-outputDir so the CI post-step can find it with
  // a single glob regardless of which project/browser produced the failure.
  const dir = path.resolve(params.outputDir, '..', GUARD_FAILURES_DIR_NAME);
  try {
    fs.mkdirSync(dir, { recursive: true });
    const record = {
      test: params.testTitle,
      file: params.testFile,
      retry: params.testRetry,
      problems: params.problems,
      when: new Date().toISOString(),
    };
    fs.appendFileSync(
      path.join(dir, GUARD_FAILURES_FILE_NAME),
      JSON.stringify(record) + '\n',
      { encoding: 'utf8' },
    );
  } catch (err) {
    // We intentionally swallow the write failure — if we can't persist the
    // artifact, throwing in teardown is still the primary signal. Don't want
    // the test harness itself to break because the runner filesystem is
    // read-only, etc.
    // eslint-disable-next-line no-console
    console.warn(
      `[guardedTest] Could not persist failure artifact: ${(err as Error).message}`,
    );
  }
}

export const test = base.extend<{
  guard: GuardBuffer;
  /** Auto-fixture: activates on every spec that imports `test` from this
   * file, even if the spec does not destructure `{ correlation }`. */
  correlation: CorrelationBuffer;
}>({
  guard: async ({ page }, use, testInfo) => {
    const buffer: GuardBuffer = {
      pageErrors: [],
      consoleErrors: [],
      serverErrors: [],
    };

    page.on('pageerror', (err) => {
      buffer.pageErrors.push(err);
    });

    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      const text = msg.text();
      if (isBenignConsoleError(text)) return;
      buffer.consoleErrors.push(text);
    });

    page.on('response', (res) => {
      const status = res.status();
      if (status >= 500) {
        buffer.serverErrors.push({ url: res.url(), status });
      }
    });

    // Hand control to the test body. Annotations are populated here, not
    // before — so the opt-out check MUST happen after this await.
    await use(buffer);

    const allowTransient5xx = testInfo.annotations.some(
      (a) => a.type === 'allow-transient-5xx',
    );

    const problems = evaluateGuard(buffer, { allowTransient5xx });
    if (problems.length === 0) return;

    appendFailureArtifact({
      outputDir: testInfo.project.outputDir,
      testFile: testInfo.file,
      testTitle: testInfo.titlePath.join(' > '),
      testRetry: testInfo.retry,
      problems,
    });

    throw new Error(
      `guardedTest caught ${problems.length} hidden failure${
        problems.length === 1 ? '' : 's'
      }:\n${problems.join('\n')}`,
    );
  },

  correlation: [async ({ page }, use, testInfo) => {
    const buffer: CorrelationBuffer = { mismatches: [], missing: [] };
    const disabled = isCorrelationGuardDisabled(process.env);

    // Passive-observe design. We do NOT install `page.route` interception —
    // that would break specs that register their own route handlers. Instead,
    // we seed an extra HTTP header once so every outbound request the browser
    // makes carries a known correlation-ID; then we observe responses and
    // verify the echo. Specs that need their own correlation-ID per-request
    // can override the header via `page.setExtraHTTPHeaders` before making
    // the call and opt out of the mismatch check via annotation.
    const testScopedId = generateCorrelationId();

    if (!disabled) {
      await page.setExtraHTTPHeaders({ [CORRELATION_HEADER]: testScopedId });

      page.on('response', (res) => {
        const req = res.request();
        const reqHeaders = req.headers();
        const sent = findHeaderCaseInsensitive(reqHeaders, CORRELATION_HEADER);
        if (!sent) return; // request didn't carry the header (e.g. non-fetch nav); skip
        const echoed = findHeaderCaseInsensitive(res.headers(), CORRELATION_HEADER);
        if (echoed === undefined) {
          buffer.missing.push({ url: res.url(), sent });
        } else if (echoed !== sent) {
          buffer.mismatches.push({ url: res.url(), sent, echoed });
        }
      });

      // Expose the test-scoped sent ID on test.info() so verifyAuditEvent (B3)
      // can cross-check the audit row's correlation_id.
      testInfo.annotations.push({
        type: 'correlation-id-sent',
        description: testScopedId,
      });
    }

    await use(buffer);

    const allowMissing = testInfo.annotations.some(
      (a) => a.type === 'allow-missing-correlation-id',
    );
    const problems = evaluateCorrelationProblems(buffer, {
      allowMissing,
      guardDisabled: disabled,
    });
    if (problems.length === 0) return;

    appendFailureArtifact({
      outputDir: testInfo.project.outputDir,
      testFile: testInfo.file,
      testTitle: testInfo.titlePath.join(' > '),
      testRetry: testInfo.retry,
      problems,
    });

    throw new Error(
      `guardedTest caught ${problems.length} correlation-id problem${
        problems.length === 1 ? '' : 's'
      }:\n${problems.join('\n')}`,
    );
  }, { auto: true }],
});

export { expect };
