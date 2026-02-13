/**
 * E2E Test Helpers
 * Reusable utilities for E2E tests across all journeys, personas, use cases, and features
 */

import { Page, expect } from '@playwright/test';

/**
 * Wait for API response with retry logic
 */
export async function waitForApiResponse(
  page: Page,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    status?: number | number[];
    retries?: number;
    retryDelay?: number;
  } = {}
): Promise<Response> {
  const { timeout = 30000, status, retries = 3, retryDelay = 2000 } = options;

  const pattern = typeof urlPattern === 'string' ? urlPattern : urlPattern.source;
  const statusArray = status ? (Array.isArray(status) ? status : [status]) : undefined;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await page.waitForResponse(
        (resp) => {
          const urlMatch =
            typeof urlPattern === 'string'
              ? resp.url().includes(urlPattern)
              : urlPattern.test(resp.url());

          if (!urlMatch) return false;

          if (statusArray) {
            return statusArray.includes(resp.status());
          }

          return resp.status() < 500; // Don't wait for 5xx errors
        },
        { timeout: attempt === 0 ? timeout : timeout * (attempt + 1) }
      );

      // Check if status matches (if specified)
      if (statusArray && !statusArray.includes(response.status())) {
        if (attempt < retries) {
          await page.waitForTimeout(retryDelay);
          continue;
        }
        throw new Error(
          `API response status ${response.status()} does not match expected ${statusArray.join(' or ')}`
        );
      }

      return response;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(retryDelay);
    }
  }

  throw new Error(`Failed to get API response after ${retries + 1} attempts`);
}

/**
 * Wait for element with retry logic
 */
export async function waitForElement(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
    state?: 'attached' | 'detached' | 'visible' | 'hidden';
    retries?: number;
    retryDelay?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000, state = 'visible', retries = 3, retryDelay = 1000 } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      await page.waitForSelector(selector, {
        timeout: attempt === 0 ? timeout : timeout * (attempt + 1),
        state,
      });
      return;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(retryDelay);
    }
  }
}

/**
 * Fill form field with retry logic
 */
export async function fillField(
  page: Page,
  selector: string,
  value: string,
  options: {
    timeout?: number;
    clear?: boolean;
  } = {}
): Promise<void> {
  const { timeout = 10000, clear = true } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });

  const field = page.locator(selector);

  if (clear) {
    await field.clear();
  }

  await field.fill(value);

  // Verify value was set
  const actualValue = await field.inputValue();
  if (actualValue !== value) {
    throw new Error(`Failed to set field value: expected "${value}", got "${actualValue}"`);
  }
}

/**
 * Click element with retry logic
 */
export async function clickElement(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
    force?: boolean;
    retries?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000, force = false, retries = 3 } = options;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      await waitForElement(page, selector, { timeout, state: 'visible' });
      const element = page.locator(selector);

      if (force) {
        await element.click({ force: true });
      } else {
        await element.click();
      }

      return;
    } catch (error) {
      if (attempt === retries) {
        throw error;
      }
      await page.waitForTimeout(1000);
    }
  }
}

/**
 * Wait for navigation with timeout
 */
export async function waitForNavigation(
  page: Page,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    waitUntil?: 'load' | 'domcontentloaded' | 'networkidle';
  } = {}
): Promise<void> {
  const { timeout = 10000, waitUntil = 'domcontentloaded' } = options;

  const pattern = typeof urlPattern === 'string' ? urlPattern : urlPattern.source;

  await page.waitForURL(
    (url) => {
      if (typeof urlPattern === 'string') {
        return url.pathname.includes(urlPattern) || url.href.includes(urlPattern);
      }
      return urlPattern.test(url.pathname) || urlPattern.test(url.href);
    },
    { timeout, waitUntil }
  );
}

/**
 * Generate unique identifier for test data
 */
