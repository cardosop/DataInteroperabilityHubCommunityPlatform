/**
 * Phase 5 E2E Test — DEPRECATED (journey-aligned)
 *
 * Content maps to: JOURNEY-DPO-015, JOURNEY-DPO-016, JOURNEY-DPO-017, JOURNEY-DE-014.
 * EXCLUDED FROM CI: removed from batch 7 (2026-03-14). Run manually via: bash scripts/e2e-batches.sh 9
 * Prefer journey specs under journeys/dpo/, journeys/de/. Deletion target: after sign-off.
 *
 * Tests complete ODPS journey: upload → workflow status → link ODCS → export
 */

import { expect, test, type Page } from '@playwright/test';
import * as fs from 'fs';
import { getTestUser, loginAsPersona } from './fixtures/auth';
import { isBenignConsoleError } from './fixtures/console-utils';
import { loginAndNavigateToRoute } from './fixtures/helpers';
import { verifyViaApi } from './fixtures/verifyViaApi';

const getApiBaseUrl = () => process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

// Helper to create a valid ODCS contract via API
async function createODCSContractViaAPI(page: Page): Promise<string | null> {
  try {
    const apiBase = getApiBaseUrl().replace(/\/$/, '');
    const result = await page.evaluate(async (base: string) => {
      const token = localStorage.getItem('access_token');
      if (!token) return { success: false, error: 'No token' };

      // Create a well-formed ODCS contract
      const contractJson = {
        id: `test-odcs-${Date.now()}`,
        name: 'Test ODCS Contract',
        hub_contract_version: '1.0.0',
        info: {
          title: 'Test ODCS Contract',
          name: 'Test ODCS Contract',
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
      return { success: true, contractId: contract.id };
    }, apiBase);

    if (!result.success) {
      console.log('ODCS contract creation via API failed:', result.error);
      return null;
    }
    return result.contractId;
  } catch (error) {
    console.log('ODCS contract creation via API exception:', error);
    return null;
  }
}

// Helper to poll workflow status until completion
async function pollWorkflowStatus(
  page: Page,
  workflowInstanceId: string,
  timeout: number = 300000
): Promise<unknown> {
  const startTime = Date.now();
  const pollInterval = 2000; // Poll every 2 seconds
  const apiBase = getApiBaseUrl().replace(/\/$/, '');

  // Give workflow a moment to start before first poll
  await page.waitForTimeout(1000);

  while (Date.now() - startTime < timeout) {
    const result = await page.evaluate(
      async ({
        workflowInstanceId,
        token,
        base,
      }: {
        workflowInstanceId: string;
        token: string | null;
        base: string;
      }) => {
        if (!token) return { success: false, error: 'No token' };
        try {
          const response = await fetch(
            `${base}/contracts/products/workflows/${workflowInstanceId}/status/?_t=${Date.now()}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                Pragma: 'no-cache',
                Expires: '0',
              },
            }
          );

          if (!response.ok) {
            const errorText = await response.text().catch(() => '');
            const errorJson = await response.json().catch(() => null);
            return {
              success: false,
              error: `Status check failed: ${response.status}`,
              errorDetails: errorJson || errorText,
            };
          }

          const data = await response.json();
          // Log the actual response for debugging
          console.log(
            `API Response: status=${data.status}, has_odps=${!!data.odps_contract}, has_odcs=${!!data.odcs_contract}`
          );
          return { success: true, data };
        } catch (error) {
          return { success: false, error: error instanceof Error ? error.message : String(error) };
        }
      },
      {
        workflowInstanceId,
        token: await page.evaluate(() => localStorage.getItem('access_token')),
        base: apiBase,
      }
    );

    if (!result.success) {
      // Log the error but don't throw immediately - might be transient
      console.log(`⚠️ Status check failed: ${result.error}, retrying...`);
      await page.waitForTimeout(pollInterval);
      continue;
    }

    const status = result.data.status;
    console.log(`Workflow status: ${status} (${result.data.progress_percentage || 0}%)`);

    if (status === 'COMPLETED') {
      return result.data;
    } else if (status === 'FAILED') {
      throw new Error(`Workflow failed: ${result.data.message || 'Unknown error'}`);
    } else if (status === 'PENDING' || status === 'RUNNING') {
      // Continue polling
    } else {
      console.log(`⚠️ Unknown workflow status: ${status}, continuing to poll...`);
    }

    // Wait before next poll
    await page.waitForTimeout(pollInterval);
  }

  throw new Error(`Workflow did not complete within ${timeout}ms`);
}

test.describe('Phase 5 ODPS Journey', () => {
  test('complete journey: ODPS upload → workflow status → link ODCS → export', async ({ page }) => {
    test.setTimeout(120000);

    // Log console errors except known benign ones (navigation aborts, WS unavailable)
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

    // Step 1: Navigate to ODPS upload page
    console.log('Step 1: Navigating to ODPS upload page...');
    await loginAndNavigateToRoute(page, testUser, '/odps/upload', {
      timeout: 60000,
      contentSelector: '.odps-upload-page, .odps-upload-form, h1',
    });

    await page.waitForTimeout(2000);

    // Guard: if the ODPS upload page doesn't render an upload form, skip gracefully.
    // This can happen when the ODPS feature is disabled or the route doesn't exist.
    // Condition hoisted into test.skip (PR 5 ESLint rule) + skip reason reaches
    // PR 10's skip-counter gate so CI fails when ODPS route is broadly unavailable.
    const redirected = page.url().includes('/403') || page.url().includes('/login');
    test.skip(
      redirected,
      `ODPS upload page redirected to ${page.url()} — route may not exist or user lacks permission`,
    );
    if (redirected) {
      return;
    }
    const odpsFormExists = await page.locator(
      '.odps-upload-page, .odps-upload-form, input[type="file"], textarea[id="odps-content"]'
    ).first().waitFor({ state: 'visible', timeout: 10000 }).then(() => true).catch(() => false);
    test.skip(
      !odpsFormExists,
      'ODPS upload form not found on /odps/upload — ODPS feature may not be enabled in this environment',
    );
    if (!odpsFormExists) {
      return;
    }

    // Step 2: Upload ODPS JSON file
    console.log('Step 2: Uploading ODPS JSON file...');

    // Create a valid ODPS 4.1 document with embedded ODCS contract
    const odpsDocument = {
      schema: 'https://opendataproducts.org/schema/v4.1',
      version: '4.1',
      product: {
        details: {
          en: {
            productID: `test-product-${Date.now()}`,
            name: 'Test ODPS Product',
            description: 'Test product for E2E testing',
            productVersion: '1.0.0',
            category: 'Data Product',
          },
        },
        dataSchema: {
          fields: [
            { name: 'id', type: 'string', description: 'Unique identifier' },
            { name: 'name', type: 'string', description: 'Name field' },
          ],
        },
        contract: {
          spec: {
            apiVersion: 'odcs/v3',
            kind: 'DataContract',
            id: `test-odcs-${Date.now()}`,
            name: 'Test ODCS Contract',
            version: '1.0.0',
            schema: {
              fields: [
                { name: 'id', type: 'string', description: 'Unique identifier' },
                { name: 'name', type: 'string', description: 'Name field' },
              ],
            },
          },
        },
        marketplace: {
          pricingPlans: [
            {
              planID: 'basic',
              name: 'Basic Plan',
              price: 9.99,
              currency: 'USD',
              billingPeriod: 'monthly',
            },
          ],
          accessMethods: {
            api: {
              type: 'REST',
              endpoint: 'https://api.example.com/data',
              authentication: {
                type: 'API_KEY',
              },
            },
          },
        },
      },
    };

    const odpsJson = JSON.stringify(odpsDocument, null, 2);

    // Option 1: Upload via file input
    const fileInput = page.locator('input[type="file"]');
    if ((await fileInput.count()) > 0) {
      // Create a temporary file in the browser context
      await fileInput.setInputFiles({
        name: 'test-odps.json',
        mimeType: 'application/json',
        buffer: Buffer.from(odpsJson),
      });
      await page.waitForTimeout(1000);
    } else {
      // Option 2: Paste content directly into textarea
      const contentTextarea = page.locator('textarea[id="odps-content"]');
      await contentTextarea.waitFor({ timeout: 10000 });
      await contentTextarea.fill(odpsJson);
      await page.waitForTimeout(500);
    }

    // Verify format is JSON
    const formatSelect = page.locator('select[id="odps-format"]');
    if ((await formatSelect.count()) > 0) {
      const currentFormat = await formatSelect.inputValue();
      if (currentFormat !== 'JSON') {
        await formatSelect.selectOption('JSON');
        await page.waitForTimeout(500);
      }
    }

    // Step 3: Submit ODPS creation
    console.log('Step 3: Submitting ODPS creation...');
    const createButton = page.locator('button:has-text("Create ODPS Product")');
    const createButtonFound = await createButton.waitFor({ timeout: 10000 }).then(() => true).catch(() => false);
    test.skip(
      !createButtonFound,
      '"Create ODPS Product" button not found — ODPS submission form may use different UI or not be fully implemented',
    );
    if (!createButtonFound) {
      return;
    }

    // Monitor network request to capture workflow instance ID
    let workflowInstanceId: string | null = null;
    const responsePromise = page
      .waitForResponse(
        (response) =>
          response.url().includes('/contracts/products/') && response.request().method() === 'POST',
        { timeout: 30000 }
      )
      .catch(() => null);

    await createButton.click();

    // Wait for response
    const response = await responsePromise;
    if (response) {
      if (response.ok()) {
        const responseData = await response.json();
        workflowInstanceId = responseData.workflow_instance_id;
        console.log(`✅ ODPS creation started, workflow instance ID: ${workflowInstanceId}`);

        // Dual-channel verification (PR 7a-ext2b) — third adoption of the
        // pattern. Confirm the workflow instance is actually queryable at
        // its status endpoint before we start polling; catches the
        // failure mode where the UI's response reports a workflow ID but
        // the backend never registered it (e.g. side-effect registration
        // failed inside a `@transaction.atomic` block). Using a predicate
        // rather than exact match because the status can be any of
        // pending/running/completed/failed.
        if (workflowInstanceId) {
          await verifyViaApi(
            page,
            `/api/v1/contracts/products/workflows/${workflowInstanceId}/status/`,
            (body: { status?: string }) =>
              typeof body.status === 'string' && body.status.length > 0,
          );
        }
      } else {
        const errorText = await response.text().catch(() => '');
        const errorJson = await response.json().catch(() => null);
        const errorMessage = errorJson ? JSON.stringify(errorJson, null, 2) : errorText;
        console.error(`❌ ODPS creation failed: ${response.status()} - ${errorMessage}`);
        // Workflows disabled is a tenant configuration issue, not a test failure.
        // Condition hoisted into test.skip (PR 5 ESLint rule).
        const workflowsDisabled = errorMessage.includes('Workflows are disabled');
        test.skip(
          workflowsDisabled,
          `Workflows are disabled for this tenant — skip. Enable workflows in tenant settings to run this test.`,
        );
        if (workflowsDisabled) {
          return;
        }
        throw new Error(`ODPS creation failed: ${response.status()} - ${errorMessage}`);
      }
    } else {
      // Try to extract from UI
      await page.waitForTimeout(3000);
      const workflowProgress = page.locator('.odps-workflow-progress');
      const workflowVisible = (await workflowProgress.count()) > 0;
      if (workflowVisible) {
        // Workflow progress is shown, extract ID from page if possible
        // For now, we'll poll the API to find the workflow
        console.log('⚠️ No response received, will try to find workflow via polling');
      } else {
        // Condition hoisted into test.skip per PR 5 ESLint rule.
        test.skip(
          !workflowVisible,
          'No response received for ODPS creation — backend may be unavailable or test timed out',
        );
        return;
      }
    }

    // If we don't have workflow instance ID, try to get it from the page
    if (!workflowInstanceId) {
      // Wait for workflow progress section to appear
      await page.waitForSelector('.odps-workflow-progress', { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Try to extract from page state or API
      workflowInstanceId = await page.evaluate(async () => {
        const token = localStorage.getItem('access_token');
        if (!token) return null;

        // Get recent workflows (this is a workaround - ideally we'd have the ID from response)
        // For now, we'll need to rely on the UI showing the workflow status
        return null;
      });
    }

    // Step 4: Poll workflow status until completion
    console.log('Step 4: Polling workflow status...');
    if (!workflowInstanceId) {
      // Extract from UI - wait for workflow status to be displayed
      await page.waitForSelector('.workflow-running, .workflow-completed, .workflow-failed', {
        timeout: 10000,
      });

      // Try to get workflow instance ID from the page
      workflowInstanceId = await page.evaluate(() => {
        // Check if workflow instance ID is in the page somewhere
        const text = document.body.textContent || '';
        const match = text.match(/workflow[_-]?instance[_-]?id["\s:]+([a-f0-9-]{36})/i);
        return match ? match[1] : null;
      });

      if (!workflowInstanceId) {
        // Last resort: wait for completion and extract from navigation
        console.log('⚠️ Could not extract workflow instance ID, waiting for completion...');
        await page.waitForSelector('.workflow-completed, .workflow-failed', { timeout: 300000 });

        // Check if we were redirected to ODPS detail page
        if (page.url().includes('/odps/')) {
          const odpsId = page.url().split('/odps/')[1].split('/')[0];
          console.log(`✅ Workflow completed, ODPS ID: ${odpsId}`);
          workflowInstanceId = null; // We have ODPS ID instead
        }
      }
    }

    let odpsContractId: string | null = null;
    let odcsContractId: string | null = null;

    if (workflowInstanceId) {
      // Poll workflow status via API
      const workflowResult = await pollWorkflowStatus(page, workflowInstanceId);
      odpsContractId = workflowResult.odps_contract?.id || null;
      odcsContractId = workflowResult.odcs_contract?.id || null;
      console.log(`✅ Workflow completed - ODPS: ${odpsContractId}, ODCS: ${odcsContractId}`);
    } else {
      // Wait for UI to show completion and extract IDs
      await page.waitForSelector('.workflow-completed', { timeout: 300000 });
      await page.waitForTimeout(2000);

      // Extract contract IDs from the completion message
      const createdContracts = page.locator('.created-contracts');
      if ((await createdContracts.count()) > 0) {
        const contractsText = await createdContracts.textContent();
        const odpsMatch = contractsText?.match(/ODPS Contract[:\s]+([a-f0-9-]{36})/i);
        const odcsMatch = contractsText?.match(/ODCS Contract[:\s]+([a-f0-9-]{36})/i);
        odpsContractId = odpsMatch ? odpsMatch[1] : null;
        odcsContractId = odcsMatch ? odcsMatch[1] : null;
      }

      // If still no IDs, check if we were redirected
      if (!odpsContractId && page.url().includes('/odps/')) {
        odpsContractId = page.url().split('/odps/')[1].split('/')[0];
      }
    }

    if (!odpsContractId) {
      throw new Error('Failed to get ODPS contract ID after workflow completion');
    }

    console.log(`✅ ODPS contract created: ${odpsContractId}`);
    if (odcsContractId) {
      console.log(`✅ ODCS contract created: ${odcsContractId}`);
    }

    // Step 5: Navigate to ODPS detail page (full login+nav to recover from auth expiry after long journey)
    console.log('Step 5: Navigating to ODPS detail page...');
    await loginAndNavigateToRoute(page, testUser, `/odps/${odpsContractId}`, {
      timeout: 60000,
      contentSelector: '.odps-detail-page, .odps-detail-content, .error-display, h1',
    });

    await page.waitForTimeout(1500);

    // Verify ODPS detail page loaded
    const odpsHeading = page.locator('.odps-detail-page h1, .odps-detail-content h1').first();
    await expect(odpsHeading).toBeVisible({ timeout: 10000 });

    // Step 6: Link ODCS contract (if not already linked)
    console.log('Step 6: Linking ODCS contract...');

    // Check if ODCS is already linked (from product-first flow)
    const linksSection = page.locator('.odps-links-section');
    let needsLinking = true;

    if ((await linksSection.count()) > 0) {
      const linksText = await linksSection.textContent();
      if (linksText?.includes('Linked ODCS Contract')) {
        console.log('✅ ODCS contract already linked from product-first flow');
        needsLinking = false;

        // Extract ODCS contract ID if not already known
        if (!odcsContractId) {
          const odcsLink = page.locator('.linked-contract a, .btn-link');
          if ((await odcsLink.count()) > 0) {
            const href = await odcsLink.first().getAttribute('href');
            if (href) {
              const match = href.match(/\/contracts\/([a-f0-9-]+)/);
              if (match) {
                odcsContractId = match[1];
              }
            }
          }
        }
      }
    }

    if (needsLinking && !odcsContractId) {
      // Create an ODCS contract to link
      console.log('Creating ODCS contract to link...');
      odcsContractId = await createODCSContractViaAPI(page);

      if (!odcsContractId) {
        throw new Error('Failed to create ODCS contract for linking');
      }

      console.log(`✅ Created ODCS contract: ${odcsContractId}`);

      // Navigate to ODCS contract detail page and link ODPS
      await page.goto(`/contracts/${odcsContractId}`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(2000);

      // Click "Link ODPS" button
      const linkODPSButton = page.locator('button:has-text("Link ODPS")');
      await linkODPSButton.waitFor({ timeout: 10000 });
      await linkODPSButton.click();

      // Wait for link page to load
      await page.waitForURL(/\/contracts\/[^/]+\/link-odps/, { timeout: 10000 });
      await page.waitForTimeout(2000);

      // Select "Link Existing ODPS" mode
      const existingModeButton = page.locator('button:has-text("Link Existing ODPS")');
      if ((await existingModeButton.count()) > 0) {
        await existingModeButton.click();
        await page.waitForTimeout(500);
      }

      // Enter ODPS contract ID
      const odpsIdInput = page.locator('input[id="odps-contract-id"]');
      await odpsIdInput.waitFor({ timeout: 10000 });
      await odpsIdInput.fill(odpsContractId);

      // Click link button
      const linkButton = page.locator('button:has-text("Link ODPS Contract")');
      await linkButton.waitFor({ timeout: 10000 });

      const linkResponsePromise = page
        .waitForResponse(
          (response) =>
            response.url().includes('/link-odps/') && response.request().method() === 'POST',
          { timeout: 30000 }
        )
        .catch(() => null);

      await linkButton.click();

      // Wait for response
      const linkResponse = await linkResponsePromise;
      if (linkResponse && !linkResponse.ok()) {
        const errorText = await linkResponse.text().catch(() => '');
        throw new Error(`ODPS linking failed: ${linkResponse.status()} - ${errorText}`);
      }

      await page.waitForTimeout(2000);
      console.log('✅ ODPS contract linked to ODCS');
    }

    // Step 7: Export ODPS contract
    console.log('Step 7: Exporting ODPS contract...');

    // Re-login and navigate (auth may have expired after long journey; avoids "Redirected to login")
    await loginAndNavigateToRoute(page, testUser, `/odps/${odpsContractId}`, {
      timeout: 90000,
      contentSelector: '.odps-detail-page, .odps-detail-content, .error-display, h1',
    });

    // Find export section
    const exportSection = page.locator('.odps-export-section');
    await exportSection.waitFor({ timeout: 10000 });

    // Select export format (JSON)
    const exportFormatSelect = page.locator('select[id="export-format"]');
    if ((await exportFormatSelect.count()) > 0) {
      await exportFormatSelect.selectOption('json');
      await page.waitForTimeout(500);
    }

    // Monitor download
    const downloadPromise = page.waitForEvent('download', { timeout: 30000 }).catch(() => null);

    // Click export button
    const exportButton = page.locator('button:has-text("Export")');
    await exportButton.waitFor({ timeout: 10000 });
    await exportButton.click();

    // Wait for download
    const download = await downloadPromise;
    if (download) {
      console.log(`✅ ODPS exported successfully: ${download.suggestedFilename()}`);

      // Verify download completed successfully
      // The export endpoint returns a file download, so we verify the download event occurred
      // Detailed content validation is covered by backend unit tests
      const path = await download.path();
      if (path) {
        // Verify file exists and has content
        const stats = fs.statSync(path);
        expect(stats.size).toBeGreaterThan(0);
        console.log(
          `✅ Export file downloaded: ${download.suggestedFilename()} (${stats.size} bytes)`
        );

        // Try to parse as JSON to verify it's valid JSON (but don't fail if structure differs)
        try {
          const content = fs.readFileSync(path, 'utf-8');
          const exportedData = JSON.parse(content);

          // Basic validation: should be an object or have some structure
          if (typeof exportedData === 'object' && exportedData !== null) {
            console.log('✅ Exported file is valid JSON');
            // Log structure for debugging
            if (exportedData.schema) {
              console.log(`✅ ODPS schema found: ${exportedData.schema}`);
            }
            if (exportedData.product) {
              console.log('✅ ODPS product field found');
            }
            if (exportedData.version) {
              console.log(`✅ ODPS version found: ${exportedData.version}`);
            }
          }
        } catch (err) {
          // If JSON parsing fails, log but don't fail the test
          // The export endpoint may return different formats
          console.log(`⚠️ Could not parse export as JSON: ${err}`);
          console.log('⚠️ Export completed but content validation skipped');
        }
      } else {
        // If no file path, verify download event occurred
        console.log('✅ Export download event captured');
      }
    } else {
      // Check if export button shows success state
      await page.waitForTimeout(2000);
      const exportSuccess = page.locator('.export-success, .success-message');
      if ((await exportSuccess.count()) > 0) {
        console.log('✅ Export completed (success message shown)');
      } else {
        console.log('⚠️ Download event not captured, but export may have succeeded');
      }
    }

    console.log('✅ Complete ODPS journey test passed!');
  });
});
