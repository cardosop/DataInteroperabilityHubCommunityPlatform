/**
 * Dimension: Idempotency — asset create round-trip (Phase 226 G10b).
 *
 * Counterpart to G10a (marketplace purchase). HTTP ``Idempotency-Key`` on
 * ``POST /api/v1/*`` is owned by the project-wide
 * ``hub.apps.api.middleware.idempotency.IdempotencyMiddleware``. This spec
 * validates the asset-create endpoint as observed end-to-end:
 *
 *   * Replay with same key + same body → original response (200/201) with
 *     ``Idempotency-Replayed: true`` header, same asset id.
 *   * Replay with same key + DIFFERENT body → 409 with code
 *     ``IDEMPOTENCY_CONFLICT``.
 *   * Without the header, behaviour is unchanged (each call creates a new
 *     asset, or the second 409s on ``Asset.key`` uniqueness).
 *   * Malformed key (too short / control chars) → 400 with code
 *     ``INVALID_IDEMPOTENCY_KEY``.
 *
 * Backend unit + integration coverage of the same matrix lives at
 * ``hub/apps/assets/tests/test_idempotency.py`` and
 * ``hub/apps/api/tests/test_idempotency.py`` (the middleware itself).
 *
 * Key format constraint (validate_idempotency_key): UUID OR 8-256 chars
 * of alphanumeric + hyphen/underscore/slash. We use UUID-suffixed keys
 * to satisfy the validator.
 *
 * No mocks. Real backend.
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '../fixtures/guardedTest';
import { getTestUser } from '../fixtures/auth';

const API_BASE = '/api/v1';

interface AssetCreateResult {
  status: number;
  body: { id?: string; key?: string; name?: string; error?: unknown; [k: string]: unknown };
  replayHeader: string | undefined;
}

/**
 * Extract the error code from the middleware's nested envelope:
 *
 *     {"error": {"code": "...", "message": "...", "http_status": ...}}
 *
 * Tolerates the flat-envelope variant (DRF view-level errors) just in
 * case the middleware ever pivots to that shape.
 */
function readErrorCode(body: AssetCreateResult['body']): string | undefined {
  if (typeof body.error === 'object' && body.error !== null) {
    const inner = body.error as { code?: unknown };
    if (typeof inner.code === 'string') return inner.code;
  }
  if (typeof (body as { code?: unknown }).code === 'string') {
    return (body as { code?: string }).code;
  }
  return undefined;
}

async function attemptCreate(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  token: string,
  payload: Record<string, unknown>,
  idempotencyKey?: string,
): Promise<AssetCreateResult> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
  if (idempotencyKey !== undefined) {
    headers['Idempotency-Key'] = idempotencyKey;
  }
  const res = await page.request.post(`${API_BASE}/assets/`, {
    headers,
    data: payload,
  });
  const status = res.status();
  let body: AssetCreateResult['body'] = {};
  try {
    body = (await res.json()) as AssetCreateResult['body'];
  } catch {
    // some 5xx return non-JSON; leave body empty
  }
  // The middleware emits ``Idempotency-Replayed: true`` (header name
  // normalised to lowercase by Playwright's headers() accessor).
  return {
    status,
    body,
    replayHeader: res.headers()['idempotency-replayed'],
  };
}

async function login(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  email: string,
  password: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email, password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

function uniqueAssetKey(prefix = 'idem-asset'): string {
  return `${prefix}-${Date.now()}-${randomUUID().slice(0, 8)}`;
}

/** Middleware-acceptable idempotency key (UUID4, 36 chars, in the allowed
 * UUID branch of ``validate_idempotency_key``). */
function idempotencyKey(): string {
  return randomUUID();
}

test.describe('Dimension: Asset-create idempotency', () => {
  test.setTimeout(120_000);

  test('replay with same Idempotency-Key returns original asset id', async ({ page }) => {
    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);

    const idemKey = idempotencyKey();
    const payload = {
      key: uniqueAssetKey(),
      name: 'Idem Asset',
      description: 'E2E G10b — replay test',
      visibility: 'INTERNAL',
    };

    const first = await attemptCreate(page, token, payload, idemKey);
    if (first.status === 404) {
      test.skip(
        true,
        'POST /api/v1/assets/ returned 404 — endpoint not enabled on this environment',
      );
    }
    expect(first.status, `first create body: ${JSON.stringify(first.body)}`).toBe(201);
    const firstId = first.body.id;
    expect(firstId).toBeTruthy();

    // Tiny pause so the middleware's Redis write completes before the replay.
    await page.waitForTimeout(150);

    const replay = await attemptCreate(page, token, payload, idemKey);
    // The middleware preserves the original status code on replay.
    expect([200, 201]).toContain(replay.status);
    expect(
      replay.body.id,
      `replay must equal first id (got ${replay.body.id})`,
    ).toBe(firstId);
    expect(
      replay.replayHeader,
      'replay response must carry Idempotency-Replayed: true',
    ).toBe('true');
  });

  test('same Idempotency-Key with different payload returns 409 IDEMPOTENCY_CONFLICT', async ({
    page,
  }) => {
    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);

    const idemKey = idempotencyKey();
    const original = {
      key: uniqueAssetKey('idem-mm'),
      name: 'Original',
      visibility: 'INTERNAL',
    };
    const first = await attemptCreate(page, token, original, idemKey);
    if (first.status === 404) {
      test.skip(true, 'POST /api/v1/assets/ unavailable in this environment');
    }
    expect(first.status).toBe(201);

    // Same key, MUTATED body. MUST 409 with IDEMPOTENCY_CONFLICT.
    const mutated = await attemptCreate(
      page,
      token,
      { ...original, name: 'Mutated' },
      idemKey,
    );
    expect(mutated.status).toBe(409);
    expect(readErrorCode(mutated.body), JSON.stringify(mutated.body)).toBe(
      'IDEMPOTENCY_CONFLICT',
    );
  });

  test('omitting Idempotency-Key preserves original (non-idempotent) behaviour', async ({
    page,
  }) => {
    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);

    const payloadA = {
      key: uniqueAssetKey('no-idem-a'),
      name: 'No Idem A',
      visibility: 'INTERNAL',
    };
    const payloadB = {
      key: uniqueAssetKey('no-idem-b'),
      name: 'No Idem B',
      visibility: 'INTERNAL',
    };
    const a = await attemptCreate(page, token, payloadA);
    if (a.status === 404) {
      test.skip(true, 'POST /api/v1/assets/ unavailable in this environment');
    }
    const b = await attemptCreate(page, token, payloadB);
    expect(a.status).toBe(201);
    expect(b.status).toBe(201);
    expect(a.body.id).not.toBe(b.body.id);
    // Neither response should carry the replay marker.
    expect(a.replayHeader).toBeFalsy();
    expect(b.replayHeader).toBeFalsy();
  });

  test('malformed Idempotency-Key returns 400 INVALID_IDEMPOTENCY_KEY', async ({ page }) => {
    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);

    const payload = {
      key: uniqueAssetKey('bad-idem'),
      name: 'Bad Idem',
      visibility: 'INTERNAL',
    };
    // Too short — the middleware key format requires UUID OR 8-256 chars.
    // "abc" is 3 chars and not a UUID.
    const res = await attemptCreate(page, token, payload, 'abc');
    if (res.status === 404) {
      test.skip(true, 'POST /api/v1/assets/ unavailable in this environment');
    }
    expect(res.status).toBe(400);
    expect(readErrorCode(res.body), JSON.stringify(res.body)).toBe(
      'INVALID_IDEMPOTENCY_KEY',
    );
  });
});
