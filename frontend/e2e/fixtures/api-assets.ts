/**
 * E2E API helpers for creating backend resources (e.g. assets) without UI.
 * Used so tests that require an asset (e.g. JOURNEY-DPO-002 publish) don't skip when catalog is empty.
 * No mocks; real backend only.
 */

import type { TestUser } from '../setup/create-test-user';

const API_BASE_URL = process.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

/**
 * Log in via API and return access token.
 */
async function loginViaApi(user: TestUser): Promise<string> {
  const response = await fetch(`${API_BASE_URL}/auth/login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: user.email, password: user.password }),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Login API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { access_token?: string };
  if (!data.access_token) {
    throw new Error('Login response missing access_token');
  }
  return data.access_token;
}

/**
 * Get or create one asset via API for the given user (same tenant). Returns the asset id.
 * Tries to use an existing asset first to avoid plan limit issues.
 * Use before tests that need at least one asset (e.g. marketplace publish, scheduled export).
 */
export async function createAssetViaApi(user: TestUser): Promise<string> {
  const token = await loginViaApi(user);

  // First, try to get an existing asset to avoid plan limit issues
  const listResponse = await fetch(`${API_BASE_URL}/assets/?limit=1`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (listResponse.ok) {
    const listData = (await listResponse.json()) as {
      results?: Array<{ id?: string }>;
      id?: string;
    }[];
    // Handle both paginated and non-paginated responses
    const assets = Array.isArray(listData) ? listData : listData.results || [];
    if (assets.length > 0 && assets[0].id) {
      return assets[0].id;
    }
  }

  // If no existing asset found, try to create a new one
  const key = `e2e-publish-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const response = await fetch(`${API_BASE_URL}/assets/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      key,
      name: 'E2E Publish Asset',
      description: 'Created by E2E for publish tests',
      visibility: 'INTERNAL',
    }),
  });
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Create asset API failed: ${response.status} ${body}`);
  }
  const data = (await response.json()) as { id?: string };
  if (!data.id) {
    throw new Error('Create asset response missing id');
  }
  return data.id;
}

/**
 * Clean up old E2E scheduled exports to avoid plan limit issues.
 * Deletes scheduled exports with names starting with "e2e-se-".
 * Use before tests that need to create a new scheduled export.
 */
export async function cleanupOldScheduledExports(user: TestUser): Promise<void> {
  const token = await loginViaApi(user);

  // List all scheduled exports
  const listResponse = await fetch(`${API_BASE_URL}/scheduled-exports/`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (!listResponse.ok) {
    // If listing fails, continue - this is not critical
    return;
  }

  const listData = (await listResponse.json()) as {
    results?: Array<{ id?: string; name?: string }>;
  };
  const exports = Array.isArray(listData) ? listData : listData.results || [];

  // Delete old E2E test scheduled exports
  for (const exportItem of exports) {
    if (exportItem.id && exportItem.name && exportItem.name.startsWith('e2e-se-')) {
      try {
        await fetch(`${API_BASE_URL}/scheduled-exports/${exportItem.id}/`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
        });
      } catch (error) {
        // Ignore deletion errors - continue cleaning up others
      }
    }
  }
}
