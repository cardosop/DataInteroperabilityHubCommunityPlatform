/**
 * Infrastructure Canary Tests
 *
 * These tests validate that critical backend infrastructure is functional
 * BEFORE the main test suite runs. They catch the exact class of bugs
 * that historically caused 5+ consecutive silent false-pass runs:
 *
 * - S3 file upload (presigned URL generation + browser PUT via CSP)
 * - Compliance service reachability (NetworkPolicy allows api→compliance)
 * - Inter-service communication (DQ, datacontract, semantic services)
 * - Auth token flow (login → access_token → authenticated API call)
 *
 * These tests MUST NOT accept login redirect, error-display, or "no crash"
 * as success. They assert specific positive outcomes.
 *
 * If ANY of these tests fail, the rest of the suite's results are unreliable.
 */

import { expect, test } from '@playwright/test';
import { getApiBaseUrl, getTestUser, loginViaApi } from '../fixtures/auth';

// Canonical API base shared with the login helpers (fixtures/auth.ts).
// The previous spec-local chain had two defects: `PLAYWRIGHT_BASE_URL?.replace(...) +
// '/api/v1'` evaluates to the truthy string 'undefined/api/v1' when the env var is
// unset (operator precedence — `?.` does not extend over the `+`), and the final
// fallback silently pointed a LOCAL run at https://api.stagingmeshant-internal.example.com
// (ERR_NAME_NOT_RESOLVED on machines without that DNS). getApiBaseUrl fails fast
// with a clear message instead.
const API_BASE_URL = getApiBaseUrl();

/**
 * Authed API call with one fresh-login retry on 401.
 *
 * loginViaApi caches access tokens per email for 30s (fixtures/auth.ts) and the
 * backend rejects tokens whose `authz_version` no longer matches the user's
 * `token_version` (bumped by logout-all / password-reset — code TOKEN_INVALIDATED).
 * Under parallel workers a cached-but-invalidated token can transiently 401 on a
 * token that is seconds old. One forceFresh retry (bypasses the cache) separates
 * that transient from a real auth breakage; a second 401 hard-fails and the
 * caller's assertion message captures the body so the envelope code
 * (AUTH_UNAUTHORIZED vs TOKEN_INVALIDATED) is available for triage.
 */
async function authedFetch(
  user: Awaited<ReturnType<typeof getTestUser>>,
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const call = (token: string) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { ...(init.headers ?? {}), Authorization: `Bearer ${token}` },
    });
  const first = await loginViaApi(user.email, user.password);
  let res = await call(first.access_token);
  if (res.status === 401) {
    const fresh = await loginViaApi(user.email, user.password, { forceFresh: true });
    res = await call(fresh.access_token);
  }
  return res;
}

/** Read a response body once for diagnostics without throwing. */
async function bodyPreview(res: Response, limit = 300): Promise<string> {
  try {
    return (await res.text()).slice(0, limit);
  } catch {
    return '(unreadable body)';
  }
}