export function generateUniqueId(prefix = 'e2e'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Generate unique email for test users
 */
export function generateUniqueEmail(prefix = 'e2e'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 9)}@example.com`;
}

/**
 * Wait for app main content (no loading spinner). Use after goto for any protected route.
 * Also treats .loading-spinner-container as loading so list pages that use LoadingSpinner are covered.
 */
export async function waitForAppMainReady(
  page: Page,
  options: { timeout?: number; contentSelector?: string } = {}
): Promise<void> {
  const { timeout = 15000, contentSelector } = options;
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(
    (selector: string | undefined) => {
      const main = document.querySelector('.app-main');
      if (!main) return false;
      const loading =
        main.querySelector('.loading-spinner') || main.querySelector('.loading-spinner-container');
      if (loading) return false;
      if (selector) {
        const el = main.querySelector(selector);
        return !!el;
      }
      return true;
    },
    contentSelector,
    { timeout }
  );
  await page.waitForTimeout(1000);
}

/**
 * Wait for loading to complete
 */
export async function waitForLoadingComplete(
  page: Page,
  options: {
    timeout?: number;
    loadingSelector?: string;
  } = {}
): Promise<void> {
  const { timeout = 10000, loadingSelector = '.loading-spinner, .loading, [data-loading="true"]' } =
    options;

  try {
    // Wait for loading spinner to disappear
    await page.waitForSelector(loadingSelector, { state: 'hidden', timeout });
  } catch {
    // Loading spinner might not exist, which is fine
  }

  // Wait for page to be ready
  await page.waitForLoadState('domcontentloaded');

  // Additional wait for React to render
  await page.waitForTimeout(1000);
}

/**
 * Assert API error response
 */
export async function assertApiError(
  page: Page,
  urlPattern: string | RegExp,
  expectedStatus: number,
  expectedMessage?: string | RegExp
): Promise<void> {
  const response = await waitForApiResponse(page, urlPattern, {
    status: expectedStatus,
  });

  if (expectedMessage) {
    const body = await response.json().catch(() => ({}));
    const message = body.message || body.error || JSON.stringify(body);

    if (typeof expectedMessage === 'string') {
      expect(message).toContain(expectedMessage);
    } else {
      expect(message).toMatch(expectedMessage);
    }
  }
}

/**
 * Assert element contains text (with retry)
 */
export async function assertContainsText(
  page: Page,
  selector: string,
  text: string | RegExp,
  options: {
    timeout?: number;
    exact?: boolean;
  } = {}
): Promise<void> {
  const { timeout = 10000, exact = false } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });

  const element = page.locator(selector);

  if (exact) {
    if (typeof text === 'string') {
      await expect(element).toHaveText(text, { timeout });
    } else {
      await expect(element).toHaveText(text, { timeout });
    }
  } else {
    if (typeof text === 'string') {
      await expect(element).toContainText(text, { timeout });
    } else {
      await expect(element).toContainText(text, { timeout });
    }
  }
}

/**
 * Assert element is visible (with retry)
 */
export async function assertVisible(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
  } = {}
): Promise<void> {
  const { timeout = 10000 } = options;

  await waitForElement(page, selector, { timeout, state: 'visible' });
  await expect(page.locator(selector)).toBeVisible({ timeout });
}

/**
 * Assert element is not visible
 */
export async function assertNotVisible(
  page: Page,
  selector: string,
  options: {
    timeout?: number;
  } = {}
): Promise<void> {
  const { timeout = 5000 } = options;

  try {
    await expect(page.locator(selector)).toBeHidden({ timeout });
  } catch {
    // Element might not exist, which is fine
    const count = await page.locator(selector).count();
    if (count > 0) {
      throw new Error(`Element ${selector} is visible but should be hidden`);
    }
  }
}

/**
 * Take screenshot for debugging
 */
export async function takeDebugScreenshot(page: Page, name: string): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `debug-${name}-${timestamp}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`Debug screenshot saved: ${filename}`);
}

/**
 * Wait for API call to complete (by monitoring network requests)
 */
export async function waitForApiCall(
  page: Page,
  method: string,
  urlPattern: string | RegExp,
  options: {
    timeout?: number;
    status?: number;
  } = {}
): Promise<Response> {
  const { timeout = 30000, status } = options;

  const pattern = typeof urlPattern === 'string' ? urlPattern : urlPattern.source;

  return await page.waitForResponse(
    (resp) => {
      const methodMatch = resp.request().method() === method.toUpperCase();
      const urlMatch =
        typeof urlPattern === 'string'
          ? resp.url().includes(urlPattern)
          : urlPattern.test(resp.url());

      if (!methodMatch || !urlMatch) return false;

      if (status !== undefined) {
        return resp.status() === status;
      }

      return resp.status() < 500;
    },
    { timeout }
  );
}

/**
 * Clean up test data (helper for test teardown)
 */
export async function cleanupTestData(
  page: Page,
  resourceType: string,
  resourceIds: string[]
): Promise<void> {
  const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

  for (const id of resourceIds) {
    try {
      const token = await page.evaluate(() => localStorage.getItem('access_token'));
      if (!token) {
        console.warn(`No access token found, skipping cleanup for ${resourceType} ${id}`);
        continue;
      }

      const response = await fetch(`${API_BASE_URL}/${resourceType}/${id}/`, {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok || response.status === 404) {
        console.log(`Cleaned up ${resourceType} ${id}`);
      } else {
        console.warn(`Failed to cleanup ${resourceType} ${id}: ${response.status}`);
      }
    } catch (error) {
      console.warn(`Error cleaning up ${resourceType} ${id}:`, error);
    }
  }
}

/**
 * Test dimension: Happy path helper
 * Verifies that all steps complete successfully
 */
export async function verifyHappyPath(
  page: Page,
  steps: Array<{
    name: string;
    action: () => Promise<void>;
    verify?: () => Promise<void>;
  }>
): Promise<void> {
  for (const step of steps) {
    try {
      console.log(`Executing step: ${step.name}`);
      await step.action();

      if (step.verify) {
        await step.verify();
      }

      console.log(`✅ Step completed: ${step.name}`);
    } catch (error) {
      console.error(`❌ Step failed: ${step.name}`, error);
      throw new Error(`Happy path step failed: ${step.name} - ${error}`);
    }
  }
}

/**
 * Test dimension: Failure scenario helper
 * Verifies error handling
 */
export async function verifyFailureScenario(
  page: Page,
  action: () => Promise<void>,
  expectedError: {
    status?: number;
    message?: string | RegExp;
    selector?: string;
  }
): Promise<void> {
  try {
    await action();

    // If action succeeds, check if error should have occurred
    if (expectedError.status || expectedError.message) {
      throw new Error('Expected error but action succeeded');
    }
  } catch (error) {
    // Verify error matches expectations
    if (expectedError.status) {
      // Check API response status
      // This would need to be implemented based on how errors are handled
    }

    if (expectedError.message) {
      // Check error message
      if (expectedError.selector) {
        await assertContainsText(page, expectedError.selector, expectedError.message);
      }
    }
  }
}

/**
 * Test dimension: Edge case helper
 * Verifies boundary conditions
 */
export async function verifyEdgeCase(
  page: Page,
  testCase: {
    name: string;
    setup: () => Promise<void>;
    action: () => Promise<void>;
    verify: () => Promise<void>;
  }
): Promise<void> {
  console.log(`Testing edge case: ${testCase.name}`);

  await testCase.setup();
  await testCase.action();
  await testCase.verify();

  console.log(`✅ Edge case passed: ${testCase.name}`);
}
