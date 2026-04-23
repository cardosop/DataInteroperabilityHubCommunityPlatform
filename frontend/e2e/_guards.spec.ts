/**
 * Self-tests for the Playwright dual-channel guards.
 *
 * A guard that has its own bug becomes a silent passer — worse than no guard.
 * This suite proves the pure branch logic of guardedTest and verifyViaApi
 * without booting a browser, plus one happy-path fixture-integration check
 * to guarantee the fixture still wires up correctly.
 *
 * Note: deliberately imports from @playwright/test (not guardedTest) for the
 * unit tests — we're testing the guard, not using it.
 *
 * Run:
 *     cd frontend && npx playwright test e2e/_guards.spec.ts
 */

import { test, expect } from '@playwright/test';

import { evaluateGuard } from './fixtures/guardedTest';
import type { GuardBuffer } from './fixtures/guardedTest';
import { matchBody } from './fixtures/verifyViaApi';
import { isBenignConsoleError } from './fixtures/console-utils';

function emptyBuffer(): GuardBuffer {
  return { pageErrors: [], consoleErrors: [], serverErrors: [] };
}

// ---------------------------------------------------------------- evaluateGuard

test.describe('evaluateGuard — pure branch logic', () => {
  test('empty buffer → no problems', () => {
    const problems = evaluateGuard(emptyBuffer(), { allowTransient5xx: false });
    expect(problems).toEqual([]);
  });

  test('pageerror is reported', () => {
    const buffer = emptyBuffer();
    buffer.pageErrors.push(new Error('boom'));
    const problems = evaluateGuard(buffer, { allowTransient5xx: false });
    expect(problems).toEqual(['pageerror: boom']);
  });

  test('non-benign console.error is reported', () => {
    const buffer = emptyBuffer();
    buffer.consoleErrors.push('real app bug: foo failed');
    const problems = evaluateGuard(buffer, { allowTransient5xx: false });
    expect(problems).toEqual(['console.error: real app bug: foo failed']);
  });

  test('HTTP 5xx is reported by default', () => {
    const buffer = emptyBuffer();
    buffer.serverErrors.push({ url: 'https://x/api', status: 503 });
    const problems = evaluateGuard(buffer, { allowTransient5xx: false });
    expect(problems).toEqual(['HTTP 503: https://x/api']);
  });

  test('HTTP 5xx is suppressed by allow-transient-5xx opt-out', () => {
    const buffer = emptyBuffer();
    buffer.serverErrors.push({ url: 'https://x/api', status: 500 });
    const problems = evaluateGuard(buffer, { allowTransient5xx: true });
    expect(problems).toEqual([]);
  });

  test('opt-out does NOT suppress pageerror or console.error', () => {
    const buffer = emptyBuffer();
    buffer.pageErrors.push(new Error('js-boom'));
    buffer.consoleErrors.push('real bug');
    buffer.serverErrors.push({ url: 'https://x/api', status: 502 });
    const problems = evaluateGuard(buffer, { allowTransient5xx: true });
    expect(problems).toEqual([
      'pageerror: js-boom',
      'console.error: real bug',
    ]);
  });

  test('multiple errors are reported in deterministic order', () => {
    const buffer: GuardBuffer = {
      pageErrors: [new Error('first'), new Error('second')],
      consoleErrors: ['cerror-1', 'cerror-2'],
      serverErrors: [
        { url: 'https://x/a', status: 500 },
        { url: 'https://x/b', status: 503 },
      ],
    };
    const problems = evaluateGuard(buffer, { allowTransient5xx: false });
    expect(problems).toEqual([
      'pageerror: first',
      'pageerror: second',
      'console.error: cerror-1',
      'console.error: cerror-2',
      'HTTP 500: https://x/a',
      'HTTP 503: https://x/b',
    ]);
  });
});

// ------------------------------------------------------------------- matchBody

