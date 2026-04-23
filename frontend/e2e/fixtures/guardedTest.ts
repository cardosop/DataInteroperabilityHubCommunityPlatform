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

export const test = base.extend<{ guard: GuardBuffer }>({
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
});

export { expect };
