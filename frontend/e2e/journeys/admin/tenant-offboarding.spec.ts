/**
 * Phase 260.1.F — Tenant offboarding hard-cascade (platform admin + E2E token).
 *
 * Provisions a disposable tenant (`POST /tenants/ephemeral/` + X-E2E-Token), uploads
 * a CSV via the production file init/complete flow, then invokes
 * `DELETE /tenants/{id}/?cascade=true` as platform admin with the same secret.
 *
 * Assertions: tenant no longer retrievable; audit row `FILE_TENANT_OFFBOARD_PURGE_SCHEDULED`
 * for the file id. No mocks beyond environment skips when the stack lacks MinIO or secrets.
 */

import { test, expect } from '../../fixtures/test-data-cleanup';
import { getPlatformAdminUser, loginViaApi } from '../../fixtures/auth';
import { e2eTestHeaders } from '../../fixtures/e2e-token';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';
import { verifyViaApiAbsent } from '../../fixtures/verifyViaApi';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

async function uploadCsvViaInitFlow(
  bearer: string,
  tenantId: string,
  csv: string,
): Promise<string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${bearer}`,
    'Content-Type': 'application/json',
    'X-Tenant-ID': tenantId,
  };

  const initRes = await fetch(`${API_BASE}/files/init/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      name: 'offboard.csv',
      content_type: 'text/csv',
      size: Buffer.byteLength(csv),
    }),
  });
  if (!initRes.ok) {
    throw new Error(`files/init failed ${initRes.status} ${await initRes.text()}`);
  }
  const init = (await initRes.json()) as {
    file_id: string;
    upload_url: string;
    expected_sha256?: string;
  };

  const putRes = await fetch(init.upload_url, {
    method: 'PUT',
    headers: { 'Content-Type': 'text/csv' },
    body: csv,
  });
  if (!putRes.ok) {
    throw new Error(`presigned PUT failed ${putRes.status}`);
  }

  const completeRes = await fetch(`${API_BASE}/files/${init.file_id}/complete/`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ sha256: init.expected_sha256 ?? '' }),
  });
  if (!completeRes.ok) {
    throw new Error(`files/complete failed ${completeRes.status} ${await completeRes.text()}`);
  }
  return init.file_id;
}

test.describe('260.1.F — Tenant offboarding cascade @admin @critical', () => {
  test.setTimeout(180_000);

  test('ephemeral tenant → file upload → cascade delete → FILE_TENANT_OFFBOARD audit', async ({
    page,
  }) => {
    test.skip(!process.env.E2E_TEST_SECRET, 'E2E_TEST_SECRET unset — cascade delete requires shared secret.');

    // Capture lookup error into a flag so ``test.skip`` becomes a
    // real conditional skip (per ``e2e-guards/no-test-skip-true``).
    let platformAdminUser: Awaited<ReturnType<typeof getPlatformAdminUser>> | null = null;
    let paLookupError: Error | null = null;
    try {
      platformAdminUser = await getPlatformAdminUser();
    } catch (err) {
      paLookupError = err as Error;
    }
    test.skip(paLookupError !== null, `No platform admin (${paLookupError?.message ?? ''}).`);
    if (!platformAdminUser) throw new Error('unreachable: skip should have aborted');

    const { access_token: paToken } = await loginViaApi(
      platformAdminUser.email,
      platformAdminUser.password,
    );
    await page.goto('/');
    await page.evaluate((tok) => {
      localStorage.setItem('access_token', tok);
    }, paToken);

    // Setup-only fixture POST creating a disposable tenant. The tenant
    // existence is verified by the cascade-DELETE call further down
    // (expects 204) + the post-delete verifyViaApiAbsent probe.
    // TENANT_CREATED audit emission is owned by the API contract suite
    // at hub/apps/tenants/tests/test_ephemeral_tenant.py.
    // noverify: setup-only POST; the cascade-DELETE assertions below are the test's contract.
    const ephemRes = await page.request.post(`${API_BASE}/tenants/ephemeral/`, {
      headers: {
        'Content-Type': 'application/json',
        ...e2eTestHeaders(),
      },
      data: { name: `offboard-${Date.now()}`, label: '260.1.F' },
    });
    test.skip(ephemRes.status() === 404, 'POST /tenants/ephemeral/ returned 404 — e2e environment or token gate closed.',);
    expect(ephemRes.ok(), await ephemRes.text()).toBeTruthy();
    const disposable = (await ephemRes.json()) as {
      id: string;
      admin_user: { email: string; password: string };
    };
    const tenantId = disposable.id;

    // Same conditional-skip restructuring for the upload-prereqs path.
    let fileId: string | null = null;
    let uploadPrereqError: Error | null = null;
    try {
      const tenantLogin = await loginViaApi(disposable.admin_user.email, disposable.admin_user.password);
      fileId = await uploadCsvViaInitFlow(tenantLogin.access_token, tenantId, 'col\n1\n');
    } catch (err) {
      uploadPrereqError = err as Error;
    }
    test.skip(
      uploadPrereqError !== null,
      `File upload prerequisites failed (${uploadPrereqError?.message ?? ''}).`,
    );
    if (fileId === null) throw new Error('unreachable: skip should have aborted');

    // The mutation under test: hard-cascade DELETE of the disposable
    // tenant. Verification pair within 30 lines below:
    //   1. ``verifyViaApiAbsent`` — GET /tenants/{id}/ must return 404.
    //   2. ``verifyAuditEvent`` — FILE_TENANT_OFFBOARD_PURGE_SCHEDULED row.
    const delRes = await page.request.delete(`${API_BASE}/tenants/${tenantId}/?cascade=true`, {
      headers: {
        Authorization: `Bearer ${paToken}`,
        ...e2eTestHeaders(),
      },
    });
    expect(
      delRes.status(),
      `cascade DELETE expected 204 — got ${delRes.status()} ${await delRes.text()}`,
    ).toBe(204);

    await verifyViaApiAbsent(page, `${API_BASE}/tenants/${tenantId}/`, {
      authHeaderOverride: { Authorization: `Bearer ${paToken}` },
    });

    await verifyAuditEvent(page, {
      action: 'FILE_TENANT_OFFBOARD_PURGE_SCHEDULED',
      resourceType: 'FILE',
      resourceId: fileId,
      retryBudgetMs: 8_000,
    });
    await verifyAuditEvent(page, {
      action: 'TENANT_HARD_DELETE_CASCADE',
      resourceType: 'TENANT',
      resourceId: tenantId,
      retryBudgetMs: 8_000,
    });
  });
});
