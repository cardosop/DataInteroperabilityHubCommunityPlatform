/**
 * Phase TR.A — Dual-Channel E2E Backend Verification Helpers.
 *
 * After a UI operation (create, update, publish, delete), verify the
 * result independently through the backend API and audit trail.  This
 * catches cases where the UI shows success but the backend did not
 * actually persist the change.
 *
 * Usage in a spec:
 *   import { verifyViaApi, verifyAuditEvent } from '../fixtures/verifyBackend';
 *
 *   test('asset create persists to backend', async ({ page, request }) => {
 *     // ... UI operations ...
 *     const assetId = await extractIdFromPage(page);
 *     await verifyViaApi(request, `/api/v1/assets/${assetId}/`, {
 *       status: 200,
 *       requiredFields: ['id', 'name', 'status'],
 *     });
 *     await verifyAuditEvent(request, {
 *       action: 'ASSET_CREATED',
 *       resourceType: 'ASSET',
 *       timeout: 15000,
 *     });
 *   });
 */
import { APIRequestContext, expect } from "@playwright/test";

// ── Types ──────────────────────────────────────────────────────────────

export interface VerifyApiOptions {
  /** Expected HTTP status (default: 200). */
  status?: number;
  /** Fields that MUST be present in the JSON response body. */
  requiredFields?: string[];
  /** Fields with expected values (exact match). */
  expectedValues?: Record<string, unknown>;
  /** Max retries for polling until condition is met. */
  retries?: number;
  /** Delay between retries in ms. */
  retryDelay?: number;
}

export interface VerifyAuditOptions {
  /** The audit event action (e.g. 'ASSET_CREATED'). */
  action: string;
  /** The audit resource type (e.g. 'ASSET', 'CONTRACT'). */
  resourceType?: string;
  /** Max time to wait for the event in ms (default: 15000). */
  timeout?: number;
  /** Poll interval in ms (default: 1000). */
  pollInterval?: number;
}

export interface VerifySemanticOptions {
  /** SPARQL query to execute. */
  query: string;
  /** Expected binding name that must exist in results. */
  expectedBinding?: string;
  /** Expected number of result rows (minimum). */
  minResults?: number;
}

// ── API Verification ───────────────────────────────────────────────────

export async function verifyViaApi(
  request: APIRequestContext,
  url: string,
  options: VerifyApiOptions = {},
): Promise<Record<string, unknown>> {
  const {
    status = 200,
    requiredFields = [],
    expectedValues = {},
    retries = 5,
    retryDelay = 1000,
  } = options;

  let lastError: Error | null = null;
  let lastBody: Record<string, unknown> = {};

  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await request.get(url);
      expect(response.status()).toBe(status);

      const body = (await response.json()) as Record<string, unknown>;
      lastBody = body;

      // Verify required fields exist (support nested paths like 'data.id')
      for (const field of requiredFields) {
        const value = getNestedValue(body, field);
        expect(value, `Field '${field}' should exist in API response`).toBeDefined();
        expect(value, `Field '${field}' should not be null`).not.toBeNull();
      }

      // Verify expected values match
      for (const [field, expected] of Object.entries(expectedValues)) {
        const actual = getNestedValue(body, field);
        expect(actual, `Field '${field}' expected '${expected}', got '${actual}'`).toBe(
          expected,
        );
      }

      return body;
    } catch (e) {
      lastError = e as Error;
      if (attempt < retries - 1) {
        await new Promise((r) => setTimeout(r, retryDelay));
      }
    }
  }

  throw new Error(
    `verifyViaApi failed after ${retries} retries for ${url}: ${lastError?.message}\nLast body: ${JSON.stringify(lastBody).slice(0, 500)}`,
  );
}

// ── Audit Event Verification ───────────────────────────────────────────

export async function verifyAuditEvent(
  request: APIRequestContext,
  options: VerifyAuditOptions,
): Promise<Record<string, unknown>> {
  const {
    action,
    resourceType,
    timeout = 15000,
    pollInterval = 1000,
  } = options;

  const startTime = Date.now();
  let lastBody: Record<string, unknown> = {};

  while (Date.now() - startTime < timeout) {
    try {
      let url = `/api/v1/audit/audit-events/?ordering=-timestamp&limit=10`;
      if (resourceType) {
        url += `&resource_type=${encodeURIComponent(resourceType)}`;
      }

      const response = await request.get(url);
      if (response.status() !== 200) {
        await new Promise((r) => setTimeout(r, pollInterval));
        continue;
      }

      const body = (await response.json()) as Record<string, unknown>;
      lastBody = body;

      const results = (body.results || body.data || []) as Record<string, unknown>[];
      for (const event of results) {
        if (event.action === action) {
          if (!resourceType || event.resource_type === resourceType) {
            return event;
          }
        }
      }
    } catch {
      // API might not be ready yet — retry
    }

    await new Promise((r) => setTimeout(r, pollInterval));
  }

  throw new Error(
    `verifyAuditEvent: event '${action}'${resourceType ? ` (${resourceType})` : ''} not found within ${timeout}ms. Last response: ${JSON.stringify(lastBody).slice(0, 300)}`,
  );
}

// ── Semantic / RDF Verification ────────────────────────────────────────

export async function verifySemantic(
  request: APIRequestContext,
  options: VerifySemanticOptions,
): Promise<Record<string, unknown>> {
  const { query, expectedBinding, minResults = 0 } = options;

  const encodedQuery = encodeURIComponent(query);
  const response = await request.get(
    `/api/v1/semantic/sparql?query=${encodedQuery}`,
  );

  expect(response.status()).toBe(200);

  const body = (await response.json()) as Record<string, unknown>;

  // Verify results exist
  const results = (body.results?.bindings || body.bindings || []) as Record<
    string,
    unknown
  >[];

  if (minResults > 0) {
    expect(results.length).toBeGreaterThanOrEqual(minResults);
  }

  if (expectedBinding) {
    const hasBinding = results.some(
      (row) => expectedBinding in (row as Record<string, unknown>),
    );
    expect(
      hasBinding,
      `Semantic results should contain binding '${expectedBinding}'`,
    ).toBe(true);
  }

  return body;
}

// ── Helpers ────────────────────────────────────────────────────────────

function getNestedValue(
  obj: Record<string, unknown>,
  path: string,
): unknown {
  const keys = path.split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current && typeof current === "object" && key in (current as Record<string, unknown>)) {
      current = (current as Record<string, unknown>)[key];
    } else {
      return undefined;
    }
  }
  return current;
}

/**
 * Extract a resource ID from the current page URL.
 * Assumes URL pattern like /assets/<id> or /contracts/<id>.
 */
export function extractIdFromUrl(url: string, prefix: string): string | null {
  const match = url.match(new RegExp(`/${prefix}/([a-f0-9-]+)`));
  return match ? match[1] : null;
}