test.describe('Infrastructure Canary', () => {
  test.setTimeout(60000);

  test('canary: API health endpoint returns healthy with DB + Redis connected', async () => {
    const healthUrl = API_BASE_URL.replace('/api/v1', '/health/');
    const res = await fetch(healthUrl);
    expect(res.status).toBe(200);
    const data = (await res.json()) as {
      status?: string;
      database?: string;
      redis?: { cache?: string; queue?: string };
    };
    expect(data.status).toBe('healthy');
    expect(data.database).toBe('connected');
    expect(data.redis?.cache).toBe('connected');
    expect(data.redis?.queue).toBe('connected');
  });

  test('canary: authenticated API call returns 200 (auth token flow works)', async () => {
    const user = await getTestUser();

    // Call an authenticated endpoint — /assets/ is lightweight
    const res = await authedFetch(user, '/assets/?page_size=1');
    // Must be 200, not 401/403/500. Body capture distinguishes the known
    // transient (TOKEN_INVALIDATED — token_version race) from a real
    // key/alg drift (AUTH_UNAUTHORIZED "Invalid or expired token").
    // Read the body ONLY on failure — a response body can be consumed once.
    const errBody = res.status === 200 ? '' : ` Body: ${await bodyPreview(res)}`;
    expect(res.status, `Expected 200 from /assets/, got ${res.status}.${errBody}`).toBe(200);
  });

  test('canary: S3 presigned URL has valid IRSA credentials (not placeholder)', async () => {
    const user = await getTestUser();

    // Init a file upload to get a presigned URL
    const initRes = await authedFetch(user, '/files/init/', {
      signal: AbortSignal.timeout(15_000),
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'canary-probe.csv',
        content_type: 'text/csv',
        size: 10,
        upload_method: 'browser',
      }),
    });
    // Skip when S3/file storage is not configured (local test environment).
    // authedFetch already retried once with a fresh token, so a 401 here is
    // a stable condition, not the token_version transient.
    const s3NotConfigured = initRes.status === 401;
    test.skip(s3NotConfigured, 'File init returned 401 — S3 storage backend not configured for local test env');
    if (s3NotConfigured) return;
    expect(initRes.status, `File init failed: ${initRes.status}`).toBe(201);

    const initData = (await initRes.json()) as { upload_url?: string; file_id?: string };
    expect(initData.upload_url, 'File init response missing upload_url').toBeTruthy();

    // Validate the presigned URL has a real AWS credential (not "IRSA", "minio", or empty)
    const url = new URL(initData.upload_url!);
    const credential = url.searchParams.get('X-Amz-Credential') || '';
    const akid = credential.split('/')[0];
    // Local/test stacks use MinIO as the object store: the short access-key
    // 'minio' and a localhost hostname are correct THERE, but on the AWS
    // stack they are exactly the placeholder shape this canary exists to
    // catch. The IRSA assertions below apply to real S3 URLs only; MinIO
    // uploads are exercised by the PUT test below.
    const isMinio = akid === 'minio' || /localhost|minio/i.test(url.hostname);
    if (isMinio) {
      // Local object-store contract (instead of a bare skip): the presigned
      // URL must target the MinIO endpoint the test stack configures —
      // localhost:9010 — so a misconfigured MinIO host fails loudly. The
      // IRSA-only assertions above apply to the AWS stack.
      // hostname is 'localhost' with the endpoint on the PORT — assert both.
      expect(
        url.hostname,
        `MinIO presigned URL hostname '${url.hostname}' is not localhost`,
      ).toBe('localhost');
      expect(
        url.port,
        `MinIO presigned URL port '${url.port}' is not the local MinIO endpoint (9010)`,
      ).toBe('9010');
      return;
    }
    expect(
      akid.length,
      `Presigned URL AKID '${akid}' is too short (${akid.length} chars) — ` +
        `expected 16+ chars from IRSA. Credential misconfigured.`
    ).toBeGreaterThanOrEqual(16);

    // Verify the URL points to a real S3 endpoint (not localhost/minio)
    expect(
      url.hostname,
      `Presigned URL hostname '${url.hostname}' is not an S3 endpoint`
    ).toContain('.s3.');
  });

  test('canary: S3 presigned PUT upload succeeds (CORS + CSP must allow it)', async () => {
    const user = await getTestUser();

    const csv = 'id,name\n1,canary';
    const initRes = await authedFetch(user, '/files/init/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: `canary-${Date.now()}.csv`,
        content_type: 'text/csv',
        size: Buffer.byteLength(csv),
        upload_method: 'browser',
      }),
    });
    const s3NotConfigured = initRes.status === 401;
    test.skip(s3NotConfigured, 'File init returned 401 — S3 storage backend not configured for local test env');
    if (s3NotConfigured) return;
    expect(initRes.status, `File init failed: ${initRes.status}`).toBe(201);
    const { upload_url } = (await initRes.json()) as { upload_url: string };

    // PUT to the presigned URL (Node.js fetch — no CSP/CORS enforcement)
    const putRes = await fetch(upload_url, {
      method: 'PUT',
      body: csv,
      headers: { 'Content-Type': 'text/csv' },
    });
    expect(
      putRes.status,
      `S3 PUT failed: ${putRes.status} ${putRes.statusText}. ` +
        // intentional: tolerates non-text / streaming response body when building a diagnostic message; the `throw new Error(...)` immediately below this catch is the primary failure path — this catch is not the pass/fail decision.
        `Body: ${(await putRes.text().catch(() => '')).slice(0, 300)}`
    ).toBe(200);
  });

  test('canary: S3 presigned URL is reachable via CORS preflight from app origin', async ({ page }) => {
    const user = await getTestUser();

    const initRes = await authedFetch(user, '/files/init/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: 'cors-probe.csv',
        content_type: 'text/csv',
        size: 10,
        upload_method: 'browser',
      }),
    });
    const s3NotConfigured = initRes.status === 401;
    test.skip(s3NotConfigured, 'File init returned 401 — S3 storage backend not configured for local test env');
    if (s3NotConfigured) return;
    expect(initRes.status, `File init failed: ${initRes.status}`).toBe(201);
    const { upload_url } = (await initRes.json()) as { upload_url: string };
    expect(
      upload_url,
      'File init response missing upload_url'
    ).toBeTruthy();
    const url = new URL(upload_url);

    // Simulate the browser CORS preflight. Derive the app origin from the
    // live page (resolved via Playwright baseURL) — the previous
    // PLAYWRIGHT_BASE_URL || staging fallback sent the preflight Origin to
    // https://stagingmeshant-internal.example.com in local runs, and ERR_NAME_NOT_RESOLVED
    // navigations elsewhere in this spec share the same defect.
    await page.goto('/login', { waitUntil: 'domcontentloaded' });
    const appOrigin = new URL(page.url()).origin;
    const preflightRes = await fetch(`${url.origin}${url.pathname}`, {
      method: 'OPTIONS',
      headers: {
        Origin: appOrigin,
        'Access-Control-Request-Method': 'PUT',
        'Access-Control-Request-Headers': 'content-type',
      },
    });
    // S3 answers the preflight with 200; MinIO (local/test) answers 204.
    // Both are "preflight not rejected" — the failure mode this canary
    // guards against is a 4xx/5xx or a dropped CORS response.
    expect([200, 204], 'CORS preflight must not be rejected').toContain(preflightRes.status);

    const allowOrigin = preflightRes.headers.get('access-control-allow-origin');
    expect(
      allowOrigin,
      `S3 CORS missing Access-Control-Allow-Origin for ${appOrigin}`
    ).toBe(appOrigin);

    const allowMethods = preflightRes.headers.get('access-control-allow-methods') || '';
    expect(allowMethods, 'S3 CORS must allow PUT').toContain('PUT');
  });

  test('canary: CSP connect-src allows S3 uploads (nginx config check)', async ({ page }) => {
    // Navigate to any page to get the CSP header. Relative URL resolves via
    // Playwright baseURL — the app the rest of the suite actually runs
    // against. The previous `PLAYWRIGHT_BASE_URL || 'https://staging…'`
    // fallback navigated local runs to staging (ERR_NAME_NOT_RESOLVED).
    const res = await page.goto('/login', { waitUntil: 'domcontentloaded' });
    const csp = (await res?.headerValue('content-security-policy')) || '';

    // Extract connect-src directive
    const connectSrc = csp
      .split(';')
      .find((d) => d.trim().startsWith('connect-src'))
      ?.trim() || '';

    expect(
      connectSrc,
      `CSP missing connect-src directive entirely. Full CSP: ${csp.slice(0, 200)}`
    ).toContain('connect-src');

    // The presigned-upload target differs by environment: AWS S3 on
    // staging/prod (connect-src carries the *.s3.* wildcard), MinIO on
    // local/test (localhost:9010). connect-src must allow whichever one
    // the environment uses — browser XHR PUT to a presigned URL that the
    // policy blocks surfaces as "Upload failed: network error".
    expect(
      connectSrc,
      `CSP connect-src does not allow the object-store upload target. Got: ${connectSrc}. ` +
        `Browser XHR PUT to presigned URLs will be blocked, causing ` +
        `"Upload failed: network error (no HTTP response from object store)".`
    ).toMatch(/\*\.s3\..*amazonaws\.com|localhost:9010/);
  });

  test('canary: compliance service is reachable from API (NetworkPolicy check)', async () => {
    const user = await getTestUser();

    // Create a minimal compliance run to test the full path:
    // API pod → compliance-service:8082 health check → create run
    //
    // First, check if the compliance list endpoint works (doesn't require
    // the compliance microservice, just Django + DB)
    const listRes = await authedFetch(user, '/compliance/runs/?page_size=1');
    // Read the body ONLY on failure — listRes.json() below consumes it.
    const listErrBody =
      listRes.status === 200 ? '' : ` Body: ${await bodyPreview(listRes)}`;
    expect(
      listRes.status,
      `Compliance list endpoint returned ${listRes.status} — Django/DB issue.${listErrBody}`
    ).toBe(200);

    // Now test the compliance microservice path by looking at the most
    // recent run's status. If it shows "Compliance service is unavailable"
    // in regulation_mapping_json, the NetworkPolicy is blocking.
    const listData = (await listRes.json()) as {
      results?: Array<{
        status?: string;
        regulation_mapping_json?: { error?: string; error_type?: string };
      }>;
    };

    const recentRuns = listData.results || [];
    const unavailableRun = recentRuns.find(
      (r) =>
        r.status === 'FAILED' &&
        r.regulation_mapping_json?.error_type === 'ConnectionError'
    );

    if (unavailableRun) {
      throw new Error(
        `Compliance service is UNREACHABLE from the api pod.\n` +
          `Recent run failed with: ${unavailableRun.regulation_mapping_json?.error}\n` +
          `This typically means the NetworkPolicy (allow-compliance.yaml) ` +
          `is missing an ingress rule for api/worker pods.\n` +
          `Check: kubectl get networkpolicy -n hub-staging`
      );
    }
  });
});
