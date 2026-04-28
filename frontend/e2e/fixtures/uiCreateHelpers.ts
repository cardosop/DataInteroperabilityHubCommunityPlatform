/**
 * Phase 226 E2 — UI-create flow helpers that auto-register the new ID
 * with `createdResources` (or the legacy `cleanup` registry).
 *
 * Most existing helpers under `fixtures/api-assets.ts` provision via the
 * REST API — fast, deterministic, and they already accept a `cleanup`
 * argument. The gap E2 closes is the *UI-create* path: a spec that
 * exercises the actual asset/contract/dataset/listing form, watches
 * Playwright redirect to the detail page, and wants the new ID
 * registered for auto-teardown.
 *
 * Symmetry with `api-assets.ts`: each UI helper accepts the same
 * `{ cleanup?: CleanupRegistry | CreatedResourcesRegistry }` shape so
 * spec code is interchangeable: pass either registry object, the helper
 * tracks the result. Failure modes (form rejection, redirect missing,
 * id-parse failure) raise `Error` with a contextual message — never
 * silently return the wrong id.
 *
 * No mocks. Real backend only.
 */

import type { Page } from '@playwright/test';
import type { TestUser } from '../setup/create-test-user';
import type { CleanupRegistry } from './test-data-cleanup';
import type { CreatedResourcesRegistry } from './createdResources';

/** Either registry shape — both expose `track({ type, id, owner })`. */
export type AnyCleanupRegistry = CleanupRegistry | CreatedResourcesRegistry;

// ---------------------------------------------------- pure logic

/**
 * Extract a UUID-shaped resource id from a URL path of the form
 * `/<resource>/<id>` (with optional trailing slash, query, or hash).
 *
 * Returns the id, or null if the path does not end in a parseable id
 * segment. Pure for testability — every spec that needs the ID parses
 * via this helper instead of writing a one-off regex.
 *
 * Why a permissive UUID/slug shape (not strict 36-char UUID): some
 * resources expose human-friendly slugs (`my-dataset-key`) in the URL
 * path. We accept any path segment that contains at least one
 * alphanumeric character and no slashes. The caller is responsible for
 * cross-checking the shape against the resource type's id contract
 * (e.g. via `verifyViaApi` before relying on it).
 */
export function extractResourceIdFromUrl(
  url: string,
  resourcePath: string,
): string | null {
  if (typeof url !== 'string' || typeof resourcePath !== 'string') return null;
  const normPath = resourcePath.replace(/^\/+|\/+$/g, '');
  // Match `/<resourcePath>/<id>` followed by end / `/` / `?` / `#`.
  const escaped = normPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp(`/${escaped}/([^/?#]+)(?:[/?#]|$)`);
  const m = url.match(re);
  if (!m) return null;
  const id = decodeURIComponent(m[1]);
  // Reject reserved suffix segments that look like routes, not IDs
  // (e.g. `/assets/create`, `/contracts/import`). We do this by
  // filtering against the small set of known sub-routes the app uses.
  if (['create', 'new', 'import', 'edit'].includes(id.toLowerCase())) return null;
  return id;
}

/** Default poll deadline for "wait for redirect to detail page" — kept
 * small (15s) so a missing redirect surfaces fast rather than burning
 * the whole spec timeout. */
export const REDIRECT_TIMEOUT_MS_DEFAULT = 15_000;

// ---------------------------------------------------- UI helpers

interface CreateAssetUiOptions {
  name: string;
  key: string;
  /** Cleanup registry (either `cleanup` from test-data-cleanup or
   * `createdResources` from guardedTest). When supplied, the new asset
   * id is auto-registered for teardown. */
  cleanup?: AnyCleanupRegistry;
  /** Owner that should appear in the cleanup record so teardown re-
   * logs-in as the right user. Defaults to inferring from page.context()
   * storageState — but explicit-is-better-than-implicit so the helper
   * requires it when `cleanup` is supplied. */
  owner?: TestUser;
  /** How long to wait for the form-submit redirect. */
  timeoutMs?: number;
}

/**
 * Drive the Asset Create form via Playwright UI, wait for the redirect
 * to `/assets/{id}`, parse the id, and (if a registry is supplied)
 * register the asset for auto-teardown. Returns the new asset id.
 *
 * Throws when:
 *   * the redirect to `/assets/<id>` does not happen within `timeoutMs`
 *   * the URL after redirect does not contain a parseable id
 *   * the form rejects (visible `.error-display, [data-testid="error-display"]`)
 *
 * The helper deliberately does NOT itself call `loginUser` — the caller
 * is expected to be authenticated already (via guardedTest's setup-auth
 * project, or a manual login call). Mixing auth into a create helper
 * makes the failure modes harder to read.
 */
export async function createAssetViaUi(
  page: Page,
  options: CreateAssetUiOptions,
): Promise<string> {
  if (options.cleanup && !options.owner) {
    throw new Error(
      'createAssetViaUi: `owner` is required when `cleanup` is supplied — ' +
      'teardown re-logs-in as the owner before issuing DELETE.',
    );
  }
  await page.goto('/assets/create', { waitUntil: 'domcontentloaded' });
  await page.fill('input[id="asset-name"]', options.name);
  await page.fill('input[id="asset-key"]', options.key);
  await page.getByRole('button', { name: /^Create$/i }).click();

  const timeout = options.timeoutMs ?? REDIRECT_TIMEOUT_MS_DEFAULT;
  // Wait for the redirect to a detail page. We pin via a regex so a
  // soft-redirect to an error page doesn't false-pass.
  await page.waitForURL(/\/assets\/[^/]+$/, { timeout });

  const id = extractResourceIdFromUrl(page.url(), '/assets');
  if (!id) {
    throw new Error(
      `createAssetViaUi: redirect URL ${page.url()} did not contain a parseable asset id`,
    );
  }
  if (options.cleanup && options.owner) {
    options.cleanup.track({ type: 'asset', id, owner: options.owner });
  }
  return id;
}

interface CreateContractUiOptions {
  name: string;
  key: string;
  cleanup?: AnyCleanupRegistry;
  owner?: TestUser;
  timeoutMs?: number;
}

/** Drive the Contract Create form. Same shape as `createAssetViaUi`. */
export async function createContractViaUi(
  page: Page,
  options: CreateContractUiOptions,
): Promise<string> {
  if (options.cleanup && !options.owner) {
    throw new Error(
      'createContractViaUi: `owner` is required when `cleanup` is supplied',
    );
  }
  await page.goto('/contracts/create', { waitUntil: 'domcontentloaded' });
  await page.fill('input[id="contract-name"]', options.name);
  await page.fill('input[id="contract-key"]', options.key);
  await page.getByRole('button', { name: /^Create$/i }).click();
  const timeout = options.timeoutMs ?? REDIRECT_TIMEOUT_MS_DEFAULT;
  await page.waitForURL(/\/contracts\/[^/]+$/, { timeout });
  const id = extractResourceIdFromUrl(page.url(), '/contracts');
  if (!id) {
    throw new Error(
      `createContractViaUi: redirect URL ${page.url()} did not contain a parseable contract id`,
    );
  }
  if (options.cleanup && options.owner) {
    options.cleanup.track({ type: 'contract', id, owner: options.owner });
  }
  return id;
}
