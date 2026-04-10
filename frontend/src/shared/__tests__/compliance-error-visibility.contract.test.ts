/**
 * Phase 213.G.15 — fixture-based contract check.
 *
 * Verifies that `waitForComplianceRunViaApi` populates the new error
 * fields (`error`, `errorType`, `errorCode`) from the serializer payload
 * when they are present, and that `expectComplianceRunSucceeded` produces
 * a one-shot diagnosable failure message instead of the historical bare
 * `"Status was 'FAILED'"` form.
 *
 * No network: global fetch is stubbed with deterministic JSON fixtures.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  expectComplianceRunSucceeded,
  waitForComplianceRunViaApi,
} from '../../../e2e/fixtures/api-compliance';

const FAKE_USER = {
  email: 'cpo@example.test',
  password: 'irrelevant',
  tenantId: 't1',
  role: 'CPO',
} as unknown as Parameters<typeof waitForComplianceRunViaApi>[0];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  }) as unknown as Response;
}

describe('waitForComplianceRunViaApi — error visibility (Phase 213.G.10/G.15)', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockReset();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('populates error + errorType from regulation_mapping_json on REMOTE_FAILURE', async () => {
    fetchMock
      // login
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'tok' }))
      // poll → terminal FAILED with persisted error fields
      .mockResolvedValueOnce(
        jsonResponse(200, {
          status: 'FAILED',
          regulation_mapping_json: {
            error: 'scan worker crashed: KeyError tenant_id',
            error_type: 'REMOTE_FAILURE',
          },
          metadata_json: null,
        })
      );

    const result = await waitForComplianceRunViaApi(FAKE_USER, 'run-1', 5_000);

    expect(result.status).toBe('FAILED');
    expect(result.error).toBe('scan worker crashed: KeyError tenant_id');
    expect(result.errorType).toBe('REMOTE_FAILURE');
    expect(result.errorCode).toBeUndefined();
  });

  it('populates errorCode from metadata_json on POLL_TIMEOUT', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'tok' }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          status: 'FAILED',
          regulation_mapping_json: null,
          metadata_json: { error_code: 'POLL_TIMEOUT' },
        })
      );

    const result = await waitForComplianceRunViaApi(FAKE_USER, 'run-2', 5_000);
    expect(result.status).toBe('FAILED');
    expect(result.errorCode).toBe('POLL_TIMEOUT');
    expect(result.error).toBeUndefined();
  });

  it('does not populate error fields on a clean SUCCEEDED run', async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(200, { access_token: 'tok' }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          status: 'SUCCEEDED',
          regulation_mapping_json: { GDPR: { articles: ['Art. 6'] } },
          metadata_json: { job_id: 'remote-1' },
        })
      );

    const result = await waitForComplianceRunViaApi(FAKE_USER, 'run-3', 5_000);
    expect(result.status).toBe('SUCCEEDED');
    expect(result.error).toBeUndefined();
    expect(result.errorType).toBeUndefined();
    expect(result.errorCode).toBeUndefined();
  });
});

describe('expectComplianceRunSucceeded — diagnosable failure messages (Phase 213.G.13)', () => {
  it('returns silently on SUCCEEDED', () => {
    expect(() =>
      expectComplianceRunSucceeded({ status: 'SUCCEEDED' })
    ).not.toThrow();
  });

  it('throws with status + error_type + error on REMOTE_FAILURE', () => {
    expect(() =>
      expectComplianceRunSucceeded(
        {
          status: 'FAILED',
          error: 'boom upstream',
          errorType: 'REMOTE_FAILURE',
        },
        'ctx'
      )
    ).toThrow(/status=FAILED.*error_type=REMOTE_FAILURE.*error=boom upstream/);
  });

  it('throws with error_code when only metadata_json populated', () => {
    expect(() =>
      expectComplianceRunSucceeded({
        status: 'FAILED',
        errorType: 'POLL_TIMEOUT',
        errorCode: 'POLL_TIMEOUT',
      })
    ).toThrow(/error_code=POLL_TIMEOUT/);
  });

  it('flags backend invariant violation when no error fields are present', () => {
    expect(() =>
      expectComplianceRunSucceeded({ status: 'FAILED' })
    ).toThrow(/invariant violated/);
  });
});
