/**
 * E2E Test: JOURNEY-DPO-001 — Fail-closed asset creation when tenant
 * has restricted data-storage policy
 *
 * Journey: DPO observes the platform refusing to create an Asset when
 * the tenant policy + the file payload combine to a compliance FAIL.
 * Persona: Data Protection Officer (DPO)
 * Reference: Phase 250.1.B.2 deliverable; ADR-AST-001
 *  (docs/adr/asset-creation/ADR-AST-001-fail-closed-asset-persistence.md);
 *  D250.2 fail-closed parity with User_Journeys.md:49-59.
 *
 * Success path: DPO creates a tenant with `allowed_to_store=False`,
 * uploads a file with PII, attempts to register it as an Asset via the
 * data-first endpoint, and sees:
 *   1. HTTP 4xx response (specifically 422 with code
 *      ASSET_FAIL_CLOSED_REJECTED).
 *   2. Zero Asset rows persisted for that tenant.
 *   3. UI shows the rejection reason + the linked compliance run id.
 *   4. ASSET_FAIL_CLOSED_REJECTED audit event visible in the audit log.
 *
 * Failure path: configuring a permissive tenant
 * (`compliance_fail_closed_enabled=False`) reverts to legacy semantics
 * — Asset persists in DRAFT with FAIL status. This is the 30-day soak
 * window per D250.12.
 *
 * Real backend only; no mocks. Uses asset-creation-fixtures.ts
 * (Phase 250.1.B.3 deliverable) for `seedFailClosedTenant`.
 */

import { expect, test } from '../../fixtures/test-data-cleanup';
import { getTestUser, gotoWithRetry, loginAsPersona } from '../../fixtures/auth';
import {
  isRemoteApiTarget,
  waitForAppMainReady,
  waitForLoadingComplete,
} from '../../fixtures/helpers';
import {
  seedFailClosedTenant,
  expectFailClosedRejection,
  expectAssetCountEquals,
  expectAuditEventEmitted,
} from '../../fixtures/asset-creation-fixtures';
import { verifyAuditEvent } from '../../fixtures/verifyAuditEvent';

// Phase 250.1.B.2 — poll budget for the workflow run state. The
// fail-closed path is short (no DQ scan; compliance returns FAIL fast),
// so 30s local / 60s remote is comfortable.
const WORKFLOW_POLL_TIMEOUT_MS = (() => {
  const override = parseInt(process.env.E2E_WORKFLOW_POLL_TIMEOUT_MS ?? '', 10);
  if (Number.isFinite(override) && override > 0) return override;
  return isRemoteApiTarget() ? 60_000 : 30_000;
})();

// Track fixtures created per-test so we can tear down the resources
// (tenant + file_id) that fall outside the framework cleanup
// registry's CleanupResourceType union per
// frontend/e2e/fixtures/test-data-cleanup.ts:49.
const _activeFixtures: Array<{ cleanupOrphans: () => Promise<void> }> = [];

test.afterEach(async () => {
  // Best-effort: process the fixtures created in this test in reverse
  // order. Errors are logged inside `cleanupOrphans` and don't fail
  // the test (the test result already reflects the assertions).
  while (_activeFixtures.length > 0) {
    const fixture = _activeFixtures.pop();
    if (fixture) await fixture.cleanupOrphans();
  }
});

