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

import {
  evaluateGuard,
  test as guardedTest,
  evaluateCorrelationProblems,
  isCorrelationGuardDisabled,
  generateCorrelationId,
  // Phase 226 G16 — security-header guard pure helpers.
  evaluateSecurityHeaders,
  hasSecurityHeaderEvidence,
  isDocumentResponseForSecurityGuard,
  isSecurityHeaderGuardDisabled,
  type CorrelationBuffer,
  type CorrelationEvaluateOptions,
} from './fixtures/guardedTest';
import type { GuardBuffer } from './fixtures/guardedTest';
import { matchBody, classifyAbsenceStatus } from './fixtures/verifyViaApi';
import {
  findMatchingAuditEvent,
  pollForAuditEvent,
  type AuditEventRow,
} from './fixtures/verifyAuditEvent';
import {
  classifyClearAuthStorageError,
  isChromeErrorPageStorageAccessError,
} from './fixtures/auth';
import {
  buildMailhogRequestHeaders,
  isMailhogProxyUrl,
} from './fixtures/auth-journey-steps';
import { classifyLoginResponse } from './setup/create-test-user';
import {
  canonicalIriFor,
  classifyDereferenceResponse,
  validateJsonLdPayload,
  sparqlResultHasExpectedTriple,
} from './fixtures/verifySemantic';
import { isBenignConsoleError } from './fixtures/console-utils';
import {
  canonicalize,
  hashCanonical,
  extractSchemaShape,
  diffShapes,
  classifyDiff,
  type OpenAPISchema,
  type SchemaShape,
} from './fixtures/openapiDrift';
import { RefreshRaceState, decidePost401 } from './fixtures/refreshRaceState';
import {
  filterByImpact,
  summarizeViolations,
  expectNoSeriousViolations,
  type AxeAuditResult,
  type AxeViolation,
} from './fixtures/axeAudit';

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

// ------------------------------------------ classifyAbsenceStatus (Phase 226 B2)
//
// Pure classifier that verifyViaApiAbsent / verifyViaApiForbidden feed response
// status codes into. Separated from the browser-facing helper so the branches
// are unit-testable without a Page / network.

test.describe('classifyAbsenceStatus — pure branch logic (Phase 226 B2)', () => {
  test('404 → "absent"', () => {
    expect(classifyAbsenceStatus(404)).toBe('absent');
  });

  test('403 → "forbidden"', () => {
    expect(classifyAbsenceStatus(403)).toBe('forbidden');
  });

  test('401 → "unauthorized" (distinct from forbidden — session invalid)', () => {
    expect(classifyAbsenceStatus(401)).toBe('unauthorized');
  });

  test('200 → "visible" (resource IS visible — fails absent/forbidden test)', () => {
    expect(classifyAbsenceStatus(200)).toBe('visible');
  });

  test('204 → "visible" (any 2xx)', () => {
    expect(classifyAbsenceStatus(204)).toBe('visible');
  });

  test('500 → "server-error" (never acceptable — real bug)', () => {
    expect(classifyAbsenceStatus(500)).toBe('server-error');
  });

  test('502 → "server-error"', () => {
    expect(classifyAbsenceStatus(502)).toBe('server-error');
  });

  test('400 → "other-client-error" (not the absence signal)', () => {
    expect(classifyAbsenceStatus(400)).toBe('other-client-error');
  });

  test('429 → "other-client-error" (rate-limit is transient, not absence)', () => {
    expect(classifyAbsenceStatus(429)).toBe('other-client-error');
  });

  test('301 → "unexpected-redirect"', () => {
    expect(classifyAbsenceStatus(301)).toBe('unexpected-redirect');
  });
});

// ----------------------------------------- verifyAuditEvent pure logic (Phase 226 B3)
//
// The browser-facing helper calls `GET /api/v1/audit/events/?...` and polls
// for the matching row under a configurable retry budget (async audit writes
// may lag the UI response). Pure logic split out:
//   - findMatchingAuditEvent: given a list of rows + expectation, return the
//     first matching row or a human-readable mismatch message.
//   - pollForAuditEvent: given an injected fetcher, poll until found or budget
//     exhausts. Injected fetcher lets us unit-test without network.

const baseRow = (overrides: Partial<AuditEventRow> = {}): AuditEventRow => ({
  id: 'audit-1',
  action: 'ASSET_CREATED',
  resource_type: 'ASSET',
  resource_id: '00000000-0000-0000-0000-000000000001',
  actor_user: 'user-1',
  tenant: 'tenant-1',
  result: 'SUCCESS',
  timestamp: '2026-04-24T10:00:00Z',
  // correlation_id left undefined by default — the audit model doesn't emit
  // it yet. Tests that want to exercise the correlation-id filter set it
  // explicitly via overrides.
  ...overrides,
});

test.describe('findMatchingAuditEvent — pure matcher (Phase 226 B3)', () => {
  test('empty list → mismatch message cites zero rows', () => {
    const result = findMatchingAuditEvent([], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: 'x',
    });
    expect(result.matched).toBeNull();
    expect(result.mismatch).toContain('0 rows');
  });

  test('exact-match on required fields → returns row', () => {
    const row = baseRow();
    const result = findMatchingAuditEvent([row], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: row.resource_id!,
    });
    expect(result.matched).toEqual(row);
    expect(result.mismatch).toBeNull();
  });

  test('action mismatch → no match, mismatch cites the diff', () => {
    const row = baseRow({ action: 'ASSET_UPDATED' });
    const result = findMatchingAuditEvent([row], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: row.resource_id!,
    });
    expect(result.matched).toBeNull();
    expect(result.mismatch).toContain('ASSET_CREATED');
    expect(result.mismatch).toContain('ASSET_UPDATED');
  });

  test('resource_id mismatch → no match', () => {
    const row = baseRow();
    const result = findMatchingAuditEvent([row], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: 'other',
    });
    expect(result.matched).toBeNull();
    expect(result.mismatch).toContain('other');
  });

  test('tenant filter matches when supplied', () => {
    const rowA = baseRow({ tenant: 'tenant-A' });
    const rowB = baseRow({ tenant: 'tenant-B' });
    const result = findMatchingAuditEvent([rowA, rowB], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: rowA.resource_id!,
      tenantId: 'tenant-B',
    });
    expect(result.matched).toEqual(rowB);
  });

  test('correlation_id filter matches when row carries the field', () => {
    const rowA = baseRow({ correlation_id: 'corr-111' });
    const rowB = baseRow({ correlation_id: 'corr-222' });
    const result = findMatchingAuditEvent([rowA, rowB], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: rowA.resource_id!,
      correlationId: 'corr-222',
    });
    expect(result.matched).toEqual(rowB);
  });

  test('correlation_id filter no-ops gracefully when row lacks the field', () => {
    // Real-world case: backend audit model does not emit correlation_id
    // today. Filter should not reject rows that have no correlation_id.
    const row = baseRow({ correlation_id: undefined });
    const result = findMatchingAuditEvent([row], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: row.resource_id!,
      correlationId: 'corr-expected-but-not-yet-emitted',
    });
    expect(result.matched).toEqual(row);
  });

  test('actor filter matches when supplied', () => {
    const rowA = baseRow({ actor_user: 'user-A' });
    const rowB = baseRow({ actor_user: 'user-B' });
    const result = findMatchingAuditEvent([rowA, rowB], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: rowA.resource_id!,
      actorUserId: 'user-B',
    });
    expect(result.matched).toEqual(rowB);
  });

  test('first match wins with multiple matching rows', () => {
    const row1 = baseRow({ id: 'a1', timestamp: '2026-04-24T10:00:00Z' });
    const row2 = baseRow({ id: 'a2', timestamp: '2026-04-24T10:00:01Z' });
    const result = findMatchingAuditEvent([row1, row2], {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: row1.resource_id!,
    });
    expect(result.matched?.id).toBe('a1');
  });
});

