/**
 * close-test-coverage-gaps 4.4 — governance sub-route API seed helpers.
 *
 * The governance-sub-routes spec exercises the consent / dsar / dpia /
 * breach / processor surfaces against the REAL backend. The :id routes
 * (dsar detail, dpia review, breach detail) need a parent record first;
 * these helpers create one through the real wire API (no mocks, no
 * page.evaluate) using the authenticated handler endpoints.
 *
 * Follows the api-compliance.ts pattern: retrying API login, transient
 * connection-error backoff, and the shared API_BASE resolution.
 */

import type { TestUser } from '../setup/create-test-user';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

function isTransientConnectionError(err: unknown): boolean {
  const msg = err instanceof Error ? err.message : String(err);
  if (/fetch failed|terminated|network/i.test(msg)) return true;
  const cause = err && typeof err === 'object' && (err as { cause?: unknown }).cause;
  if (cause && typeof cause === 'object') {
    const c = cause as { code?: string; message?: string };
    if (c.code === 'ECONNRESET' || c.code === 'UND_ERR_SOCKET') return true;
  }
  return false;
}

const RETRIES = 5;
const RETRY_DELAYS_MS = [2000, 4000, 6000, 8000, 10000];

async function loginViaApiGovernance(user: TestUser): Promise<string> {
  for (let r = 0; r < RETRIES; r++) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: user.email, password: user.password }),
      });
      if (response.status === 429) {
        const retryAfter = parseInt(response.headers.get('retry-after') ?? '', 10);
        const backoffMs = retryAfter > 0 ? retryAfter * 1000 : RETRY_DELAYS_MS[Math.min(r, RETRY_DELAYS_MS.length - 1)];
        await new Promise((resolve) => setTimeout(resolve, backoffMs));
        continue;
      }
      if (response.status >= 500 && r < RETRIES - 1) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (!response.ok) {
        // intentional: tolerates non-text / streaming response body when
        // building a diagnostic message; the throw below is the primary
        // failure path — this catch is not the pass/fail decision.
        const body = await response.text().catch(() => '');
        throw new Error(`Governance API login failed: ${response.status} ${body}`);
      }
      const data = (await response.json()) as { access_token?: string };
      if (!data.access_token) throw new Error('Login response missing access_token');
      return data.access_token;
    } catch (err) {
      if (r < RETRIES - 1 && isTransientConnectionError(err)) {
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAYS_MS[r]));
        continue;
      }
      if (r >= RETRIES - 1) throw err;
    }
  }
  throw new Error('loginViaApiGovernance: exhausted retries');
}

interface ApiRequestOptions {
  /** Extra body fields merged into the JSON payload. */
  extra?: Record<string, unknown>;
}

async function apiRequest<T>(
  user: TestUser,
  method: 'GET' | 'POST',
  path: string,
  options: ApiRequestOptions = {},
  body: Record<string, unknown> = {}
): Promise<T> {
  const token = await loginViaApiGovernance(user);
  const payload = { ...body, ...(options.extra ?? {}) };
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: method === 'POST' ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    // intentional: tolerates non-text / streaming response body when
    // building a diagnostic message; the throw below is the primary
    // failure path — this catch is not the pass/fail decision.
    const bodyText = await response.text().catch(() => '');
    throw new Error(
      `Governance API ${method} ${path} failed: ${response.status} ${bodyText}`
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface ConsentPurposeSeed {
  key: string;
  name: string;
}

/** Create a tenant consent purpose (unique key per run — the model is
 *  unique-per-tenant on `key`). */
export async function createConsentPurposeViaApi(
  user: TestUser,
  purpose: ConsentPurposeSeed
): Promise<void> {
  await apiRequest<{ id: string }>(user, 'POST', '/consent/consent-purposes/', {}, {
    key: purpose.key,
    name: purpose.name,
    description: 'E2E governance sub-routes seed',
    is_active: true,
  });
}

/** Create a DSAR request via the authenticated handler endpoint
 *  (POST /dsar/requests/ — IsDsarHandler: TENANT_ADMIN/DPO/LEGAL_ADMIN).
 *  Returns the request id. */
export async function createDsarRequestViaApi(
  user: TestUser,
  subjectEmail: string
): Promise<string> {
  const row = await apiRequest<{ id: string }>(user, 'POST', '/dsar/requests/', {}, {
    request_type: 'ACCESS',
    subject_email: subjectEmail,
    subject_name: 'E2E DSAR Subject',
    regimes: ['GDPR'],
    verification_method: 'MANUAL_REVIEW',
  });
  if (!row.id) throw new Error('DSAR create response missing id');
  return row.id;
}

/** Create a DPIA draft and submit it for review — the record lands in
 *  the IN_REVIEW queue the review page/queue consume. Returns the id. */
export async function createDpiaInReviewViaApi(
  user: TestUser,
  title: string
): Promise<string> {
  const row = await apiRequest<{ id: string }>(user, 'POST', '/dpia/records/', {}, {
    title,
    regime: 'GDPR',
  });
  if (!row.id) throw new Error('DPIA create response missing id');
  await apiRequest<{ id: string }>(user, 'POST', `/dpia/records/${row.id}/submit/`);
  return row.id;
}

/** Create a breach incident via the authenticated incidents endpoint.
 *  Returns the incident id. */
export async function createBreachIncidentViaApi(
  user: TestUser,
  title: string
): Promise<string> {
  const row = await apiRequest<{ id: string }>(user, 'POST', '/breach/incidents/', {}, {
    title,
    summary: 'E2E governance sub-routes seed — no real PII.',
    regimes: ['GDPR'],
    discovered_at: new Date().toISOString(),
  });
  if (!row.id) throw new Error('Breach incident create response missing id');
  return row.id;
}
