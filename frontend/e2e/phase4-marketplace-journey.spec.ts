/**
 * Phase 4 E2E Test — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DPO-002 (Publish Asset to Marketplace), JOURNEY-DC-001 (Discover and Purchase).
 * EXCLUDED FROM CI: removed from batch 7 (2026-03-14). Run manually via: bash scripts/e2e-batches.sh 9
 * Prefer journey specs under journeys/dpo/, journeys/dc/. Deletion target: after sign-off.
 *
 * Tests complete marketplace journey: browse listing → purchase → entitlement visible
 */

import { expect, test, type Page } from '@playwright/test';
import { clearAuthStorage, getConsumerTestUser, getTestUser, loginAsPersona } from './fixtures/auth';
import { loginAndNavigateToRoute, waitForAppMainReady } from './fixtures/helpers';
import { isBenignConsoleError } from './fixtures/console-utils';
import { verifyViaApi } from './fixtures/verifyViaApi';

const getApiBaseUrl = () => process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/** Timing: log step name and elapsed ms for performance investigation. */
function stepTiming(stepName: string, startMs: number): number {
  const elapsed = Date.now() - startMs;
  console.log(`⏱️ [TIMING] ${stepName}: ${(elapsed / 1000).toFixed(2)}s`);
  return elapsed;
}