test.describe('pollForAuditEvent — retry budget + injected fetcher (Phase 226 B3)', () => {
  test('succeeds on first attempt when row is already present', async () => {
    let calls = 0;
    const fetcher = async (): Promise<AuditEventRow[]> => {
      calls += 1;
      return [baseRow()];
    };
    const row = await pollForAuditEvent(fetcher, {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: baseRow().resource_id!,
      retryBudgetMs: 2000,
      pollIntervalMs: 100,
    });
    expect(row.id).toBe('audit-1');
    expect(calls).toBe(1);
  });

  test('succeeds on retry after initial empty response (eventual consistency)', async () => {
    let calls = 0;
    const fetcher = async (): Promise<AuditEventRow[]> => {
      calls += 1;
      if (calls < 3) return [];
      return [baseRow()];
    };
    const row = await pollForAuditEvent(fetcher, {
      action: 'ASSET_CREATED',
      resourceType: 'ASSET',
      resourceId: baseRow().resource_id!,
      retryBudgetMs: 2000,
      pollIntervalMs: 10,
    });
    expect(row.id).toBe('audit-1');
    expect(calls).toBe(3);
  });

  test('throws when retry budget exhausts without a match', async () => {
    let calls = 0;
    const fetcher = async (): Promise<AuditEventRow[]> => {
      calls += 1;
      return [];
    };
    await expect(
      pollForAuditEvent(fetcher, {
        action: 'ASSET_CREATED',
        resourceType: 'ASSET',
        resourceId: 'missing',
        retryBudgetMs: 60,
        pollIntervalMs: 20,
      }),
    ).rejects.toThrow(/no matching audit row/i);
    expect(calls).toBeGreaterThan(1); // at least 2 attempts within the budget
  });

  test('throws with diagnostic body preview on exhaustion (rows existed but none matched)', async () => {
    const fetcher = async (): Promise<AuditEventRow[]> => [
      baseRow({ action: 'ASSET_UPDATED' }),
    ];
    await expect(
      pollForAuditEvent(fetcher, {
        action: 'ASSET_CREATED',
        resourceType: 'ASSET',
        resourceId: baseRow().resource_id!,
        retryBudgetMs: 40,
        pollIntervalMs: 10,
      }),
    ).rejects.toThrow(/ASSET_CREATED/);
  });

  test('default retry budget is 3000ms (audit emission is synchronous — Phase 226 OQ1)', async () => {
    // Pin the budget. Audit writes are synchronous via
    // `hub/apps/audit/utils.py:239` (zero `.delay()` callsites). 3 s
    // covers replication lag for the audit list endpoint and nothing
    // more — bumping back to 10 s would re-introduce the silent
    // flake-tolerance OQ1 was created to remove.
    let attemptTimestamps: number[] = [];
    const fetcher = async (): Promise<AuditEventRow[]> => {
      attemptTimestamps.push(Date.now());
      return [];
    };
    const start = Date.now();
    await expect(
      pollForAuditEvent(fetcher, {
        action: 'ASSET_CREATED',
        resourceType: 'ASSET',
        resourceId: 'missing-id',
        // No retryBudgetMs override — exercises the default.
      }),
    ).rejects.toThrow(/3000 ms retry budget/);
    const elapsed = Date.now() - start;
    // Default is 3000 ms; allow some slack for CI runners but reject any
    // accidental 10 000 ms regression.
    expect(elapsed).toBeGreaterThanOrEqual(2500);
    expect(elapsed).toBeLessThan(6000);
    expect(attemptTimestamps.length).toBeGreaterThan(1);
  });
});

// ----------------------------------------- clearAuthStorage error classification
//
// Pure logic backing `clearAuthStorage` in fixtures/auth.ts. The function has
// to tolerate four distinct transient failure modes (page-closed, chrome-error
// page, transient network, navigation timeout) without swallowing real bugs.
// Pinning every classifier branch here means a regression in the bucketing
// logic shows up as a unit-test failure — long before it propagates as a
// suite-wide flake on staging.

test.describe('classifyClearAuthStorageError — pure error bucketing', () => {
  test('Playwright "Target closed" → page-closed', () => {
    const err = new Error(
      'page.goto: Target page, context or browser has been closed',
    );
    expect(classifyClearAuthStorageError(err)).toBe('page-closed');
  });

  test('Playwright "Execution context was destroyed" → page-closed', () => {
    const err = new Error('Execution context was destroyed');
    expect(classifyClearAuthStorageError(err)).toBe('page-closed');
  });

  test('SecurityError on localStorage → chrome-error-page', () => {
    const err = new Error(
      "page.evaluate: SecurityError: Failed to read the 'localStorage' property from 'Window': Access is denied for this document.",
    );
    expect(classifyClearAuthStorageError(err)).toBe('chrome-error-page');
  });

  test('"Access is denied for this document" alone → chrome-error-page', () => {
    const err = new Error('Access is denied for this document');
    expect(classifyClearAuthStorageError(err)).toBe('chrome-error-page');
  });

  test('net::ERR_NAME_NOT_RESOLVED → transient-network', () => {
    const err = new Error('page.reload: net::ERR_NAME_NOT_RESOLVED');
    expect(classifyClearAuthStorageError(err)).toBe('transient-network');
  });

  test('net::ERR_NETWORK_CHANGED → transient-network', () => {
    const err = new Error('page.reload: net::ERR_NETWORK_CHANGED');
    expect(classifyClearAuthStorageError(err)).toBe('transient-network');
  });

  test('net::ERR_INTERNET_DISCONNECTED → transient-network', () => {
    const err = new Error('page.goto: net::ERR_INTERNET_DISCONNECTED');
    expect(classifyClearAuthStorageError(err)).toBe('transient-network');
  });

  test('net::ERR_CONNECTION_RESET → transient-network', () => {
    const err = new Error('page.goto: net::ERR_CONNECTION_RESET');
    expect(classifyClearAuthStorageError(err)).toBe('transient-network');
  });

  test('Node fetch ECONNREFUSED → transient-network', () => {
    const err = new Error('fetch failed') as Error & { cause?: { code: string } };
    err.cause = { code: 'ECONNREFUSED' };
    expect(classifyClearAuthStorageError(err)).toBe('transient-network');
  });

  test('"Timeout 30000ms exceeded" → timeout', () => {
    const err = new Error('Timeout 30000ms exceeded');
    expect(classifyClearAuthStorageError(err)).toBe('timeout');
  });

  test('"Test timeout of 60000ms exceeded" → fatal (not retryable)', () => {
    // Test-level timeouts are NOT transient: the test budget is gone, so
    // pretending the timeout is benign would mask real overall-budget bugs.
    const err = new Error('Test timeout of 60000ms exceeded');
    expect(classifyClearAuthStorageError(err)).toBe('fatal');
  });

  test('arbitrary error → fatal', () => {
    const err = new Error('TypeError: Cannot read property "foo" of undefined');
    expect(classifyClearAuthStorageError(err)).toBe('fatal');
  });

  test('non-Error throwable (string) → fatal', () => {
    expect(classifyClearAuthStorageError('something went wrong')).toBe('fatal');
  });

  test('null / undefined → fatal (no swallow)', () => {
    expect(classifyClearAuthStorageError(null)).toBe('fatal');
    expect(classifyClearAuthStorageError(undefined)).toBe('fatal');
  });

  test('classifier precedence: page-closed beats chrome-error-page', () => {
    // A page-closed error during a localStorage read should NOT be misread
    // as a chrome-error page. The page is gone, not partition-isolated.
    const err = new Error(
      'page has been closed; SecurityError: localStorage', // hypothetical merged string
    );
    expect(classifyClearAuthStorageError(err)).toBe('page-closed');
  });
});

test.describe('isChromeErrorPageStorageAccessError — narrow predicate', () => {
  test('matches the exact Chromium SecurityError shape', () => {
    expect(
      isChromeErrorPageStorageAccessError(
        new Error("SecurityError: Failed to read the 'localStorage' property from 'Window': Access is denied for this document."),
      ),
    ).toBe(true);
  });

  test('does NOT match a generic localStorage-undefined error', () => {
    // ReferenceError when localStorage is unavailable for other reasons (eg
    // private mode constraints) should NOT bucket here — those are real bugs.
    expect(
      isChromeErrorPageStorageAccessError(
        new Error('ReferenceError: localStorage is not defined'),
      ),
    ).toBe(false);
  });

  test('does NOT match unrelated SecurityErrors', () => {
    expect(
      isChromeErrorPageStorageAccessError(
        new Error("SecurityError: The operation is insecure."),
      ),
    ).toBe(false);
  });
});

// ----------------------------------------- mailhog client header gating (Phase 226 OQ-MailHog)
//
// The MailHog client used by JOURNEY-AUTH-003 must send `X-E2E-Token`
// only when targeting the staging proxy (non-localhost). Local-dev
// MailHog is plain HTTP and ignores extra headers, but sending the
// secret to a localhost service would still leak it into request logs
// kept by anyone running `MAILHOG_URL=http://my-shared-vm:8025`.

test.describe('isMailhogProxyUrl — pure URL bucketing', () => {
  test('localhost variants → false (no token needed)', () => {
    expect(isMailhogProxyUrl('http://localhost:8025')).toBe(false);
    expect(isMailhogProxyUrl('http://127.0.0.1:8025')).toBe(false);
    expect(isMailhogProxyUrl('https://127.0.0.1/api/v1')).toBe(false);
    expect(isMailhogProxyUrl('http://0.0.0.0:8025')).toBe(false);
  });

  test('staging proxy URL → true (token required)', () => {
    expect(
      isMailhogProxyUrl('https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog'),
    ).toBe(true);
  });

  test('non-localhost LAN URL → true (defensive: still treat as proxy)', () => {
    expect(isMailhogProxyUrl('http://10.0.0.5:8025')).toBe(true);
    expect(isMailhogProxyUrl('http://my-mailhog:8025')).toBe(true);
  });
});

test.describe('classifyLoginResponse — pure HTTP-status bucketing', () => {
  test('200/204 → ok', () => {
    expect(classifyLoginResponse(200)).toBe('ok');
    expect(classifyLoginResponse(204)).toBe('ok');
  });

  test('429 → rate-limit (caller retries with longer delay)', () => {
    expect(classifyLoginResponse(429)).toBe('rate-limit');
  });

  test('5xx → server-error (caller retries — transient infra)', () => {
    // The 2026-04-28 staging run lost 29 tests to a 503 burst that looked
    // identical to wrong-password before this classifier landed.
    expect(classifyLoginResponse(500)).toBe('server-error');
    expect(classifyLoginResponse(502)).toBe('server-error');
    expect(classifyLoginResponse(503)).toBe('server-error');
    expect(classifyLoginResponse(504)).toBe('server-error');
  });

  test('4xx (other than 429) → client-error (real auth failure, no retry)', () => {
    expect(classifyLoginResponse(400)).toBe('client-error');
    expect(classifyLoginResponse(401)).toBe('client-error');
    expect(classifyLoginResponse(403)).toBe('client-error');
    expect(classifyLoginResponse(404)).toBe('client-error');
    expect(classifyLoginResponse(422)).toBe('client-error');
  });

  test('1xx / 3xx / weird → unknown (conservative — fail loud)', () => {
    expect(classifyLoginResponse(100)).toBe('unknown');
    expect(classifyLoginResponse(301)).toBe('unknown');
    expect(classifyLoginResponse(0)).toBe('unknown');
    expect(classifyLoginResponse(999)).toBe('unknown');
  });
});

