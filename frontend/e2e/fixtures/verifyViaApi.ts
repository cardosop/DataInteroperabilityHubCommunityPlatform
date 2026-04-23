/**
 * `verifyViaApi` — post-UI-action cross-check against the REST API.
 *
 * The dual-channel story: after a test drives the UI to create or mutate
 * something, immediately call `verifyViaApi(page, endpoint, expected)` to
 * confirm the backend actually persisted it. A passing UI toast + a 404 on
 * `/api/v1/<resource>/<id>/` is exactly the hidden-failure class this work
 * exists to kill.
 *
 * Landed in PR 2 unused. PR 7a-7d threads it into the 28 Tier-1 specs, one
 * verify-call per write operation.
 *
 * Auth gotcha (the reason this is not just `page.request.get(...)`)
 * -------------------------------------------------------------------
 * Meshant stores the JWT access_token in localStorage, not a cookie. When
 * Playwright's `page.request.get(...)` is called, it inherits cookies from
 * the page context but does NOT read localStorage. The Bearer header must
 * be set explicitly. This helper does that extraction + header injection
 * so callers don't have to think about it. See
 * /home/ph/.claude/plans/create-a-comprehensive-and-piped-fiddle.md
 * Review Finding #4 for the full backstory.
 */

import type { Page } from '@playwright/test';

/** The "expected" argument can be:
 *   - a Partial<T> mapping key → expected value (exact equality)
 *   - a predicate function receiving the parsed JSON body and returning bool
 *   - an async predicate (for checks that want to await further I/O)
 */
export type VerifyExpectation<T extends object> =
  | Partial<T>
  | ((body: T) => boolean | Promise<boolean>);

export interface VerifyViaApiOptions {
  /**
   * If true, do not throw when the endpoint returns 4xx. Useful for
   * negative-path verifications like "tenant B cannot see tenant A's asset"
   * where 404 is the SUCCESS signal.
   *
   * Default false — most callers want any non-2xx to fail loud.
   */
  expectFailure?: boolean;

  /** Override the auth extraction. Rarely needed; used by _guards.spec.ts. */
  authHeaderOverride?: Record<string, string>;
}

async function extractBearerHeaders(
  page: Page,
  override?: Record<string, string>,
): Promise<Record<string, string>> {
  if (override !== undefined) return override;
  // `page.evaluate` runs in the browser context where `localStorage` is a
  // global. The e2e tsconfig does not include the DOM lib (intentionally —
  // the rest of the Playwright code is Node-side), so we cast locally to
  // avoid pulling a redundant lib into the global type environment.
  const token = await page.evaluate<string | null>(
    () =>
      (globalThis as unknown as { localStorage?: { getItem: (k: string) => string | null } })
        .localStorage?.getItem('access_token') ?? null,
  );
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

function formatKey(k: string): string {
  return `\`${k}\``;
}

/**
 * Pure matcher — returns null when `body` satisfies `expected`, otherwise
 * returns a human-readable mismatch message. Exposed so the self-test suite
 * can exercise every branch without a browser or network.
 *
 * Equality rules:
 *   * Object.is for primitives and non-JSON-serializable values.
 *   * Fallback: JSON.stringify structural equality for objects/arrays.
 */
export async function matchBody<T extends object>(
  body: T,
  expected: VerifyExpectation<T>,
): Promise<string | null> {
  if (typeof expected === 'function') {
    const ok = await expected(body);
    if (!ok) {
      return `predicate returned false. Body: ${JSON.stringify(body)}`;
    }
    return null;
  }
  for (const [key, want] of Object.entries(expected)) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const have = (body as any)[key];
    if (Object.is(have, want)) continue;
    if (JSON.stringify(have) === JSON.stringify(want)) continue;
    return (
      `body mismatch on ${formatKey(key)}: ` +
      `expected=${JSON.stringify(want)}, actual=${JSON.stringify(have)}`
    );
  }
  return null;
}

/**
 * Fetch `endpoint` using the page's bearer token, then assert on the body.
 * Returns the parsed body on success so callers can chain further checks.
 */
export async function verifyViaApi<T extends object>(
  page: Page,
  endpoint: string,
  expected: VerifyExpectation<T>,
  options: VerifyViaApiOptions = {},
): Promise<T> {
  const headers = await extractBearerHeaders(page, options.authHeaderOverride);
  const res = await page.request.get(endpoint, { headers });
  const status = res.status();

  if (!options.expectFailure && !res.ok()) {
    let text = '';
    try {
      text = await res.text();
    } catch {
      /* ignore — some responses have no body */
    }
    throw new Error(
      `verifyViaApi: GET ${endpoint} returned ${status}. ` +
        `Expected a 2xx response. Body preview: ${text.slice(0, 400)}`,
    );
  }

  if (options.expectFailure && res.ok()) {
    throw new Error(
      `verifyViaApi: GET ${endpoint} returned ${status} but ` +
        `expectFailure=true asked for a non-2xx response.`,
    );
  }

  // parse once; predicate callers may still want the body
  const body = (await res.json()) as T;
  const mismatch = await matchBody(body, expected);
  if (mismatch !== null) {
    throw new Error(
      `verifyViaApi: ${endpoint} ${mismatch}\nfull body: ${JSON.stringify(body)}`,
    );
  }
  return body;
}