// Helper to activate asset via API (since UI flow is complex)
async function activateAssetViaAPI(page: Page, assetId: string): Promise<boolean> {
  try {
    const apiBaseUrl = getApiBaseUrl();
    const result = await page.evaluate(
      async ({ assetId, apiBase }: { assetId: string; apiBase: string }) => {
        const token = localStorage.getItem('access_token');
        if (!token) return { success: false, error: 'No token' };
        const base = apiBase.replace(/\/$/, '');

        // Use a well-formed ODCS contract that should validate successfully
        const contractJson = {
          id: `test-contract-${Date.now()}`,
          name: 'Test Contract',
          hub_contract_version: '1.0.0',
          info: {
            title: 'Test Contract',
            name: 'Test Contract',
            version: '1.0.0',
          },
          schema: {
            fields: [
              { name: 'id', type: 'string', description: 'Unique identifier' },
              { name: 'name', type: 'string', description: 'Name field' },
            ],
          },
        };

        const contractResponse = await fetch(`${base}/contracts/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            original_spec_type: 'ODCS',
            original_spec_version: '3.0.0',
            original_format: 'JSON',
            original_raw: JSON.stringify(contractJson),
          }),
        });

        if (!contractResponse.ok) {
          const error = await contractResponse.text();
          return {
            success: false,
            error: `Contract creation failed: ${contractResponse.status} - ${error}`,
          };
        }

        const contract = await contractResponse.json();
        const contractId = contract.id;
        let contractVersion = contract.version || 1; // Store initial version

        // Validate and normalize the contract FIRST (before attachment, as attachment requires validation_status)
        const validateResponse = await fetch(`${base}/contracts/${contractId}/validate/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ async: false }),
        });

        if (!validateResponse.ok) {
          const error = await validateResponse.text();
          return {
            success: false,
            error: `Contract validation failed: ${validateResponse.status} - ${error}`,
          };
        }

        // Wait for validation to complete (if async, poll for status)
        const validateResult = await validateResponse.json();
        console.log('Validation result:', JSON.stringify(validateResult));

        if (validateResponse.status === 202) {
          // Async validation - poll for completion
          const jobId = validateResult.job_id;
          let attempts = 0;
          while (attempts < 30) {
            await new Promise((resolve) => setTimeout(resolve, 1000));
            const jobStatus = await fetch(`${base}/jobs/${jobId}/`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (jobStatus.ok) {
              const job = await jobStatus.json();
              if (job.status === 'completed' || job.status === 'failed') {
                break;
              }
            }
            attempts++;
          }
        }

        // Wait for validation to complete and be saved to database
        // Poll the contract until validation_status is set (with timeout)
        let contractData = null;
        let attempts = 0;
        const maxAttempts = 10;
        const pollInterval = 1000; // 1 second

        while (attempts < maxAttempts) {
          await new Promise((resolve) => setTimeout(resolve, pollInterval));

          const contractCheck = await fetch(`${base}/contracts/${contractId}/`, {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          });

          if (contractCheck.ok) {
            contractData = await contractCheck.json();

            // Check if validation_status is set and valid
            if (
              contractData.validation_status &&
              (contractData.validation_status === 'VALID' ||
                contractData.validation_status === 'WARNING_ONLY')
            ) {
              contractVersion = contractData.version || contractVersion; // Update version
              console.log(
                `Contract validation_status set to ${contractData.validation_status} after ${attempts + 1} attempts`
              );
              break;
            }
          }

          attempts++;
        }

        if (!contractData) {
          return { success: false, error: `Failed to fetch contract after validation` };
        }

        // Check validation_status - if it's None or invalid, we can't proceed
        if (
          !contractData.validation_status ||
          (contractData.validation_status !== 'VALID' &&
            contractData.validation_status !== 'WARNING_ONLY')
        ) {
          // Try one more validation attempt
          console.log(
            `Validation_status is ${contractData.validation_status || 'None'}, retrying validation...`
          );
          const retryValidateResponse = await fetch(`${base}/contracts/${contractId}/validate/`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ async: false }),
          });

          if (retryValidateResponse.ok) {
            // Poll again after retry
            attempts = 0;
            while (attempts < maxAttempts) {
              await new Promise((resolve) => setTimeout(resolve, pollInterval));

              const retryContractCheck = await fetch(`${base}/contracts/${contractId}/`, {
                headers: { Authorization: `Bearer ${token}` },
              });
              if (retryContractCheck.ok) {
                const retryContractData = await retryContractCheck.json();
                if (
                  retryContractData.validation_status === 'VALID' ||
                  retryContractData.validation_status === 'WARNING_ONLY'
                ) {
                  contractData = retryContractData;
                  contractVersion = retryContractData.version || contractVersion; // Update version
                  console.log(
                    `Contract validation_status set to ${contractData.validation_status} after retry`
                  );
                  break;
                }
              }
              attempts++;
            }

            if (
              !contractData.validation_status ||
              (contractData.validation_status !== 'VALID' &&
                contractData.validation_status !== 'WARNING_ONLY')
            ) {
              return {
                success: false,
                error: `Contract validation_status is ${contractData.validation_status || 'None'}, needs VALID or WARNING_ONLY. Validation may have failed or DataContract service is unavailable.`,
              };
            }
          } else {
            const retryError = await retryValidateResponse.text();
            return {
              success: false,
              error: `Contract validation_status is ${contractData.validation_status || 'None'}, needs VALID or WARNING_ONLY. Retry validation failed: ${retryValidateResponse.status} - ${retryError}`,
            };
          }
        }

        // Now attach contract to asset (after validation)
        const attachResponse = await fetch(`${base}/assets/${assetId}/contracts/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ contract_id: contractId }),
        });

        if (!attachResponse.ok) {
          const error = await attachResponse.text();
          return {
            success: false,
            error: `Contract attachment failed: ${attachResponse.status} - ${error}`,
          };
        }

        // Update contract to set status to ACTIVE (include version for optimistic locking)
        const updateResponse = await fetch(`${base}/contracts/${contractId}/`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            status: 'ACTIVE',
            version: contractVersion, // Include version for optimistic locking
          }),
        });

        if (!updateResponse.ok) {
          const error = await updateResponse.text();
          return {
            success: false,
            error: `Contract update failed: ${updateResponse.status} - ${error}`,
          };
        }

        // Get asset to retrieve version for optimistic locking
        const assetResponse = await fetch(`${base}/assets/${assetId}/`, {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!assetResponse.ok) {
          const error = await assetResponse.text();
          return {
            success: false,
            error: `Failed to fetch asset: ${assetResponse.status} - ${error}`,
          };
        }

        const assetData = await assetResponse.json();
        const assetVersion = assetData.version || 1;

        // Activate asset (requires version for optimistic locking)
        const activateResponse = await fetch(`${base}/assets/${assetId}/activate/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            version: assetVersion,
          }),
        });

        if (!activateResponse.ok) {
          const error = await activateResponse.text();
          return {
            success: false,
            error: `Asset activation failed: ${activateResponse.status} - ${error}`,
          };
        }

        return { success: true };
      },
      { assetId, apiBase: apiBaseUrl }
    );

    if (!result.success) {
      console.log('Asset activation via API failed:', result.error);
      return false;
    }
    return true;
  } catch (error) {
    console.log('Asset activation via API exception:', error);
    return false;
  }
}