test.describe('buildMailhogRequestHeaders — pure header bag', () => {
  test('localhost URL → no headers (regardless of token)', () => {
    expect(buildMailhogRequestHeaders('http://localhost:8025', 'secret')).toEqual({});
    expect(buildMailhogRequestHeaders('http://127.0.0.1:8025', 'secret')).toEqual({});
  });

  test('staging URL with token → X-E2E-Token header', () => {
    const headers = buildMailhogRequestHeaders(
      'https://api.stagingmeshant-internal.example.com/api/v1/test/mailhog',
      'staging-secret',
    );
    expect(headers).toEqual({ 'X-E2E-Token': 'staging-secret' });
  });

  test('staging URL without token → empty headers (fail-loud later)', () => {
    // Empty token shouldn't render `X-E2E-Token: ""` (the proxy would 404).
    // Instead we omit the header so the proxy 404s with a clearer signal.
    expect(
      buildMailhogRequestHeaders('https://api.stagingmeshant-internal.example.com', undefined),
    ).toEqual({});
    expect(
      buildMailhogRequestHeaders('https://api.stagingmeshant-internal.example.com', ''),
    ).toEqual({});
  });
});

// ----------------------------------------- verifySemanticIri pure logic (Phase 226 B5)
//
// The browser-facing helper runs a five-step chain against the semantic
// endpoint: (1) 303 dereferencing redirect, (2) JSON-LD payload validation,
// (3) JSON-LD context document, (4) SPARQL triple visibility, (5) negative
// bogus-UUID 404. Pure logic split out so every branch is unit-testable
// without a browser.

test.describe('canonicalIriFor — pure IRI construction (Phase 226 B5)', () => {
  test('constructs SEMANTIC_BASE_IRI/id/<type>/<id>', () => {
    expect(
      canonicalIriFor('https://meshant.example.com', 'asset', 'abc-123'),
    ).toBe('https://meshant.example.com/id/asset/abc-123');
  });

  test('strips trailing slash from base', () => {
    expect(
      canonicalIriFor('https://meshant.example.com/', 'dataset', 'abc-123'),
    ).toBe('https://meshant.example.com/id/dataset/abc-123');
  });

  test('throws on empty resource type', () => {
    expect(() => canonicalIriFor('https://x', '', 'id')).toThrow(/resourceType/);
  });

  test('throws on empty resource id', () => {
    expect(() => canonicalIriFor('https://x', 'asset', '')).toThrow(/resourceId/);
  });
});

test.describe('classifyDereferenceResponse — 303-or-direct branch (Phase 226 B5)', () => {
  test('303 with matching Location header → "redirect-match"', () => {
    expect(
      classifyDereferenceResponse({
        status: 303,
        locationHeader: 'https://x/id/asset/abc',
      }, 'https://x/id/asset/abc'),
    ).toBe('redirect-match');
  });

  test('303 with mismatched Location → "redirect-mismatch"', () => {
    expect(
      classifyDereferenceResponse({
        status: 303,
        locationHeader: 'https://x/id/asset/other',
      }, 'https://x/id/asset/abc'),
    ).toBe('redirect-mismatch');
  });

  test('303 with no Location header → "redirect-missing-location"', () => {
    expect(
      classifyDereferenceResponse({
        status: 303,
        locationHeader: null,
      }, 'https://x/id/asset/abc'),
    ).toBe('redirect-missing-location');
  });

  test('200 (direct JSON-LD return) → "direct-payload"', () => {
    expect(
      classifyDereferenceResponse({
        status: 200,
        locationHeader: null,
      }, 'https://x/id/asset/abc'),
    ).toBe('direct-payload');
  });

  test('404 → "not-found" (negative-path confirmation)', () => {
    expect(
      classifyDereferenceResponse({
        status: 404,
        locationHeader: null,
      }, 'https://x/id/asset/abc'),
    ).toBe('not-found');
  });

  test('500 → "server-error"', () => {
    expect(
      classifyDereferenceResponse({
        status: 500,
        locationHeader: null,
      }, 'https://x/id/asset/abc'),
    ).toBe('server-error');
  });
});

test.describe('validateJsonLdPayload — shape checks (Phase 226 B5)', () => {
  const basePayload = () => ({
    '@context': 'https://meshant.example.com/context.jsonld',
    '@id': 'https://meshant.example.com/id/asset/abc',
    '@type': 'meshant:Asset',
  });

  test('valid payload with expected @id and @type → null', () => {
    const mismatch = validateJsonLdPayload(basePayload(), {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toBeNull();
  });

  test('missing @context → mismatch', () => {
    const payload = basePayload() as Record<string, unknown>;
    delete payload['@context'];
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toContain('@context');
  });

  test('missing @id → mismatch', () => {
    const payload = basePayload() as Record<string, unknown>;
    delete payload['@id'];
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toContain('@id');
  });

  test('@id mismatch → reports diff', () => {
    const payload = basePayload();
    payload['@id'] = 'https://wrong.example.com/id/asset/abc';
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toContain('@id');
    expect(mismatch).toContain('meshant.example.com');
    expect(mismatch).toContain('wrong.example.com');
  });

  test('@type mismatch when expectedType is set', () => {
    const payload = basePayload();
    payload['@type'] = 'meshant:Dataset';
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toContain('@type');
  });

  test('expectedType undefined → @type is not checked', () => {
    const payload = basePayload();
    payload['@type'] = 'anything';
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
    });
    expect(mismatch).toBeNull();
  });

  test('@type may be an array (JSON-LD allows multiple types)', () => {
    const payload = basePayload() as Record<string, unknown>;
    payload['@type'] = ['meshant:Asset', 'schema:Dataset'];
    const mismatch = validateJsonLdPayload(payload, {
      expectedIri: 'https://meshant.example.com/id/asset/abc',
      expectedType: 'meshant:Asset',
    });
    expect(mismatch).toBeNull();
  });
});