test.describe('Phase 250.1.B.2 — DPO fail-closed asset creation', () => {
  test('refuses asset creation when compliance gate fails closed', async ({
    page,
    cleanup,
  }) => {
    // ── Arrange ────────────────────────────────────────────────────
    // Seed a tenant with `compliance_fail_closed_enabled=True` AND a
    // policy that produces compliance FAIL on the synthetic PII file.
    const fixture = await seedFailClosedTenant({
      cleanup,
      tenantPolicyAllowsStorage: false,
      complianceFailClosedEnabled: true,
    });
    _activeFixtures.push(fixture);

    // ── Act ────────────────────────────────────────────────────────
    // POST the data-first endpoint with a synthetic PII-laden file.
    const response = await fixture.attemptDataFirstAssetCreation({
      key: 'fail-closed-pii',
      name: 'PII Dataset (should be rejected)',
      // Synthetic file content carrying detectable PII signatures
      // (email + SSN-shaped digits). The real compliance scanner
      // running in staging detects these and returns FAIL.
      fileContent: 'name,ssn,email\nAlice,111-22-3333,alice@example.com\n',
    });

    // ── Assert: response shape ─────────────────────────────────────
    expectFailClosedRejection(response);

    // ── Assert: zero Asset rows persisted ──────────────────────────
    await expectAssetCountEquals(fixture, 'fail-closed-pii', 0);

    // ── Assert: workflow run lands in terminal FAILED state ────────
    if (response.body.workflow_run_id) {
      const finalState = await fixture.pollWorkflowRunUntilTerminal(
        response.body.workflow_run_id,
        { timeoutMs: WORKFLOW_POLL_TIMEOUT_MS },
      );
      expect(finalState).toBe('FAILED');
    }

    // ── Assert: audit event emitted with rejection link ────────────
    await expectAuditEventEmitted(fixture, {
      action: 'ASSET_FAIL_CLOSED_REJECTED',
      detailsContains: 'compliance',
    });

    // ── Assert: UI surfaces the rejection ──────────────────────────
    // (Frontend behavior: AssetCreatePage poll terminates on FAILED
    // and shows a banner with the reason + a "Why this happened" link
    // to the runbook.)
    await loginAsPersona(page, fixture.dpoUser);
    await gotoWithRetry(page, '/assets/create');
    await waitForAppMainReady(page);
    await waitForLoadingComplete(page);

    // The fail-closed banner should be visible after polling completes.
    const banner = page.getByRole('alert', { name: /asset creation rejected/i });
    await expect(banner).toBeVisible({ timeout: WORKFLOW_POLL_TIMEOUT_MS });
    await expect(banner).toContainText(/compliance/i);
    await expect(banner).toContainText(/runbook|why this happened/i);
  });

  test('legacy fallback: persists DRAFT when fail-closed flag is OFF', async ({
    cleanup,
  }) => {
    // D250.12 30-day soak window — existing tenants opt-out of
    // fail-closed by setting `compliance_fail_closed_enabled=False`.
    // Asset MUST persist in DRAFT in this mode.
    const fixture = await seedFailClosedTenant({
      cleanup,
      tenantPolicyAllowsStorage: false,
      complianceFailClosedEnabled: false,
    });
    _activeFixtures.push(fixture);

    const response = await fixture.attemptDataFirstAssetCreation({
      key: 'legacy-fallback-pii',
      name: 'Legacy fallback DRAFT',
      fileContent: 'name,ssn\nBob,222-33-4444\n',
    });

    expect([200, 201, 202]).toContain(response.status);

    // Asset MUST persist in DRAFT. Phase 250.1.A legacy fallback
    // contract.
    await expectAssetCountEquals(fixture, 'legacy-fallback-pii', 1);

    const asset = await fixture.fetchAsset('legacy-fallback-pii');
    expect(asset.status).toBe('DRAFT');
    expect(asset.compliance_status).toBe('FAIL');
  });

  test('cross-tenant isolation: tenant B cannot use tenant A file_id', async ({
    cleanup,
  }) => {
    // D250.16 existence-leak protection — cross-tenant access returns
    // 404, NOT 403, so an attacker cannot enumerate file_ids by
    // status-code analysis.
    const tenantA = await seedFailClosedTenant({
      cleanup,
      tenantPolicyAllowsStorage: true,
      complianceFailClosedEnabled: true,
    });
    _activeFixtures.push(tenantA);
    const tenantB = await seedFailClosedTenant({
      cleanup,
      tenantPolicyAllowsStorage: true,
      complianceFailClosedEnabled: true,
    });
    _activeFixtures.push(tenantB);

    const fileA = await tenantA.uploadFile({
      content: 'a,b\n1,2\n',
      name: 'tenant-a.csv',
    });

    // Tenant B attempts to use Tenant A's file_id.
    const response = await tenantB.attemptDataFirstAssetCreation({
      key: 'cross-tenant-attempt',
      name: 'Should 404',
      fileId: fileA.id,
    });

    expect(response.status).toBe(404);
    // Zero Asset rows in EITHER tenant — pre-gate failure.
    await expectAssetCountEquals(tenantA, 'cross-tenant-attempt', 0);
    await expectAssetCountEquals(tenantB, 'cross-tenant-attempt', 0);
  });
});