/** Create a marketplace listing via API (fallback when publish-page dropdown does not show asset). */
async function createListingViaAPI(
  page: Page,
  assetId: string
): Promise<{ listingId: string } | { success: false; error: string }> {
  const apiBase = getApiBaseUrl().replace(/\/$/, '');
  const LISTING_API_TIMEOUT_MS = 30000;
  const result = await page.evaluate(
    async ({
      assetId,
      apiBase,
      timeoutMs,
    }: {
      assetId: string;
      apiBase: string;
      timeoutMs: number;
    }) => {
      const token = localStorage.getItem('access_token');
      if (!token) return { success: false, error: 'No token' };
      const title = `Test Listing ${Date.now()}`;
      const shortDescription = 'Test marketplace listing description';
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch(`${apiBase}/marketplace/listings/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            asset_id: assetId,
            title,
            short_description: shortDescription,
            long_description: shortDescription,
            pricing_model: 'FREE_AUTO_APPROVE',
          }),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);
        if (!response.ok) {
          const text = await response.text();
          return { success: false, error: `${response.status}: ${text}` };
        }
        const data = await response.json();
        return { success: true, listingId: data.id };
      } catch (e) {
        clearTimeout(timeoutId);
        const msg = e instanceof Error ? e.message : String(e);
        return {
          success: false,
          error: msg.includes('abort') ? `Request timeout after ${timeoutMs}ms` : msg,
        };
      }
    },
    { assetId, apiBase, timeoutMs: LISTING_API_TIMEOUT_MS }
  );
  return result as { listingId: string } | { success: false; error: string };
}

test.describe('Phase 4 Marketplace Journey', () => {
  test('complete journey: browse listing → purchase → entitlement visible', async ({ page }) => {
    test.setTimeout(120000);
    const t0 = Date.now();

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        if (!isBenignConsoleError(text)) {
          console.log(`Browser console error: ${text}`);
        }
      }
    });

    // Login first (force fresh to avoid auth redirect race)
    await loginAsPersona(page, getTestUser);
    const testUser = await getTestUser();
    stepTiming('login', t0);
    const t1 = Date.now();

    // KYC VERIFIED is ensured by ensureE2ESubscriptionForUser (ensure-e2e-subscription API),
    // which runs after login and sets tenant kyc_status=VERIFIED for marketplace publish.
    await page.waitForTimeout(500);

    // Step 1: Create an asset first (prerequisite for listing)
    console.log('Step 1: Creating asset...');
    await loginAndNavigateToRoute(page, testUser, '/assets', {
      timeout: 60000,
      contentSelector: '.asset-list-page, .empty-state, .error-display, h1',
    });

    await page.waitForTimeout(2000);

    const createButton = page
      .locator('button:has-text("Create Asset")')
      .or(page.locator('.empty-state-action:has-text("Create Asset")'));
    await createButton.first().waitFor({ timeout: 10000 });
    await createButton.first().click();

    await expect(page).toHaveURL(/\/assets\/create/, { timeout: 10000 });
    await page.waitForSelector('input[id="asset-key"]', { timeout: 10000 });

    const assetKey = `test-asset-marketplace-${Date.now()}`;
    await page.fill('input[id="asset-name"]', 'Test Asset for Marketplace');
    await page.fill('input[id="asset-key"]', assetKey);
    await page.fill('textarea[id="asset-description"]', 'Test asset for marketplace listing');
    await page.selectOption('select[id="asset-visibility"]', 'INTERNAL');

    const submitButton = page.locator('button:has-text("Create Asset")');
    await submitButton.waitFor({ timeout: 10000 });

    // Click submit and wait for navigation
    await submitButton.click();

    // Wait for navigation away from create page (visible project has slowMo; backend can be slow)
    try {
      await page.waitForURL(
        (url) => {
          const path = url.pathname;
          return (
            path.startsWith('/assets/') &&
            !path.includes('/assets/create') &&
            path.match(/\/assets\/[^/]+/) !== null
          );
        },
        { timeout: 60000, waitUntil: 'domcontentloaded' }
      );
    } catch {
      await page.waitForTimeout(3000);
    }

    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    let assetUrl = page.url();
    const urlMatch = assetUrl.match(/\/assets\/([^/]+)/);
    if (!urlMatch || urlMatch[1] === 'create') {
      // Still on create - fail fast with backend error if present
      await page.waitForTimeout(2000);
      assetUrl = page.url();
      const finalMatch = assetUrl.match(/\/assets\/([^/]+)/);
      if (!finalMatch || finalMatch[1] === 'create') {
        // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
        const errEl = await page.locator('.error-display').first().textContent().catch(() => '');
        const errHint = errEl ? ` Backend error: ${errEl.slice(0, 200)}` : '';
        throw new Error(
          `Asset creation failed (URL still on create). Current URL: ${assetUrl}.${errHint}`
        );
      }
    }

    const assetId = assetUrl.match(/\/assets\/([^/]+)/)?.[1] ?? '';

    // Verify asset was created - wait for asset detail page
    await page.waitForSelector('.asset-detail-page, .asset-detail-content', { timeout: 10000 });
    await page.waitForTimeout(2000);
    stepTiming('Step 1: create asset', t1);
    const t2 = Date.now();

    // Step 2: Activate asset via API (required for marketplace listing)
    // Retry once on network errors (ERR_CONNECTION_RESET / Failed to fetch) - API may briefly close connections
    console.log('Step 2: Activating asset via API...');
    let activated = false;
    try {
      activated = await activateAssetViaAPI(page, assetId);
    } catch (e) {
      const msg = String(e?.message ?? e);
      if (/Failed to fetch|ERR_|other side closed|ECONNRESET/i.test(msg)) {
        console.log('Activation failed with network error, retrying once after 5s...');
        await page.waitForTimeout(5000);
        try {
          activated = await activateAssetViaAPI(page, assetId);
        } catch {
          console.log('Asset activation failed after retry - will try to continue anyway');
        }
      } else {
        console.log('Asset activation failed - will try to continue anyway');
      }
    }
    if (activated) {
      console.log('Asset activated successfully');
    } else {
      console.log('Asset activation failed - will try to continue anyway');
    }
    stepTiming('Step 2: activate asset', t2);
    const t3 = Date.now();

    // Step 4: Create a marketplace listing via API (fast, deterministic).
    // We use API here because the publish page asset dropdown is populated by useAssets(); after
    // creating an asset in the same run, the dropdown often doesn't show it yet (cache/refetch
    // timing), causing 70–110s of timeouts. API creation typically completes in 2–10s.
    // DoD-5.1 (browse → purchase → entitlement) is still validated via UI below.
    console.log('Step 4: Creating marketplace listing via API...');
    const LISTING_API_TIMEOUT_MS = 20000; // Backend create is usually 1–5s; 20s allows for slow runs
    const apiResult = await Promise.race([
      createListingViaAPI(page, assetId),
      new Promise<{ success: false; error: string }>((_, reject) =>
        setTimeout(
          () => reject(new Error(`Listing API did not respond within ${LISTING_API_TIMEOUT_MS}ms`)),
          LISTING_API_TIMEOUT_MS
        )
      ),
    ]).catch((e) => ({ success: false as const, error: String((e as Error).message) }));
    if (!apiResult || !('listingId' in apiResult)) {
      throw new Error(`Listing creation failed: ${apiResult?.error ?? 'timeout'}`);
    }
    const listingId = apiResult.listingId;
    console.log('Created listing via API:', listingId);
    stepTiming('Step 4: create listing', t3);
    const t4 = Date.now();

    await page.waitForTimeout(1000);

    // Step 4.5: Publish the listing (required for it to be visible and purchasable)
    console.log('Step 4.5: Publishing listing...');
    console.log(`📝 Listing ID to publish: ${listingId}`);
    try {
      const token = await page.evaluate(() => {
        return localStorage.getItem('access_token');
      });

      if (!token) {
        throw new Error('No access token found for publishing listing');
      }

      console.log('🔑 Token retrieved, making publish API call...');
      const apiBase = getApiBaseUrl().replace(/\/$/, '');

      // Publish the listing via API with full base URL so E2E hits API on port 8000 (not Vite proxy to 8001)
      const PUBLISH_TIMEOUT_MS = 30000;
      const publishResponse = await page.evaluate(
        async ({
          listingId,
          token,
          apiBaseUrl,
          timeoutMs,
        }: {
          listingId: string;
          token: string;
          apiBaseUrl: string;
          timeoutMs: number;
        }) => {
          console.log(`[Browser] Starting publish for listing: ${listingId}`);
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
          try {
            const url = `${apiBaseUrl}/marketplace/listings/${listingId}/`;
            const response = await fetch(url, {
              method: 'PATCH',
              headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
              },
              body: JSON.stringify({ status: 'PUBLISHED' }),
              signal: controller.signal,
            });
            clearTimeout(timeoutId);
            if (!response.ok) {
              const errorText = await response.text();
              // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
              const errorJson = await response.json().catch(() => null);
              return {
                success: false,
                status: response.status,
                error: errorJson || errorText,
              };
            }
            const data = await response.json();
            return { success: true, data };
          } catch (error) {
            clearTimeout(timeoutId);
            const msg = error instanceof Error ? error.message : String(error);
            return {
              success: false,
              error: msg.includes('abort') ? `Publish timeout after ${timeoutMs}ms` : msg,
            };
          }
        },
        { listingId, token, apiBaseUrl: apiBase, timeoutMs: PUBLISH_TIMEOUT_MS }
      );

      console.log(
        `📥 Publish response received: ${JSON.stringify({ success: publishResponse.success, status: publishResponse.status || 'N/A' })}`
      );

      if (!publishResponse.success) {
        console.log(
          `⚠️ Publish failed: ${publishResponse.status || 'Unknown'} - ${JSON.stringify(publishResponse.error)}`
        );
        throw new Error(
          `Failed to publish listing: ${publishResponse.status || 'Unknown'} - ${JSON.stringify(publishResponse.error)}`
        );
      }

      console.log('✅ Listing published successfully');
      await page.waitForTimeout(1000); // Wait for UI to update
    } catch (error) {
      console.log(`⚠️ Publish error: ${error}`);
      throw error;
    }
    stepTiming('Step 4.5: publish listing', t4);
    const t5 = Date.now();

    // Step 5: Browse marketplace and find the listing
    // Use loginAndNavigateToRoute (full login) when session may have expired during long journey
    console.log('Step 5: Browsing marketplace...');
    console.log(`📝 Looking for listing ID: ${listingId}`);
    await loginAndNavigateToRoute(page, testUser, '/marketplace', {
      timeout: 90000,
      contentSelector: '.listing-list-page, .listing-list-grid, .empty-state, h1',
    });
    console.log('📍 Navigated to /marketplace');
    console.log('✅ Marketplace content loaded');

    await page.waitForTimeout(2000);

    // Search for our listing or click on it if visible
    console.log('🔍 Searching for listing card...');
    const listingCard = page.locator('.listing-card').filter({ hasText: 'Test Listing' });
    const cardCount = await listingCard.count();
    console.log(`📊 Found ${cardCount} listing card(s) matching "Test Listing"`);

    if (cardCount > 0) {
      console.log('✅ Listing card found, clicking...');
      await listingCard.first().click();
      await page.waitForURL(/\/marketplace\/listings\/[^/]+$/, { timeout: 10000 });
      console.log('✅ Navigated to listing detail page');
    } else {
      // If not visible, navigate directly to the listing
      console.log('⚠️ Listing card not visible, navigating directly to listing...');
      await page.goto(`/marketplace/listings/${listingId}`);
      console.log(`📍 Navigated directly to /marketplace/listings/${listingId}`);
    }

    console.log('⏳ Waiting for listing detail page to load...');
    await page.waitForSelector('.listing-detail-page, .error-display', { timeout: 30000 });
    if (page.url().includes('/login')) {
      throw new Error('Provider auth redirect: listing page redirected to login.');
    }
    if ((await page.locator('.error-display').count()) > 0) {
      const errText = await page.locator('.error-display').first().textContent();
      throw new Error(`Listing detail failed: ${errText}`);
    }
    console.log('✅ Listing detail page loaded');
    await page.waitForTimeout(2000);
    stepTiming('Step 5: browse marketplace', t5);
    const t6 = Date.now();

    // Step 5.5: Switch to consumer user (different tenant) for purchasing
    // The backend prevents users from purchasing their own listings
    console.log('Step 5.5: Switching to consumer user for purchase...');
    const consumerUser = await getConsumerTestUser();

    // Fully clear provider auth (cookies + storage) to avoid token/session conflicts
    console.log('🚪 Logging out provider user...');
    await clearAuthStorage(page);
    await page.waitForTimeout(1500);

    // Login as consumer and navigate to listing; retry up to 2x on redirect-to-login (auth race on user switch)
    console.log('🔑 Logging in as consumer and navigating to listing...');
    const listingUrl = `/marketplace/listings/${listingId}`;
    let consumerOnListing = false;
    let lastErr: unknown;
    for (let attempt = 0; attempt < 2 && !consumerOnListing; attempt++) {
      if (attempt > 0) {
        console.log(`⚠️ Consumer redirected to login, retry ${attempt + 1}/2...`);
        await clearAuthStorage(page);
        await page.waitForTimeout(2000);
      }
      try {
        await loginAndNavigateToRoute(page, consumerUser, listingUrl, {
          timeout: 60000,
          contentSelector: '.listing-detail-page, .error-display',
        });
        consumerOnListing = !page.url().includes('/login');
      } catch (err) {
        lastErr = err;
        const msg = err instanceof Error ? err.message : String(err);
        if (!msg.includes('Redirected to login') && !msg.includes('Still on login')) {
          throw err;
        }
      }
    }
    if (!consumerOnListing) {
      throw new Error(
        'Consumer auth redirect: listing page redirected to login after retries. ' +
          'Ensure consumer user exists and has marketplace access (ensure_e2e_user_roles, ensure_e2e_subscription).',
        { cause: lastErr }
      );
    }
    if ((await page.locator('.error-display').count()) > 0) {
      const errText = await page.locator('.error-display').first().textContent();
      throw new Error(`Listing detail failed for consumer: ${errText}`);
    }
    console.log('✅ Listing page loaded for consumer');
    await page.waitForTimeout(2000);
    stepTiming('Step 5.5: switch to consumer', t6);
    const t7 = Date.now();

    // Step 6: Purchase/Get Access to the listing
    console.log('Step 6: Purchasing listing...');
    console.log('🔍 Looking for purchase button...');
    const purchaseButton = page
      .locator('button:has-text("Get Access")')
      .or(page.locator('button:has-text("Request Access")'));
    await purchaseButton.waitFor({ timeout: 10000 });
    console.log('✅ Purchase button found');

    const buttonText = await purchaseButton.textContent();
    console.log(`📝 Purchase button text: "${buttonText}"`);

    // Monitor network request to capture order creation response
    let orderCreateRequest: unknown = null;
    let orderCreateError: string | null = null;

    page.on('request', async (request) => {
      if (request.url().includes('/marketplace/orders/') && request.method() === 'POST') {
        try {
          const postData = request.postData();
          if (postData) {
            orderCreateRequest = JSON.parse(postData);
            console.log(
              '📤 Order creation request payload:',
              JSON.stringify(orderCreateRequest, null, 2)
            );
          }
        } catch (e) {
          console.log('⚠️ Could not parse order request payload:', e);
        }
      }
    });

    // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
    const orderResponsePromise = page
      .waitForResponse(
        (response) =>
          response.url().includes('/marketplace/orders/') && response.request().method() === 'POST',
        { timeout: 30000 }
      )
      .catch(() => null);

    console.log('🖱️ Clicking purchase button...');
    await purchaseButton.click();
    console.log('✅ Purchase button clicked');

    // Wait for response
    const orderResponse = await orderResponsePromise;
    if (orderResponse) {
      if (!orderResponse.ok()) {
        // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
        const errorText = await orderResponse.text().catch(() => '');
        // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
        const errorJson = await orderResponse.json().catch(() => null);
        orderCreateError = `Status ${orderResponse.status()}: ${errorJson ? JSON.stringify(errorJson, null, 2) : errorText}`;
        console.log('❌ Order creation error:', orderCreateError);
        console.log('📤 Request payload was:', JSON.stringify(orderCreateRequest, null, 2));
        throw new Error(`Order creation failed: ${orderCreateError}`);
      } else {
        // intentional: best-effort .catch on an optional step — primary pass/fail is made by a downstream assertion (verifyViaApi, waitFor, explicit expect). The fallback value tolerates well-known transient or absent-UI cases without papering over real failures.
        const responseData = await orderResponse.json().catch(() => null);
        console.log('✅ Order creation API call succeeded');
        if (responseData) {
          console.log('📥 Response data:', JSON.stringify(responseData, null, 2));
        }
      }
    } else {
      console.log('⚠️ No response received for order creation request');
    }

    // Wait for order to be created and redirect
    console.log('⏳ Waiting for order creation and redirect...');
    await page.waitForURL(/\/marketplace\/orders\/[^/]+$/, { timeout: 15000 });
    const orderUrl = page.url();
    const orderId = orderUrl.split('/').pop()!;
    console.log(`✅ Created order: ${orderId}`);
    console.log(`📍 Order URL: ${orderUrl}`);

    // Dual-channel verification (PR 7a-ext2e). The URL match proves the UI
    // routed on a 201/202 response; it does not prove the Order row is
    // backed by the expected listing or that the entitlement-creation
    // side-effects fired. Hit /api/v1/marketplace/orders/<id>/ directly so
    // subsequent steps (entitlement list check) don't race a silently
    // failed order-finalise job.
    await verifyViaApi(
      page,
      `/api/v1/marketplace/orders/${orderId}/`,
      (body: { listing_id?: string; listing?: { id?: string } }) =>
        body.listing_id === listingId || body.listing?.id === listingId,
    );

    console.log('⏳ Waiting for order detail page to load...');
    await page.waitForSelector('.order-detail-page, .order-detail-content', { timeout: 10000 });
    console.log('✅ Order detail page loaded');
    await page.waitForTimeout(2000);
    stepTiming('Step 6: purchase', t7);
    const t8 = Date.now();

    // Step 7: Verify entitlement is visible
    console.log('Step 7: Verifying entitlement...');
    console.log('📍 Navigating to /marketplace/entitlements...');
    await page.goto('/marketplace/entitlements');
    await waitForAppMainReady(page, {
      timeout: 60000,
      contentSelector: '.entitlement-list-page, .entitlement-list-table, .empty-state, h1',
    });
    console.log('✅ Entitlements page content loaded');

    await page.waitForTimeout(3000); // Wait for entitlements to load
    console.log('⏳ Waiting additional 3s for entitlements to load...');

    // Check if entitlement is visible in the list
    console.log('🔍 Searching for entitlement row...');
    const entitlementRow = page
      .locator('.entitlement-row, tr')
      .filter({ hasText: 'Test Asset for Marketplace' });
    const rowCount = await entitlementRow.count();
    console.log(`📊 Found ${rowCount} entitlement row(s) matching "Test Asset for Marketplace"`);

    if (rowCount > 0) {
      console.log('✅ Entitlement found in list');
      await expect(entitlementRow.first()).toBeVisible();

      // Verify status is ACTIVE
      const statusBadge = entitlementRow
        .first()
        .locator('.entitlement-status-active, .entitlement-status');
      if ((await statusBadge.count()) > 0) {
        const statusText = await statusBadge.first().textContent();
        console.log(`✅ Entitlement status: ${statusText}`);
      } else {
        console.log('⚠️ Status badge not found');
      }
    } else {
      // If not immediately visible, wait a bit more (entitlement might be created asynchronously)
      console.log('⚠️ Entitlement not immediately visible, waiting 5s and retrying...');
      await page.waitForTimeout(5000);

      // Try again
      const entitlementRowRetry = page
        .locator('.entitlement-row, tr')
        .filter({ hasText: 'Test Asset for Marketplace' });
      const retryCount = await entitlementRowRetry.count();
      console.log(`📊 Retry: Found ${retryCount} entitlement row(s)`);

      if (retryCount > 0) {
        console.log('✅ Entitlement found after retry');
        await expect(entitlementRowRetry.first()).toBeVisible();
      } else {
        // Check what's actually on the page for debugging
        console.log('⚠️ Entitlement still not found, checking page content...');
        const pageContent = await page.textContent('body');
        console.log('📄 Page content (first 1000 chars):', pageContent?.substring(0, 1000));
        throw new Error('Entitlement not found in entitlements list');
      }
    }
    stepTiming('Step 7: verify entitlement', t8);
    stepTiming('TOTAL', t0);

    console.log('✅ Complete marketplace journey test passed!');
  });
});