test.describe('sparqlResultHasExpectedTriple — triple presence (Phase 226 B5)', () => {
  test('results binding matching iri + rdf:type present → true', () => {
    const bindings = [
      {
        p: { type: 'uri', value: 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' },
        o: { type: 'uri', value: 'https://meshant.example.com/ontology#Asset' },
      },
    ];
    expect(sparqlResultHasExpectedTriple(bindings, {})).toBe(true);
  });

  test('empty bindings → false', () => {
    expect(sparqlResultHasExpectedTriple([], {})).toBe(false);
  });

  test('bindings without rdf:type → false when rdf:type is required', () => {
    const bindings = [
      {
        p: { type: 'uri', value: 'https://meshant.example.com/ontology#name' },
        o: { type: 'literal', value: 'My Asset' },
      },
    ];
    expect(sparqlResultHasExpectedTriple(bindings, { requireRdfType: true })).toBe(false);
  });

  test('non-rdf:type bindings pass when rdf:type is not required', () => {
    const bindings = [
      {
        p: { type: 'uri', value: 'https://meshant.example.com/ontology#name' },
        o: { type: 'literal', value: 'My Asset' },
      },
    ];
    expect(sparqlResultHasExpectedTriple(bindings, {})).toBe(true);
  });
});

// ------------------------- correlation-ID guard pure logic (Phase 226 B4)

function emptyCorrBuffer(): CorrelationBuffer {
  return { mismatches: [], missing: [] };
}

test.describe('generateCorrelationId — pure ID generator (Phase 226 B4)', () => {
  test('is a non-empty string', () => {
    const id = generateCorrelationId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(8);
  });

  test('two sequential calls produce distinct IDs', () => {
    const a = generateCorrelationId();
    const b = generateCorrelationId();
    expect(a).not.toBe(b);
  });

  test('has an e2e-recognizable prefix for grep-ability', () => {
    const id = generateCorrelationId();
    expect(id.startsWith('e2e-')).toBe(true);
  });
});

test.describe('isCorrelationGuardDisabled — env-var kill switch (Phase 226 B4)', () => {
  test('true for "true"', () => {
    expect(isCorrelationGuardDisabled({ E2E_DISABLE_CORRELATION_GUARD: 'true' })).toBe(true);
  });

  test('true for "1"', () => {
    expect(isCorrelationGuardDisabled({ E2E_DISABLE_CORRELATION_GUARD: '1' })).toBe(true);
  });

  test('false for "false"', () => {
    expect(isCorrelationGuardDisabled({ E2E_DISABLE_CORRELATION_GUARD: 'false' })).toBe(false);
  });

  test('false for unset', () => {
    expect(isCorrelationGuardDisabled({})).toBe(false);
  });

  test('false for empty string', () => {
    expect(isCorrelationGuardDisabled({ E2E_DISABLE_CORRELATION_GUARD: '' })).toBe(false);
  });

  test('case-insensitive on "TRUE"', () => {
    expect(isCorrelationGuardDisabled({ E2E_DISABLE_CORRELATION_GUARD: 'TRUE' })).toBe(true);
  });
});

test.describe('evaluateCorrelationProblems — pure evaluator (Phase 226 B4)', () => {
  const opts = (allowMissing = false, disabled = false): CorrelationEvaluateOptions => ({
    allowMissing,
    guardDisabled: disabled,
  });

  test('empty buffer → no problems', () => {
    expect(evaluateCorrelationProblems(emptyCorrBuffer(), opts())).toEqual([]);
  });

  test('mismatch reported by default', () => {
    const buffer = emptyCorrBuffer();
    buffer.mismatches.push({ url: 'https://x/api', sent: 'e2e-1', echoed: 'other' });
    const problems = evaluateCorrelationProblems(buffer, opts());
    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain('correlation-id mismatch');
    expect(problems[0]).toContain('https://x/api');
    expect(problems[0]).toContain('e2e-1');
    expect(problems[0]).toContain('other');
  });

  test('missing header reported by default', () => {
    const buffer = emptyCorrBuffer();
    buffer.missing.push({ url: 'https://x/api', sent: 'e2e-2' });
    const problems = evaluateCorrelationProblems(buffer, opts());
    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain('missing');
    expect(problems[0]).toContain('https://x/api');
  });

  test('allow-missing opt-out suppresses missing-header problems only (not mismatches)', () => {
    const buffer = emptyCorrBuffer();
    buffer.missing.push({ url: 'https://x/api', sent: 'a' });
    buffer.mismatches.push({ url: 'https://x/b', sent: 'b', echoed: 'c' });
    const problems = evaluateCorrelationProblems(buffer, opts(true));
    expect(problems).toHaveLength(1);
    expect(problems[0]).toContain('mismatch');
  });

  test('guard-disabled (kill switch) → zero problems regardless of buffer contents', () => {
    const buffer = emptyCorrBuffer();
    buffer.missing.push({ url: 'https://x/api', sent: 'a' });
    buffer.mismatches.push({ url: 'https://x/b', sent: 'b', echoed: 'c' });
    expect(evaluateCorrelationProblems(buffer, opts(false, true))).toEqual([]);
  });

  test('multiple problems reported in deterministic order: mismatches then missing', () => {
    const buffer = emptyCorrBuffer();
    buffer.missing.push({ url: 'https://x/miss-1', sent: 'a' });
    buffer.missing.push({ url: 'https://x/miss-2', sent: 'b' });
    buffer.mismatches.push({ url: 'https://x/mm-1', sent: 'c', echoed: 'd' });
    const problems = evaluateCorrelationProblems(buffer, opts());
    expect(problems).toHaveLength(3);
    expect(problems[0]).toContain('mm-1');
    expect(problems[1]).toContain('miss-1');
    expect(problems[2]).toContain('miss-2');
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

// Integration check — exercise the actual guardedTest fixture wiring at
// least once so we catch any import-time breakage (e.g. a renamed export,
// a broken listener attach). Named `guardedTest` at import time to avoid
// shadowing the `test` symbol from '@playwright/test' used for the pure
// tests above. Intentionally scoped to "passes when nothing is wrong" —
// the failure modes are already covered by the pure evaluateGuard tests
// and a browser-level expected-failure test is fragile to diagnose
// separately from the guard itself.
guardedTest('guardedTest happy path: no pageerror / console.error / 5xx → test passes', async ({
  page,
  guard,
}) => {
  await page.goto('about:blank');
  // Sanity check that the fixture handed us a live buffer.
  expect(guard.pageErrors).toEqual([]);
  expect(guard.consoleErrors).toEqual([]);
  expect(guard.serverErrors).toEqual([]);
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 226.F4 — OpenAPI drift pure-logic tests.
// ─────────────────────────────────────────────────────────────────────────────

test.describe('openapiDrift.canonicalize — pure', () => {
  test('primitives pass through unchanged', () => {
    expect(canonicalize(null)).toBe(null);
    expect(canonicalize(42)).toBe(42);
    expect(canonicalize('hello')).toBe('hello');
    expect(canonicalize(true)).toBe(true);
  });

  test('arrays preserve order', () => {
    const out = canonicalize([3, 1, 2]) as number[];
    expect(out).toEqual([3, 1, 2]);
  });

  test('object keys sorted recursively', () => {
    const input = { b: 1, a: { z: 1, y: 2 } };
    const out = canonicalize(input);
    expect(JSON.stringify(out)).toBe('{"a":{"y":2,"z":1},"b":1}');
  });

  test('idempotent — canonical(canonical(x)) === canonical(x)', () => {
    const input = { z: { c: [3, 1], a: 1 }, m: 'hi' };
    const once = JSON.stringify(canonicalize(input));
    const twice = JSON.stringify(canonicalize(canonicalize(input)));
    expect(twice).toBe(once);
  });
});

test.describe('openapiDrift.hashCanonical — pure', () => {
  test('byte-identical objects produce identical hash regardless of key order', () => {
    const a = { foo: 1, bar: 2 };
    const b = { bar: 2, foo: 1 };
    expect(hashCanonical(a)).toBe(hashCanonical(b));
  });

  test('value change produces different hash', () => {
    expect(hashCanonical({ foo: 1 })).not.toBe(hashCanonical({ foo: 2 }));
  });

  test('returns lowercase hex of sha256 length 64', () => {
    expect(hashCanonical({ x: 1 })).toMatch(/^[0-9a-f]{64}$/);
  });
});

function buildMinimalSchema(extra?: Partial<OpenAPISchema>): OpenAPISchema {
  return {
    openapi: '3.0.3',
    info: { title: 'Test', version: '1.0.0', description: 'long marketing copy' },
    servers: [{ url: '/api/v1', description: 'Server' }],
    paths: {
      '/items/': {
        get: {
          operationId: 'list_items',
          parameters: [
            { name: 'q', in: 'query', required: false, schema: { type: 'string' } },
            { name: 'cursor', in: 'query', required: false, schema: { type: 'string' } },
          ],
          responses: {
            '200': {
              description: 'OK',
              content: {
                'application/json': { schema: { $ref: '#/components/schemas/ItemList' } },
              },
            },
          },
        },
      },
    },
    components: {
      schemas: {
        Item: {
          type: 'object',
          required: ['id', 'name'],
          properties: {
            id: { type: 'string', format: 'uuid' },
            name: { type: 'string' },
            archived: { type: 'boolean' },
          },
        },
        ItemList: {
          type: 'object',
          required: ['results'],
          properties: {
            results: { type: 'array', items: { $ref: '#/components/schemas/Item' } },
            cursor: { type: 'string', nullable: true },
          },
        },
      },
    },
    ...extra,
  };
}

test.describe('openapiDrift.extractSchemaShape — pure', () => {
  test('captures openapi + apiVersion + path × method', () => {
    const shape = extractSchemaShape(buildMinimalSchema());
    expect(shape.openapi).toBe('3.0.3');
    expect(shape.apiVersion).toBe('1.0.0');
    expect(Object.keys(shape.paths)).toEqual(['/items/']);
    expect(Object.keys(shape.paths['/items/'])).toEqual(['get']);
  });

  test('captures parameters (sorted by `${in}:${name}`)', () => {
    const shape = extractSchemaShape(buildMinimalSchema());
    expect(shape.paths['/items/'].get.parameters).toEqual([
      { name: 'cursor', in: 'query', required: false, type: 'string' },
      { name: 'q', in: 'query', required: false, type: 'string' },
    ]);
  });

  test('captures response refs by status code', () => {
    const shape = extractSchemaShape(buildMinimalSchema());
    expect(shape.paths['/items/'].get.responses['200']).toEqual({
      contentTypes: ['application/json'],
      ref: '#/components/schemas/ItemList',
    });
  });

  test('captures component property names + types + required-set', () => {
    const shape = extractSchemaShape(buildMinimalSchema());
    expect(shape.components.Item.type).toBe('object');
    expect(shape.components.Item.properties).toEqual([
      { name: 'archived', type: 'boolean', required: false, ref: undefined },
      { name: 'id', type: 'string', required: true, ref: undefined },
      { name: 'name', type: 'string', required: true, ref: undefined },
    ]);
  });

  test('discards info.description / servers from shape', () => {
    const a = buildMinimalSchema({
      info: { title: 'A', version: '1.0.0', description: 'one' },
      servers: [{ url: '/api/a' }],
    });
    const b = buildMinimalSchema({
      info: { title: 'B', version: '1.0.0', description: 'two' },
      servers: [{ url: '/api/b' }],
    });
    expect(JSON.stringify(extractSchemaShape(a))).toBe(JSON.stringify(extractSchemaShape(b)));
  });

  test('totals are accurate', () => {
    const shape = extractSchemaShape(buildMinimalSchema());
    expect(shape.totals).toEqual({ paths: 1, operations: 1, components: 2 });
  });

  test('non-HTTP keys on path-item (parameters, summary) are skipped', () => {
    const schema: OpenAPISchema = {
      openapi: '3.0.3',
      paths: {
        '/x/': {
          summary: 'shared',
          parameters: [{ name: 'p', in: 'path', required: true, schema: { type: 'string' } }],
          get: { responses: { '200': { description: 'OK' } } },
        },
      },
    };
    const shape = extractSchemaShape(schema);
    expect(shape.totals.operations).toBe(1);
    expect(Object.keys(shape.paths['/x/'])).toEqual(['get']);
  });
});

function shapeOf(schema: OpenAPISchema): SchemaShape {
  return extractSchemaShape(schema);
}

test.describe('openapiDrift.diffShapes — categorisation', () => {
  test('identical schemas produce empty diff', () => {
    expect(diffShapes(shapeOf(buildMinimalSchema()), shapeOf(buildMinimalSchema()))).toEqual([]);
  });

  test('removed path emits REMOVED-PATH', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    delete next.paths!['/items/'];
    expect(diffShapes(a, shapeOf(next))).toContain('REMOVED-PATH: /items/');
  });

  test('added path emits ADDED-PATH', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    next.paths!['/users/'] = { get: { responses: { '200': { description: 'OK' } } } };
    expect(diffShapes(a, shapeOf(next))).toContain('ADDED-PATH: /users/');
  });

  test('removed operation emits REMOVED-OP', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    next.paths!['/items/'] = { post: { responses: { '201': { description: 'Created' } } } };
    const diff = diffShapes(a, shapeOf(next));
    expect(diff).toContain('REMOVED-OP: GET /items/');
    expect(diff).toContain('ADDED-OP: POST /items/');
  });

  test('parameter type change emits PARAM-TYPE-CHANGED', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    (next.paths!['/items/'].get as Record<string, unknown>).parameters = [
      { name: 'q', in: 'query', required: false, schema: { type: 'integer' } },
      { name: 'cursor', in: 'query', required: false, schema: { type: 'string' } },
    ];
    expect(diffShapes(a, shapeOf(next))).toContain(
      'PARAM-TYPE-CHANGED: GET /items/ (query:q): string → integer',
    );
  });

  test('parameter newly-required emits PARAM-REQUIRED', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    (next.paths!['/items/'].get as Record<string, unknown>).parameters = [
      { name: 'q', in: 'query', required: true, schema: { type: 'string' } },
      { name: 'cursor', in: 'query', required: false, schema: { type: 'string' } },
    ];
    expect(diffShapes(a, shapeOf(next))).toContain(
      'PARAM-REQUIRED: GET /items/ (query:q) became required',
    );
  });

  test('component property removal emits REMOVED-PROPERTY', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    next.components!.schemas!.Item = {
      type: 'object',
      required: ['id', 'name'],
      properties: { id: { type: 'string' }, name: { type: 'string' } },
    };
    expect(diffShapes(a, shapeOf(next))).toContain('REMOVED-PROPERTY: Item.archived');
  });

  test('property newly-required emits PROPERTY-NEWLY-REQUIRED', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    next.components!.schemas!.Item = {
      type: 'object',
      required: ['id', 'name', 'archived'],
      properties: {
        id: { type: 'string', format: 'uuid' },
        name: { type: 'string' },
        archived: { type: 'boolean' },
      },
    };
    expect(diffShapes(a, shapeOf(next))).toContain(
      'PROPERTY-NEWLY-REQUIRED: Item.archived became required',
    );
  });

  test('property type change emits PROPERTY-TYPE-CHANGED', () => {
    const a = shapeOf(buildMinimalSchema());
    const next = buildMinimalSchema();
    next.components!.schemas!.Item = {
      type: 'object',
      required: ['id', 'name'],
      properties: {
        id: { type: 'integer' },
        name: { type: 'string' },
        archived: { type: 'boolean' },
      },
    };
    expect(diffShapes(a, shapeOf(next))).toContain(
      'PROPERTY-TYPE-CHANGED: Item.id: string → integer',
    );
  });
});

