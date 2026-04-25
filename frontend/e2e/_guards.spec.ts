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
  canonicalIriFor,
  classifyDereferenceResponse,
  validateJsonLdPayload,
  sparqlResultHasExpectedTriple,
} from './fixtures/verifySemantic';
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
