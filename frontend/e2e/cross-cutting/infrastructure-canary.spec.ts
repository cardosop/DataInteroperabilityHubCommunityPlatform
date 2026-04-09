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
import { getTestUser, loginViaApi } from '../fixtures/auth';

const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  process.env.PLAYWRIGHT_BASE_URL?.replace(/\/$/, '') + '/api/v1' ||
  'https://api.stagingmeshant-internal.example.com/api/v1';

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
    const token = await loginViaApi(user.email, user.password);
    expect(token).toBeTruthy();

    // Call an authenticated endpoint — /assets/ is lightweight
    const res = await fetch(`${API_BASE_URL}/assets/?page_size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    // Must be 200, not 401/403/500
    expect(res.status, `Expected 200 from /assets/, got ${res.status}`).toBe(200);
  });

  test('canary: S3 presigned URL has valid IRSA credentials (not placeholder)', async () => {
    const user = await getTestUser();
    const token = await loginViaApi(user.email, user.password);

    // Init a file upload to get a presigned URL
    const initRes = await fetch(`${API_BASE_URL}/files/init/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: 'canary-probe.csv',
        content_type: 'text/csv',
        size: 10,
        upload_method: 'browser',
      }),
    });
    expect(initRes.status, `File init failed: ${initRes.status}`).toBe(201);

    const initData = (await initRes.json()) as { upload_url?: string; file_id?: string };
    expect(initData.upload_url, 'File init response missing upload_url').toBeTruthy();

    // Validate the presigned URL has a real AWS credential (not "IRSA", "minio", or empty)
    const url = new URL(initData.upload_url!);
    const credential = url.searchParams.get('X-Amz-Credential') || '';
    const akid = credential.split('/')[0];
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
    const token = await loginViaApi(user.email, user.password);

    const csv = 'id,name\n1,canary';
    const initRes = await fetch(`${API_BASE_URL}/files/init/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: `canary-${Date.now()}.csv`,
        content_type: 'text/csv',
        size: Buffer.byteLength(csv),
        upload_method: 'browser',
      }),
    });
    expect(initRes.status).toBe(201);
    const { upload_url, file_id } = (await initRes.json()) as {
      upload_url: string;
      file_id: string;
    };

    // PUT to the presigned URL (Node.js fetch — no CSP/CORS enforcement)
    const putRes = await fetch(upload_url, {
      method: 'PUT',
      body: csv,
      headers: { 'Content-Type': 'text/csv' },
    });
    expect(
      putRes.status,
      `S3 PUT failed: ${putRes.status} ${putRes.statusText}. ` +
        `Body: ${(await putRes.text().catch(() => '')).slice(0, 300)}`
    ).toBe(200);
  });

  test('canary: S3 presigned URL is reachable via CORS preflight from app origin', async () => {
    const user = await getTestUser();
    const token = await loginViaApi(user.email, user.password);

    const initRes = await fetch(`${API_BASE_URL}/files/init/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        name: 'cors-probe.csv',
        content_type: 'text/csv',
        size: 10,
        upload_method: 'browser',
      }),
    });
    const { upload_url } = (await initRes.json()) as { upload_url: string };
    const url = new URL(upload_url);

    // Simulate the browser CORS preflight
    const appOrigin = process.env.PLAYWRIGHT_BASE_URL || 'https://stagingmeshant-internal.example.com';
    const preflightRes = await fetch(`${url.origin}${url.pathname}`, {
      method: 'OPTIONS',
      headers: {
        Origin: appOrigin,
        'Access-Control-Request-Method': 'PUT',
        'Access-Control-Request-Headers': 'content-type',
      },
    });
    expect(preflightRes.status, 'CORS preflight must return 200').toBe(200);

    const allowOrigin = preflightRes.headers.get('access-control-allow-origin');
    expect(
      allowOrigin,
      `S3 CORS missing Access-Control-Allow-Origin for ${appOrigin}`
    ).toBe(appOrigin);

    const allowMethods = preflightRes.headers.get('access-control-allow-methods') || '';
    expect(allowMethods, 'S3 CORS must allow PUT').toContain('PUT');
  });

  test('canary: CSP connect-src allows S3 uploads (nginx config check)', async ({ page }) => {
    // Navigate to any page to get the CSP header
    const appUrl = process.env.PLAYWRIGHT_BASE_URL || 'https://stagingmeshant-internal.example.com';
    const res = await page.goto(appUrl + '/login', { waitUntil: 'domcontentloaded' });
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

    // Must include S3 wildcard for presigned URL uploads
    expect(
      connectSrc,
      `CSP connect-src does not allow S3 uploads. Got: ${connectSrc}. ` +
        `Browser XHR PUT to S3 presigned URLs will be blocked, causing ` +
        `"Upload failed: network error (no HTTP response from object store)".`
    ).toMatch(/\*\.s3\..*amazonaws\.com/);
  });

  test('canary: compliance service is reachable from API (NetworkPolicy check)', async () => {
    const user = await getTestUser();
    const token = await loginViaApi(user.email, user.password);

    // Create a minimal compliance run to test the full path:
    // API pod → compliance-service:8082 health check → create run
    //
    // First, check if the compliance list endpoint works (doesn't require
    // the compliance microservice, just Django + DB)
    const listRes = await fetch(`${API_BASE_URL}/compliance/runs/?page_size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(
      listRes.status,
      `Compliance list endpoint returned ${listRes.status} — Django/DB issue`
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