test.describe('matchBody — verifyViaApi pure matcher', () => {
  test('returns null when exact-match expectation is satisfied', async () => {
    const body = { status: 'ACTIVE', id: 42, name: 'asset-x' };
    const mismatch = await matchBody(body, { status: 'ACTIVE', id: 42 });
    expect(mismatch).toBeNull();
  });

  test('returns mismatch message when primitive differs', async () => {
    const body = { status: 'INACTIVE', id: 42 };
    const mismatch = await matchBody(body, { status: 'ACTIVE' });
    expect(mismatch).not.toBeNull();
    expect(mismatch).toContain('status');
    expect(mismatch).toContain('"ACTIVE"');
    expect(mismatch).toContain('"INACTIVE"');
  });

  test('returns mismatch when field is missing', async () => {
    const body = { id: 42 };
    const mismatch = await matchBody(body as object, { status: 'ACTIVE' });
    expect(mismatch).not.toBeNull();
    expect(mismatch).toContain('status');
  });

  test('deep-equals objects via JSON stringify', async () => {
    const body = { meta: { k: 'v', n: 1 } };
    const mismatch = await matchBody(body, { meta: { k: 'v', n: 1 } });
    expect(mismatch).toBeNull();
  });

  test('deep-inequals detected for nested mismatch', async () => {
    const body = { meta: { k: 'v', n: 1 } };
    const mismatch = await matchBody(body, { meta: { k: 'v', n: 2 } });
    expect(mismatch).not.toBeNull();
    expect(mismatch).toContain('meta');
  });

  test('predicate returning true → null', async () => {
    const body = { count: 5 };
    const mismatch = await matchBody(body, (b) => b.count > 0);
    expect(mismatch).toBeNull();
  });

  test('predicate returning false → mismatch', async () => {
    const body = { count: 0 };
    const mismatch = await matchBody(body, (b) => b.count > 0);
    expect(mismatch).not.toBeNull();
    expect(mismatch).toContain('predicate returned false');
  });

  test('async predicate is awaited', async () => {
    const body = { ready: true };
    const mismatch = await matchBody(body, async (b) => {
      await new Promise((resolve) => setTimeout(resolve, 1));
      return b.ready;
    });
    expect(mismatch).toBeNull();
  });
});

// --------------------------------------- console allowlist — NOT-benign regression gate
//
// PR 3 removed three classes of 500-whitelist entries from isBenignConsoleError
// because they were hiding real backend bugs (missing indexes causing
// statement-timeouts, connection-pool exhaustion, aborted DB transactions).
// If a well-meaning future edit re-adds them, these tests break fast.

test.describe('console allowlist regression gate (PR 3)', () => {
  const MUST_BE_REPORTED: readonly [string, string][] = [
    [
      'statement timeout (500)',
      'Failed to load resource: the server responded with a status of 500 () — PostgreSQL statement timeout',
    ],
    [
      'statement timeout ([Error Report])',
      '[Error Report] Request failed: statement timeout',
    ],
    [
      'too many clients',
      'FATAL: too many clients already',
    ],
    [
      'too many connections',
      'too many connections for role "hub"',
    ],
    [
      'ODPS atomic block',
      '[Error Report] atomic block did not commit: current transaction is aborted',
    ],
    [
      'ODPS current transaction aborted',
      '[Error Report] current transaction is aborted, commands ignored until end of transaction block',
    ],
    [
      'ODPS product creation failed',
      '[Error Report] product creation failed',
    ],
  ];

  for (const [label, text] of MUST_BE_REPORTED) {
    test(`${label} is NOT benign`, () => {
      expect(
        isBenignConsoleError(text),
        `"${text}" must surface as a real bug, not be allowlisted.`,
      ).toBe(false);
    });
  }

  test('401/403/429 auth noise is still benign (not a regression)', () => {
    // Sanity check that we only tightened the 500-class entries, not the
    // legitimately-noisy auth entries that protect unrelated tests.
    expect(
      isBenignConsoleError('Failed to load resource: status 401'),
    ).toBe(true);
    expect(
      isBenignConsoleError('Failed to load resource: status 429'),
    ).toBe(true);
  });
});

// ----------------------------------------------------- guardedTest integration

test.describe('guardedTest — integration (happy path)', () => {
  // Use a separate import path so we exercise the actual fixture wiring.
  // Intentionally scoped to "passes when nothing is wrong" because the failure
  // modes are already covered by the pure evaluateGuard tests above and a
  // browser-level "expected failure" test would depend on render-time timing
  // that is fragile to diagnose separately from the guard itself.
  const { test: guarded } = require('./fixtures/guardedTest');

  guarded('no pageerror, no console.error, no 5xx → test passes', async ({
    page,
    guard,
  }: {
    page: import('@playwright/test').Page;
    guard: GuardBuffer;
  }) => {
    await page.goto('about:blank');
    // Sanity check that the fixture handed us a live buffer
    expect(guard.pageErrors).toEqual([]);
    expect(guard.consoleErrors).toEqual([]);
    expect(guard.serverErrors).toEqual([]);
  });
});