test.describe('openapiDrift.classifyDiff — breaking vs non-breaking', () => {
  test('REMOVED-* + PARAM-TYPE-CHANGED count as breaking', () => {
    const result = classifyDiff([
      'REMOVED-PATH: /a',
      'PARAM-TYPE-CHANGED: GET /b (query:q): string → integer',
      'PROPERTY-NEWLY-REQUIRED: Item.archived became required',
      'ADDED-PATH: /c',
      'PARAM-ADDED: POST /d (query:r)',
    ]);
    expect(result.breaking).toEqual([
      'REMOVED-PATH: /a',
      'PARAM-TYPE-CHANGED: GET /b (query:q): string → integer',
      'PROPERTY-NEWLY-REQUIRED: Item.archived became required',
    ]);
    expect(result.nonBreaking).toEqual(['ADDED-PATH: /c', 'PARAM-ADDED: POST /d (query:r)']);
  });

  test('empty input → empty buckets', () => {
    expect(classifyDiff([])).toEqual({ breaking: [], nonBreaking: [] });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 226.F3 — Refresh-race state machine pure-logic tests.
// ─────────────────────────────────────────────────────────────────────────────

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (v: T) => void;
  reject: (e: unknown) => void;
} {
  let resolve: (v: T) => void = () => {};
  let reject: (e: unknown) => void = () => {};
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

test.describe('RefreshRaceState — pure', () => {
  test('single caller resolves to the refresher value', async () => {
    const state = new RefreshRaceState(async () => 'fresh-token');
    expect(await state.run()).toBe('fresh-token');
    expect(state.refreshInvocations).toBe(1);
    expect(state.successCount).toBe(1);
    expect(state.failureCount).toBe(0);
    expect(state.isInFlight).toBe(false);
  });

  test('two concurrent callers share ONE refresh', async () => {
    const d = deferred<string>();
    const state = new RefreshRaceState(() => d.promise);
    const a = state.run();
    const b = state.run();
    expect(state.refreshInvocations).toBe(1);
    expect(state.isInFlight).toBe(true);
    d.resolve('shared-token');
    expect(await a).toBe('shared-token');
    expect(await b).toBe('shared-token');
    expect(state.refreshInvocations).toBe(1);
  });

  test('after settle, next run() starts a new refresh', async () => {
    let n = 0;
    const state = new RefreshRaceState(async () => `tok-${++n}`);
    expect(await state.run()).toBe('tok-1');
    expect(await state.run()).toBe('tok-2');
    expect(state.refreshInvocations).toBe(2);
  });

  test('rejection propagates to ALL concurrent callers', async () => {
    const d = deferred<string>();
    const state = new RefreshRaceState(() => d.promise);
    const a = state.run();
    const b = state.run();
    d.reject(new Error('refresh blew up'));
    await expect(a).rejects.toThrow('refresh blew up');
    await expect(b).rejects.toThrow('refresh blew up');
    expect(state.failureCount).toBe(1);
    expect(state.isInFlight).toBe(false);
  });

  test('failed cycle does not poison the state', async () => {
    let n = 0;
    const state = new RefreshRaceState(async () => {
      n++;
      if (n === 1) throw new Error('first cycle fails');
      return `tok-${n}`;
    });
    await expect(state.run()).rejects.toThrow('first cycle fails');
    expect(await state.run()).toBe('tok-2');
    expect(state.refreshInvocations).toBe(2);
  });
});

test.describe('decidePost401 — pure decision table', () => {
  test('refresh succeeded → retry', () => {
    expect(decidePost401({ canRefresh: true, refreshOk: true })).toEqual({ kind: 'retry' });
  });

  test('refresh failed → redirect-to-login + clearTokens', () => {
    expect(decidePost401({ canRefresh: true, refreshOk: false })).toEqual({
      kind: 'redirect-to-login',
      clearTokens: true,
    });
  });

  test('cannot refresh → redirect-to-login', () => {
    expect(decidePost401({ canRefresh: false, refreshOk: false })).toEqual({
      kind: 'redirect-to-login',
      clearTokens: true,
    });
  });

  test('canRefresh=false beats refreshOk=true', () => {
    expect(decidePost401({ canRefresh: false, refreshOk: true })).toEqual({
      kind: 'redirect-to-login',
      clearTokens: true,
    });
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Phase 226.F5 — Axe-audit pure-logic tests.
// ─────────────────────────────────────────────────────────────────────────────

function violation(impact: AxeViolation['impact'], id: string, html?: string): AxeViolation {
  return {
    id,
    impact,
    description: `desc-${id}`,
    nodes: html ? [{ html, target: ['div'], failureSummary: '' }] : [],
  };
}

test.describe('axeAudit.filterByImpact — pure', () => {
  test('returns only matching impact', () => {
    const all: AxeViolation[] = [
      violation('serious', 'a'),
      violation('minor', 'b'),
      violation('serious', 'c'),
      violation('critical', 'd'),
    ];
    expect(filterByImpact(all, 'serious').map((v) => v.id)).toEqual(['a', 'c']);
    expect(filterByImpact(all, 'critical').map((v) => v.id)).toEqual(['d']);
    expect(filterByImpact(all, 'moderate')).toEqual([]);
  });

  test('null impact is excluded from every bucket', () => {
    const all: AxeViolation[] = [{ id: 'x', impact: null, nodes: [] }];
    expect(filterByImpact(all, 'serious')).toEqual([]);
    expect(filterByImpact(all, 'critical')).toEqual([]);
  });
});

test.describe('axeAudit.summarizeViolations — pure', () => {
  test('zero violations produces a single-line clean message', () => {
    const audit: AxeAuditResult = {
      label: 'home',
      totalCount: 0,
      critical: [],
      serious: [],
      moderate: [],
      minor: [],
      raw: [],
    };
    expect(summarizeViolations(audit)).toBe('[a11y:home] no violations.');
  });

  test('multi-violation message lists impact + id + node preview', () => {
    const v1 = violation('serious', 'color-contrast', '<button class="btn">Click</button>');
    const v2 = violation('minor', 'image-alt');
    const audit: AxeAuditResult = {
      label: 'asset-form',
      totalCount: 2,
      critical: [],
      serious: [v1],
      moderate: [],
      minor: [v2],
      raw: [v1, v2],
    };
    const out = summarizeViolations(audit);
    expect(out).toContain('[a11y:asset-form] 2 violation(s)');
    expect(out).toContain('serious=1');
    expect(out).toContain('color-contrast');
    expect(out).toContain('Click');
    expect(out).toContain('image-alt');
  });

  test('nodes beyond maxNodes are truncated with a "more" line', () => {
    const v: AxeViolation = {
      id: 'x',
      impact: 'serious',
      description: 'desc',
      nodes: [
        { html: '<a>1</a>' },
        { html: '<a>2</a>' },
        { html: '<a>3</a>' },
        { html: '<a>4</a>' },
        { html: '<a>5</a>' },
      ],
    };
    const audit: AxeAuditResult = {
      label: 't',
      totalCount: 1,
      critical: [],
      serious: [v],
      moderate: [],
      minor: [],
      raw: [v],
    };
    const out = summarizeViolations(audit, 2);
    expect(out).toContain('and 3 more node(s)');
  });
});

test.describe('axeAudit.expectNoSeriousViolations — pure gate', () => {
  test('passes when critical AND serious empty', () => {
    const audit: AxeAuditResult = {
      label: 'ok',
      totalCount: 1,
      critical: [],
      serious: [],
      moderate: [violation('moderate', 'x')],
      minor: [],
      raw: [violation('moderate', 'x')],
    };
    expect(() => expectNoSeriousViolations(audit)).not.toThrow();
  });

  test('throws when serious is non-empty', () => {
    const v = violation('serious', 'color-contrast');
    const audit: AxeAuditResult = {
      label: 'bad',
      totalCount: 1,
      critical: [],
      serious: [v],
      moderate: [],
      minor: [],
      raw: [v],
    };
    expect(() => expectNoSeriousViolations(audit)).toThrow(/color-contrast/);
  });

  test('throws when critical is non-empty (regardless of serious)', () => {
    const v = violation('critical', 'aria-required-attr');
    const audit: AxeAuditResult = {
      label: 'bad',
      totalCount: 1,
      critical: [v],
      serious: [],
      moderate: [],
      minor: [],
      raw: [v],
    };
    expect(() => expectNoSeriousViolations(audit)).toThrow(/aria-required-attr/);
  });
});

// ----------------------------------------------------- createdResources tracker (Phase 226 E2)
//
// `createdResources` is wired as an auto-fixture on `guardedTest`, so a bug
// in the dedup / order / teardown-request logic would leak rows on every
// passing spec. These pure-logic tests pin the contract without booting
// a backend.

import {
  createRegistry as createCreatedResourcesRegistry,
  groupByOwner as groupCreatedByOwner,
  orderResources as orderCreatedResources,
  teardownAll as teardownCreatedResourcesAll,
  teardownRequestFor as teardownCreatedRequestFor,
  type CreatedResource,
  type CreatedResourcesRegistry,
} from './fixtures/createdResources';

const stubOwner = (email = 'a@b.test') => ({ email, password: 'pw' }) as never;

test.describe('createdResources — track / dedup (Phase 226 E2)', () => {
  test('track adds a resource and is observable via snapshot', () => {
    const r: CreatedResourcesRegistry = createCreatedResourcesRegistry();
    r.track({ type: 'asset', id: 'a1', owner: stubOwner() });
    expect(r.snapshot()).toEqual([
      { type: 'asset', id: 'a1', owner: stubOwner() },
    ]);
  });

  test('track is idempotent on the same {type,id}', () => {
    const r = createCreatedResourcesRegistry();
    r.track({ type: 'asset', id: 'a1', owner: stubOwner() });
    r.track({ type: 'asset', id: 'a1', owner: stubOwner('other@b.test') });
    const snap = r.snapshot();
    expect(snap).toHaveLength(1);
    expect(snap[0].owner.email).toBe('a@b.test');
  });

  test('different types with same id coexist', () => {
    const r = createCreatedResourcesRegistry();
    r.track({ type: 'asset',   id: 'x', owner: stubOwner() });
    r.track({ type: 'dataset', id: 'x', owner: stubOwner() });
    expect(r.snapshot()).toHaveLength(2);
  });

  test('runId is stable across calls within a registry', () => {
    const r = createCreatedResourcesRegistry();
    expect(r.runId).toBe(r.runId);
    expect(r.runId).toMatch(/^[0-9a-f-]{36}$/i);
  });
});

test.describe('createdResources — orderResources (Phase 226 E2)', () => {
  test('orders for FK-safe teardown: order → dataset → listing → contract → asset → user', () => {
    const input: CreatedResource[] = [
      { type: 'user',     id: 'u', owner: stubOwner() },
      { type: 'asset',    id: 'a', owner: stubOwner() },
      { type: 'order',    id: 'o', owner: stubOwner() },
      { type: 'contract', id: 'c', owner: stubOwner() },
      { type: 'listing',  id: 'l', owner: stubOwner() },
      { type: 'dataset',  id: 'd', owner: stubOwner() },
    ];
    const ordered = orderCreatedResources(input);
    expect(ordered.map((r) => r.type)).toEqual([
      'order', 'dataset', 'listing', 'contract', 'asset', 'user',
    ]);
  });

  test('does not mutate the input', () => {
    const input: CreatedResource[] = [
      { type: 'asset', id: 'a', owner: stubOwner() },
      { type: 'order', id: 'o', owner: stubOwner() },
    ];
    const before = input.map((r) => r.type);
    orderCreatedResources(input);
    expect(input.map((r) => r.type)).toEqual(before);
  });
});

test.describe('createdResources — groupByOwner (Phase 226 E2)', () => {
  test('groups by owner.email, preserves order within group', () => {
    const a1 = { type: 'asset', id: 'a1', owner: stubOwner('a@x') } as CreatedResource;
    const a2 = { type: 'asset', id: 'a2', owner: stubOwner('a@x') } as CreatedResource;
    const b1 = { type: 'asset', id: 'b1', owner: stubOwner('b@x') } as CreatedResource;
    const groups = groupCreatedByOwner([a1, b1, a2]);
    expect(Array.from(groups.keys())).toEqual(['a@x', 'b@x']);
    expect(groups.get('a@x')).toEqual([a1, a2]);
    expect(groups.get('b@x')).toEqual([b1]);
  });

  test('empty input returns an empty map', () => {
    expect(groupCreatedByOwner([]).size).toBe(0);
  });
});

test.describe('createdResources — teardownRequestFor (Phase 226 E2)', () => {
  const apiBase = 'http://localhost:8000/api/v1';
  test('asset → DELETE /assets/<id>/', () => {
    expect(teardownCreatedRequestFor({ type: 'asset', id: 'a1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'DELETE', url: `${apiBase}/assets/a1/` });
  });
  test('dataset → DELETE /datasets/<id>/', () => {
    expect(teardownCreatedRequestFor({ type: 'dataset', id: 'd1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'DELETE', url: `${apiBase}/datasets/d1/` });
  });
  test('listing → DELETE /marketplace/listings/<id>/', () => {
    expect(teardownCreatedRequestFor({ type: 'listing', id: 'l1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'DELETE', url: `${apiBase}/marketplace/listings/l1/` });
  });
  test('order → POST /marketplace/orders/<id>/cancel/ (preserves audit trail)', () => {
    expect(teardownCreatedRequestFor({ type: 'order', id: 'o1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'POST', url: `${apiBase}/marketplace/orders/o1/cancel/` });
  });
  test('contract → DELETE /contracts/<id>/', () => {
    expect(teardownCreatedRequestFor({ type: 'contract', id: 'c1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'DELETE', url: `${apiBase}/contracts/c1/` });
  });
  test('user → DELETE /users/<id>/', () => {
    expect(teardownCreatedRequestFor({ type: 'user', id: 'u1', owner: stubOwner() }, apiBase))
      .toEqual({ method: 'DELETE', url: `${apiBase}/users/u1/` });
  });
  test('trailing slash on apiBase is normalized', () => {
    expect(teardownCreatedRequestFor({ type: 'asset', id: 'a', owner: stubOwner() }, `${apiBase}/`))
      .toEqual({ method: 'DELETE', url: `${apiBase}/assets/a/` });
  });
});

test.describe('createdResources — teardownAll (Phase 226 E2)', () => {
  test('counts succeed/attempted; treats 404 as success (already gone)', async () => {
    const calls: { url: string; method: string }[] = [];
    const fetchImpl = (async (url: string, init: { method: string }) => {
      calls.push({ url, method: init.method });
      const status = url.includes('/a-missing/') ? 404 : 204;
      return { ok: status >= 200 && status < 300, status, text: async () => '' } as Response;
    }) as unknown as typeof fetch;
    const loginImpl = async () => ({ access_token: 'tok' });
    const result = await teardownCreatedResourcesAll(
      [
        { type: 'asset', id: 'a-ok',     owner: stubOwner() },
        { type: 'asset', id: 'a-missing', owner: stubOwner() },
      ],
      { fetchImpl, loginImpl, env: {} },
    );
    expect(result).toEqual({ attempted: 2, succeeded: 2, failures: [] });
    expect(calls).toHaveLength(2);
    expect(calls.every((c) => c.method === 'DELETE')).toBe(true);
  });

  test('non-OK / non-404 → recorded as failure with response body', async () => {
    const fetchImpl = (async () => ({
      ok: false,
      status: 500,
      text: async () => 'boom',
    } as Response)) as unknown as typeof fetch;
    const loginImpl = async () => ({ access_token: 'tok' });
    const result = await teardownCreatedResourcesAll(
      [{ type: 'asset', id: 'a1', owner: stubOwner() }],
      { fetchImpl, loginImpl, env: {} },
    );
    expect(result.attempted).toBe(1);
    expect(result.succeeded).toBe(0);
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0]).toContain('asset/a1');
    expect(result.failures[0]).toContain('500');
    expect(result.failures[0]).toContain('boom');
  });

  test('re-login failure for one owner does NOT block other owners', async () => {
    const fetchImpl = (async () => ({
      ok: true, status: 204, text: async () => '',
    } as Response)) as unknown as typeof fetch;
    const loginImpl = async (email: string) => {
      if (email === 'bad@x') throw new Error('credentials rejected');
      return { access_token: 'tok' };
    };
    const result = await teardownCreatedResourcesAll(
      [
        { type: 'asset', id: 'a-bad', owner: stubOwner('bad@x') },
        { type: 'asset', id: 'a-ok',  owner: stubOwner('good@x') },
      ],
      { fetchImpl, loginImpl, env: {} },
    );
    expect(result.failures).toHaveLength(1);
    expect(result.failures[0]).toContain('re-login failed for owner bad@x');
    expect(result.attempted).toBe(1);
    expect(result.succeeded).toBe(1);
  });

  test('flush() empties the registry so repeat flush is a no-op', async () => {
    const fetchImpl = (async () => ({
      ok: true, status: 204, text: async () => '',
    } as Response)) as unknown as typeof fetch;
    const loginImpl = async () => ({ access_token: 'tok' });
    const r = createCreatedResourcesRegistry({ fetchImpl, loginImpl, env: {} });
    r.track({ type: 'asset', id: 'a1', owner: stubOwner() });
    const first = await r.flush();
    expect(first.attempted).toBe(1);
    const second = await r.flush();
    expect(second).toEqual({ attempted: 0, succeeded: 0, failures: [] });
  });
});

// ----------------------------------------------------- uiCreateHelpers — URL parser (Phase 226 E2)

import { extractResourceIdFromUrl } from './fixtures/uiCreateHelpers';

test.describe('extractResourceIdFromUrl — UI redirect ID parser (Phase 226 E2)', () => {
  test('parses a UUID from /assets/<id>', () => {
    expect(extractResourceIdFromUrl(
      'https://stagingmeshant-internal.example.com/assets/abc-123-def-456',
      '/assets',
    )).toBe('abc-123-def-456');
  });

  test('parses a slug id from /contracts/<slug>', () => {
    expect(extractResourceIdFromUrl(
      'http://localhost:5173/contracts/my-contract-key',
      '/contracts',
    )).toBe('my-contract-key');
  });

  test('handles trailing slash, query, and hash', () => {
    expect(extractResourceIdFromUrl('https://x/assets/abc/', '/assets')).toBe('abc');
    expect(extractResourceIdFromUrl('https://x/assets/abc?tab=overview', '/assets')).toBe('abc');
    expect(extractResourceIdFromUrl('https://x/assets/abc#section', '/assets')).toBe('abc');
  });

  test('returns null when path does not match resource', () => {
    expect(extractResourceIdFromUrl('https://x/datasets/xyz', '/assets')).toBeNull();
  });

  test('rejects reserved sub-route segments masquerading as IDs', () => {
    expect(extractResourceIdFromUrl('https://x/assets/create', '/assets')).toBeNull();
    expect(extractResourceIdFromUrl('https://x/assets/edit', '/assets')).toBeNull();
    expect(extractResourceIdFromUrl('https://x/assets/import', '/assets')).toBeNull();
  });

  test('handles URL-encoded id segment by decoding', () => {
    expect(extractResourceIdFromUrl('https://x/assets/abc%20def', '/assets')).toBe('abc def');
  });

  test('returns null on non-string inputs', () => {
    expect(extractResourceIdFromUrl(null as unknown as string, '/assets')).toBeNull();
    expect(extractResourceIdFromUrl('https://x/assets/abc', null as unknown as string)).toBeNull();
  });

  test('normalises leading/trailing slash on resourcePath', () => {
    expect(extractResourceIdFromUrl('https://x/assets/abc', 'assets')).toBe('abc');
    expect(extractResourceIdFromUrl('https://x/assets/abc', '/assets/')).toBe('abc');
  });
});

// ----------------------------------------------------- disposableTenant (Phase 226 E6)

import {
  resolveApiBase as resolveDispApiBase,
  ephemeralTenantUrl,
  cascadeDeleteTenantUrl,
  buildTenantName,
  parseEphemeralTenantResponse,
  provisionTenant,
  cascadeDeleteTenant,
} from './fixtures/disposableTenant';

test.describe('disposableTenant — URL builders (Phase 226 E6)', () => {
  test('ephemeralTenantUrl appends /tenants/ephemeral/', () => {
    expect(ephemeralTenantUrl('http://localhost:8000/api/v1'))
      .toBe('http://localhost:8000/api/v1/tenants/ephemeral/');
  });
  test('ephemeralTenantUrl normalises trailing slash', () => {
    expect(ephemeralTenantUrl('http://localhost:8000/api/v1/'))
      .toBe('http://localhost:8000/api/v1/tenants/ephemeral/');
  });
  test('cascadeDeleteTenantUrl includes ?cascade=true', () => {
    expect(cascadeDeleteTenantUrl('http://x/api/v1', 't1'))
      .toBe('http://x/api/v1/tenants/t1/?cascade=true');
  });
});

test.describe('disposableTenant — resolveApiBase (Phase 226 E6)', () => {
  test('prefers E2E_API_BASE_URL when set', () => {
    expect(resolveDispApiBase({ E2E_API_BASE_URL: 'http://x/api' })).toBe('http://x/api');
  });
  test('falls back to VITE_PROXY_TARGET + /api/v1', () => {
    expect(resolveDispApiBase({ VITE_PROXY_TARGET: 'http://y:8000' }))
      .toBe('http://y:8000/api/v1');
  });
  test('falls back to absolute VITE_API_BASE_URL', () => {
    expect(resolveDispApiBase({ VITE_API_BASE_URL: 'http://z/api/v1' }))
      .toBe('http://z/api/v1');
  });
  test('defaults to localhost:8000 when nothing is set', () => {
    expect(resolveDispApiBase({})).toBe('http://localhost:8000/api/v1');
  });
  test('uses port 8001 when E2E_WEB_PORT is set', () => {
    expect(resolveDispApiBase({ E2E_WEB_PORT: '5173' }))
      .toBe('http://localhost:8001/api/v1');
  });
});

test.describe('disposableTenant — buildTenantName (Phase 226 E6)', () => {
  test('embeds slot, first 8 chars of run-id, clock, and rand for traceability', () => {
    const name = buildTenantName({
      runId: 'abcdef1234-rest',
      slot: 'A',
      now: () => 1700000000000,
      rand: () => 'deadbeef',
    });
    expect(name).toBe('e2e-tenant-A-abcdef12-1700000000000-deadbeef');
  });
  test('produces e2e- prefix so the staging prefix-purge cron sweeps leaks', () => {
    const name = buildTenantName({
      runId: 'r', slot: 'B', now: () => 1, rand: () => 'x',
    });
    expect(name.startsWith('e2e-')).toBe(true);
  });
});

test.describe('disposableTenant — parseEphemeralTenantResponse (Phase 226 E6)', () => {
  const valid = {
    id: 't1',
    name: 'e2e-tenant-A-x',
    admin_user: { id: 'u1', email: 'a@x.test', password: 'pw' },
  };

  test('accepts a well-shaped response', () => {
    const t = parseEphemeralTenantResponse(valid);
    expect(t.id).toBe('t1');
    expect(t.admin.email).toBe('a@x.test');
    expect(t.admin.password).toBe('pw');
    expect(t.admin.id).toBe('u1');
  });

  test('rejects missing id', () => {
    expect(() => parseEphemeralTenantResponse({ ...valid, id: undefined }))
      .toThrow(/missing or non-string `id`/);
  });

  test('rejects missing admin_user', () => {
    expect(() => parseEphemeralTenantResponse({ id: 't', name: 'n' }))
      .toThrow(/missing `admin_user`/);
  });

  test('rejects admin_user missing password', () => {
    const bad = { ...valid, admin_user: { id: 'u', email: 'a@x' } };
    expect(() => parseEphemeralTenantResponse(bad))
      .toThrow(/admin_user missing id\/email\/password/);
  });

  test('rejects null payload', () => {
    expect(() => parseEphemeralTenantResponse(null))
      .toThrow(/not an object/);
  });
});

test.describe('disposableTenant — provisionTenant (Phase 226 E6)', () => {
  test('happy path: returns parsed tenant with admin credentials', async () => {
    const fetchImpl = (async () => ({
      ok: true,
      status: 201,
      json: async () => ({
        id: 't-new',
        name: 'e2e-tenant-A-rid-1-x',
        admin_user: { id: 'u-new', email: 'admin@x.test', password: 'gen-pw' },
      }),
      text: async () => '',
    } as Response)) as unknown as typeof fetch;
    const t = await provisionTenant('A', 'rrr', { fetchImpl, env: {} });
    expect(t.id).toBe('t-new');
    expect(t.admin.password).toBe('gen-pw');
  });

  test('404 throws an actionable error pointing at OQ4', async () => {
    const fetchImpl = (async () => ({
      ok: false, status: 404, text: async () => '', json: async () => ({}),
    } as Response)) as unknown as typeof fetch;
    await expect(provisionTenant('A', 'rid', { fetchImpl, env: {} }))
      .rejects.toThrow(/Phase 226 OQ4/);
  });

  test('5xx surfaces status + body in the error', async () => {
    const fetchImpl = (async () => ({
      ok: false, status: 500, text: async () => 'boom', json: async () => ({}),
    } as Response)) as unknown as typeof fetch;
    await expect(provisionTenant('A', 'rid', { fetchImpl, env: {} }))
      .rejects.toThrow(/500/);
  });

  test('sends X-E2E-Token header when env var present', async () => {
    let captured: Record<string, string> = {};
    const fetchImpl = (async (_url: string, init: { headers?: Record<string, string> }) => {
      captured = init.headers ?? {};
      return {
        ok: true, status: 201,
        json: async () => ({
          id: 't', name: 'n', admin_user: { id: 'u', email: 'a@x', password: 'p' },
        }),
        text: async () => '',
      } as Response;
    }) as unknown as typeof fetch;
    await provisionTenant('A', 'rid', { fetchImpl, env: { E2E_TEST_TOKEN: 'sekret' } });
    expect(captured['x-e2e-token']).toBe('sekret');
  });
});

test.describe('disposableTenant — cascadeDeleteTenant (Phase 226 E6)', () => {
  test('200/204 → ok', async () => {
    const fetchImpl = (async () => ({
      ok: true, status: 204, text: async () => '',
    } as Response)) as unknown as typeof fetch;
    expect(await cascadeDeleteTenant('t', 'tok', { fetchImpl, env: {} }))
      .toEqual({ ok: true });
  });
  test('404 → ok (already gone)', async () => {
    const fetchImpl = (async () => ({
      ok: false, status: 404, text: async () => '',
    } as Response)) as unknown as typeof fetch;
    expect(await cascadeDeleteTenant('t', 'tok', { fetchImpl, env: {} }))
      .toEqual({ ok: true });
  });
  test('5xx → not ok with reason', async () => {
    const fetchImpl = (async () => ({
      ok: false, status: 500, text: async () => 'nope',
    } as Response)) as unknown as typeof fetch;
    const r = await cascadeDeleteTenant('t', 'tok', { fetchImpl, env: {} });
    expect(r.ok).toBe(false);
    expect(r.reason).toContain('500');
    expect(r.reason).toContain('nope');
  });
  test('thrown fetch → not ok with reason (never throws)', async () => {
    const fetchImpl = (async () => { throw new Error('econn'); }) as unknown as typeof fetch;
    const r = await cascadeDeleteTenant('t', 'tok', { fetchImpl, env: {} });
    expect(r.ok).toBe(false);
    expect(r.reason).toContain('econn');
  });
});

// ----------------------------------------------------------------------
// Phase 226 G16 — security-header guard pure helpers.
// ----------------------------------------------------------------------

test.describe('isDocumentResponseForSecurityGuard — content-type heuristic', () => {
  test('text/html content-type → in scope', () => {
    expect(isDocumentResponseForSecurityGuard('https://x/y', 'text/html')).toBe(true);
    expect(isDocumentResponseForSecurityGuard('https://x/y', 'text/html; charset=utf-8')).toBe(true);
  });
  test('application/json → out of scope', () => {
    expect(isDocumentResponseForSecurityGuard('https://x/y', 'application/json')).toBe(false);
  });
  test('text/css and image content-types → out of scope', () => {
    expect(isDocumentResponseForSecurityGuard('https://x/y.css', 'text/css')).toBe(false);
    expect(isDocumentResponseForSecurityGuard('https://x/y.png', 'image/png')).toBe(false);
  });
  test('no content-type, route-shaped path → in scope', () => {
    // SPA shells frequently arrive without Content-Type in test stacks.
    expect(isDocumentResponseForSecurityGuard('https://x/login', undefined)).toBe(true);
    expect(isDocumentResponseForSecurityGuard('https://x/', undefined)).toBe(true);
  });
  test('no content-type, asset-shaped path (extension) → out of scope', () => {
    expect(isDocumentResponseForSecurityGuard('https://x/main.js', undefined)).toBe(false);
    expect(isDocumentResponseForSecurityGuard('https://x/style.css', undefined)).toBe(false);
  });
  test('non-URL string → out of scope (defensive)', () => {
    expect(isDocumentResponseForSecurityGuard('not a url', undefined)).toBe(false);
  });
});

test.describe('hasSecurityHeaderEvidence — env detection signal', () => {
  test('CSP enforce header present → evidence', () => {
    expect(hasSecurityHeaderEvidence({ 'content-security-policy': "default-src 'self'" })).toBe(true);
  });
  test('CSP report-only present → evidence (rollout state)', () => {
    expect(hasSecurityHeaderEvidence({ 'content-security-policy-report-only': 'x' })).toBe(true);
  });
  test('X-Frame-Options alone → evidence', () => {
    expect(hasSecurityHeaderEvidence({ 'x-frame-options': 'DENY' })).toBe(true);
  });
  test('Strict-Transport-Security alone → evidence', () => {
    expect(hasSecurityHeaderEvidence({ 'strict-transport-security': 'max-age=31536000' })).toBe(true);
  });
  test('mixed-case header names → evidence (case insensitive)', () => {
    expect(hasSecurityHeaderEvidence({ 'Content-Security-Policy': "default-src 'self'" })).toBe(true);
  });
  test('only X-Content-Type-Options nosniff → NOT evidence (too easy to set in app code)', () => {
    // X-Content-Type-Options often set by application code without nginx;
    // alone it doesn't prove the env enforces full security headers.
    expect(hasSecurityHeaderEvidence({ 'x-content-type-options': 'nosniff' })).toBe(false);
  });
  test('only Referrer-Policy → NOT evidence', () => {
    expect(hasSecurityHeaderEvidence({ 'referrer-policy': 'strict-origin' })).toBe(false);
  });
  test('empty headers → no evidence', () => {
    expect(hasSecurityHeaderEvidence({})).toBe(false);
  });
  test('empty header value → no evidence', () => {
    expect(hasSecurityHeaderEvidence({ 'content-security-policy': '' })).toBe(false);
  });
});

test.describe('evaluateSecurityHeaders — branch coverage', () => {
  const fullySafeHeaders: Record<string, string> = {
    'content-security-policy':
      "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'",
    'x-frame-options': 'DENY',
    'x-content-type-options': 'nosniff',
    'referrer-policy': 'strict-origin-when-cross-origin',
    'strict-transport-security': 'max-age=31536000; includeSubDomains',
  };

  test('compliant HTTPS response → no problems', () => {
    const out = evaluateSecurityHeaders('https://x/login', fullySafeHeaders, true);
    expect(out).toEqual([]);
  });

  test('compliant HTTP response → no problems (HSTS not required)', () => {
    const headers = { ...fullySafeHeaders };
    delete headers['strict-transport-security'];
    const out = evaluateSecurityHeaders('http://x/login', headers, false);
    expect(out).toEqual([]);
  });

  test('missing CSP → missing-header problem', () => {
    const headers = { ...fullySafeHeaders };
    delete headers['content-security-policy'];
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'missing-header' && p.detail.includes('content-security-policy'))).toBe(true);
  });

  test('missing HSTS on HTTPS → missing-header problem', () => {
    const headers = { ...fullySafeHeaders };
    delete headers['strict-transport-security'];
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.detail.includes('strict-transport-security'))).toBe(true);
  });

  test('Report-Only present without enforce → csp-report-only', () => {
    const headers: Record<string, string> = {
      ...fullySafeHeaders,
      'content-security-policy-report-only': 'x',
    };
    delete headers['content-security-policy'];
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'csp-report-only')).toBe(true);
  });

  test("script-src 'unsafe-eval' → flagged", () => {
    const headers = {
      ...fullySafeHeaders,
      'content-security-policy': "default-src 'self'; script-src 'self' 'unsafe-eval'",
    };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'csp-allows-unsafe-eval')).toBe(true);
  });

  test("script-src 'unsafe-inline' → flagged", () => {
    const headers = {
      ...fullySafeHeaders,
      'content-security-policy': "default-src 'self'; script-src 'self' 'unsafe-inline'",
    };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'csp-allows-unsafe-inline-script')).toBe(true);
  });

  test('X-Content-Type-Options other than nosniff → flagged', () => {
    const headers = { ...fullySafeHeaders, 'x-content-type-options': 'noop' };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'x-content-type-options-not-nosniff')).toBe(true);
  });

  test('X-Frame-Options ALLOWALL → flagged', () => {
    const headers = { ...fullySafeHeaders, 'x-frame-options': 'ALLOWALL' };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'x-frame-options-not-deny-or-sameorigin')).toBe(true);
  });

  test('X-Frame-Options SAMEORIGIN → not flagged', () => {
    const headers = { ...fullySafeHeaders, 'x-frame-options': 'SAMEORIGIN' };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out.some((p) => p.reason === 'x-frame-options-not-deny-or-sameorigin')).toBe(false);
  });

  test('mixed-case header names compared case-insensitively', () => {
    const headers: Record<string, string> = {
      'Content-Security-Policy': "default-src 'self'; script-src 'self'",
      'X-Frame-Options': 'DENY',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'strict-origin',
      'Strict-Transport-Security': 'max-age=31536000',
    };
    const out = evaluateSecurityHeaders('https://x/', headers, true);
    expect(out).toEqual([]);
  });
});

test.describe('isSecurityHeaderGuardDisabled — env-var kill switch', () => {
  test('unset → false', () => {
    expect(isSecurityHeaderGuardDisabled({})).toBe(false);
  });
  test('explicit "true" → true', () => {
    expect(isSecurityHeaderGuardDisabled({ E2E_DISABLE_SECURITY_HEADER_GUARD: 'true' })).toBe(true);
  });
  test('explicit "1" → true', () => {
    expect(isSecurityHeaderGuardDisabled({ E2E_DISABLE_SECURITY_HEADER_GUARD: '1' })).toBe(true);
  });
  test('"TRUE" (uppercase) → true', () => {
    expect(isSecurityHeaderGuardDisabled({ E2E_DISABLE_SECURITY_HEADER_GUARD: 'TRUE' })).toBe(true);
  });
  test('explicit "false" → false', () => {
    expect(isSecurityHeaderGuardDisabled({ E2E_DISABLE_SECURITY_HEADER_GUARD: 'false' })).toBe(false);
  });
  test('whitespace trimmed', () => {
    expect(isSecurityHeaderGuardDisabled({ E2E_DISABLE_SECURITY_HEADER_GUARD: '  true  ' })).toBe(true);
  });
});
