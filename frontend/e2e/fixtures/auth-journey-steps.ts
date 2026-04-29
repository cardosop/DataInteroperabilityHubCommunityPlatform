/**
 * Shared step logic for auth journey E2E tests (JOURNEY-AUTH-001, 003, 004).
 * Used by journeys/auth/JOURNEY-AUTH-*.spec.ts and auth-visitor-journeys.spec.ts (thin wrapper).
 * No mocks/stubs; real backend only.
 */

import { Page } from '@playwright/test';
import type { TestUser } from '../setup/create-test-user';
import { clearAuthStorage, loginUser, loginViaApi } from './auth';
import { E2E_TOKEN_HEADER } from './e2e-token';

// Node fetch needs absolute URL; align with auth.ts (VITE_API_BASE_URL can be relative)
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${String(process.env.VITE_PROXY_TARGET).replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith?.('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

/**
 * Resolve the MailHog base URL with sensible defaults per target environment.
 *
 *   1. If `MAILHOG_URL` env var is set explicitly, honour it (operator override).
 *   2. Else if running against an external/staging target (PLAYWRIGHT_BASE_URL is
 *      non-localhost), default to the staging proxy at `${API_BASE}/test/mailhog`.
 *      This proxy is gated by `X-E2E-Token` (E2E_TEST_SECRET) which the spec
 *      already attaches via `buildMailhogRequestHeaders`; so the moment a
 *      developer or CI job runs against staging with a valid `E2E_TEST_SECRET`,
 *      JOURNEY-AUTH-003 Success is exercised end-to-end without manual env
 *      plumbing. Cycle-2026-04-29 skip fix: the previous default of
 *      `http://localhost:8025` caused the spec to skip on every external-target
 *      run unless deploy.yml's MAILHOG_URL injection was active.
 *   3. Else (local dev / docker-compose), keep `http://localhost:8025` so the
 *      MailHog container in `docker-compose.test.yml` is the sink.
 *
 * Pure helper — exported so unit tests can pin the boundary.
 */
export function resolveMailhogBaseUrl(env: NodeJS.ProcessEnv = process.env): string {
  if (env.MAILHOG_URL) return env.MAILHOG_URL;
  const playwrightBase = env.PLAYWRIGHT_BASE_URL ?? '';
  const isExternalTarget = /^https?:\/\/(?!localhost|127\.|0\.0\.0\.0)/.test(playwrightBase);
  if (isExternalTarget) {
    const apiBase = env.E2E_API_BASE_URL
      || (env.VITE_PROXY_TARGET ? `${String(env.VITE_PROXY_TARGET).replace(/\/$/, '')}/api/v1` : null)
      || `${playwrightBase.replace(/\/$/, '')}/api/v1`;
    return `${apiBase.replace(/\/$/, '')}/test/mailhog`;
  }
  return 'http://localhost:8025';
}

const MAILHOG_BASE_URL = resolveMailhogBaseUrl();

/** True when MAILHOG_BASE_URL points at a non-localhost host (i.e. the
 * staging proxy). In that case the proxy is token-gated and we MUST
 * send `X-E2E-Token`. Locally the MailHog container has no auth so we
 * omit the header (sending it would only add noise to local request logs).
 *
 * Pure helper — exported so unit tests can pin the boundary.
 */
export function isMailhogProxyUrl(url: string): boolean {
  return /^https?:\/\/(?!localhost|127\.|0\.0\.0\.0)/.test(url);
}

/** Build the header bag for a MailHog read. Pure: takes URL + token, returns
 * a plain object suitable for `fetch(..., { headers })`.
 */
export function buildMailhogRequestHeaders(
  url: string,
  e2eTestSecret: string | undefined,
): Record<string, string> {
  if (!isMailhogProxyUrl(url)) return {};
  const token = e2eTestSecret ?? '';
  if (!token) return {};
  return { [E2E_TOKEN_HEADER]: token };
}

const REGISTER_RETRIES = 4;
const REGISTER_RETRY_DELAYS_MS = [2000, 4000, 6000];

export function uniqueEmail(prefix = 'e2e_visitor'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}@example.com`;
}

export function strongPassword(): string {
  return `TestPass${Math.floor(1000 + Math.random() * 9000)}`;
}

function isRetryableRegisterError(err: unknown): boolean {
  const msg = String((err as Error)?.message ?? (err as { cause?: Error })?.cause?.message ?? '');
  // Connection errors are retryable
  if (/ECONNRESET|ECONNREFUSED|fetch failed|socket hang up|network/i.test(msg)) return true;
  // 503 "Registration is temporarily unavailable" is transient under parallel E2E load
  if (/Register API failed: 503/i.test(msg)) return true;
  // 500 with statement timeout / deadlock — DB overloaded under parallel E2E load
  if (/Register API failed: 500/i.test(msg) && /statement timeout|canceling statement|deadlock|too many/i.test(msg)) return true;
  return false;
}

export async function registerViaApi(user: {
  email: string;
  password: string;
  name: string;
  tenant_id?: string | null;
}): Promise<void> {
  let lastErr: unknown;
  for (let i = 0; i < REGISTER_RETRIES; i++) {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(user),
      });
      if (!response.ok) {
        // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
        const body = await response.text().catch(() => '');
        throw new Error(`Register API failed: ${response.status} ${body}`);
      }
      return;
    } catch (err) {
      lastErr = err;
      if (i < REGISTER_RETRIES - 1 && isRetryableRegisterError(err)) {
        const delay = REGISTER_RETRY_DELAYS_MS[i] ?? 8000;
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}

export async function requestPasswordResetViaApi(email: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/auth/password-reset/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
    const body = await response.text().catch(() => '');
    throw new Error(`Password reset API failed: ${response.status} ${body}`);
  }
}

/** MailHog v1 returns full message (Content.Headers, Content.Body, MIME.Parts); v2 list may omit body. */
interface MailHogMessage {
  ID?: string;
  to?: Array<{ mailbox?: string; domain?: string }>;
  Content?: {
    Headers?: Record<string, string[]>;
    Body?: string;
  };
  MIME?: { Parts?: Array<{ Body?: string }> };
}

/** URL may be line-wrapped in email body (e.g. password-\\nreset).
 *
 * The token separator is intentionally `[?#]`: the production email
 * template at hub/apps/notifications/templates.py:129 uses `#token=`
 * (fragment) so the token never travels to backend access logs or
 * Referer headers — that's a deliberate security choice. The frontend
 * page at PasswordResetConfirmPage.tsx accepts the token from EITHER
 * `location.search` (`?token=`) OR `location.hash` (`#token=`), so a
 * future template change to `?token=` would still work end-to-end.
 * Matching both keeps the spec a faithful catch for whichever shape
 * the email currently uses.
 */
const RESET_LINK_REGEX =
  /https?:\/\/[^\s"']*auth\/password[\s\r\n-]*reset\/confirm[?#]token=[0-9a-fA-F-]{36}/;

function extractResetLinkFromMessage(item: MailHogMessage): string | null {
  const body =
    item?.Content?.Body ??
    item?.MIME?.Parts?.map((p) => p?.Body)
      .filter(Boolean)
      .join('\n') ??
    '';
  const candidate = `${JSON.stringify(item?.Content ?? item?.MIME ?? {})}\n${body}`;
  const match = candidate.match(RESET_LINK_REGEX);
  if (!match?.[0]) return null;
  // Use `+` (not `*`): with the `g` flag, a zero-width match fires at every
  // position where the lookahead succeeds, and substituting `-` for an
  // empty match inserts a STRAY hyphen — turning the production URL
  // `password-\r\nreset/confirm` into `password--reset/confirm` which 404s.
  // `+` requires at least one wrapping char to consume, so the substitution
  // only fires on the actual line-wrap and never on the join-point itself.
  return match[0].replace(/[\s\r\n-]+(?=reset\/confirm)/g, '-');
}

function getToEmailFromMessage(item: MailHogMessage): string {
  const toRaw =
    item?.Content?.Headers?.['To'] ?? (item?.Content?.Headers as Record<string, string[]>)?.To;
  if (toRaw !== undefined) {
    const s = Array.isArray(toRaw) ? toRaw[0] : String(toRaw);
    if (s) return s;
  }
  const path =
    item?.to?.[0] ?? (item as { To?: Array<{ Mailbox?: string; Domain?: string }> })?.To?.[0];
  if (path) {
    const m =
      (path as { mailbox?: string; Mailbox?: string }).mailbox ??
      (path as { Mailbox?: string }).Mailbox;
    const d =
      (path as { domain?: string; Domain?: string }).domain ?? (path as { Domain?: string }).Domain;
    if (m ?? d) return `${m ?? ''}@${d ?? ''}`;
  }
  return '';
}

function messageToMatches(item: MailHogMessage, toEmail: string): boolean {
  return getToEmailFromMessage(item).includes(toEmail);
}

/** Poll MailHog v1 for the password-reset email addressed to `toEmail`,
 * returning the reset URL on success.
 *
 * Only the v1 list endpoint is used. The previous v2 fallback was
 * silently broken: v2 list responses omit `Content.Body`, so the
 * regex match never fired and the loop ran out the full timeout
 * instead of producing a useful error. Drop the dead branch — the
 * proxy at `/api/v1/test/mailhog/messages/` only exposes v1 anyway.
 *
 * On staging, `MAILHOG_BASE_URL` points at the token-gated Django
 * proxy (`/api/v1/test/mailhog`). The X-E2E-Token header is added by
 * `buildMailhogRequestHeaders` ONLY when the URL is non-localhost,
 * so local-dev runs against a plain MailHog container still work
 * unchanged.
 */
export async function waitForPasswordResetEmail(
  toEmail: string,
  timeoutMs = 60_000
): Promise<string> {
  const started = Date.now();
  const headers = buildMailhogRequestHeaders(MAILHOG_BASE_URL, process.env.E2E_TEST_SECRET);
  while (Date.now() - started < timeoutMs) {
    try {
      const v1Resp = await fetch(`${MAILHOG_BASE_URL}/api/v1/messages`, { headers });
      if (!v1Resp.ok) {
        // Surface non-200s loudly. Previously the v2 fallback masked
        // a misconfigured proxy (e.g. token mismatch returning 404)
        // as "no email yet"; now the test fails fast with diagnostics.
        throw new Error(
          `MailHog list returned HTTP ${v1Resp.status}. ` +
            `URL: ${MAILHOG_BASE_URL}/api/v1/messages. ` +
            `If targeting the staging proxy, verify E2E_TEST_SECRET matches ` +
            `STAGING_E2E_TEST_SECRET on the staging deployment.`,
        );
      }
      const v1Data = (await v1Resp.json()) as MailHogMessage[] | { items?: MailHogMessage[] };
      const list: MailHogMessage[] = Array.isArray(v1Data)
        ? v1Data
        : ((v1Data as { items?: MailHogMessage[] })?.items ?? []);
      for (const item of list) {
        if (!messageToMatches(item, toEmail)) continue;
        const link = extractResetLinkFromMessage(item);
        if (link) return link;
        if (item.ID) {
          const detailResp = await fetch(
            `${MAILHOG_BASE_URL}/api/v1/messages/${item.ID}`,
            { headers },
          );
          if (detailResp.ok) {
            const full = (await detailResp.json()) as MailHogMessage;
            const fullLink = extractResetLinkFromMessage(full);
            if (fullLink) return fullLink;
          }
        }
      }
    } catch (e) {
      throw new Error(`MailHog is not reachable at ${MAILHOG_BASE_URL}. Root error: ${String(e)}`);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(
    `Timed out waiting for password reset email to ${toEmail}. Ensure worker-service and SMTP/MailHog are configured.`
  );
}

/** Run JOURNEY-AUTH-004 success: unauthenticated user accesses public resources */
export async function runJOURNEY_AUTH_004_Success(page: Page): Promise<void> {
  await clearAuthStorage(page);
  await page.goto('/public', { waitUntil: 'domcontentloaded' });
  if (!page.url().includes('/public')) {
    throw new Error('Expected /public, got ' + page.url());
  }
  const heading = page.getByRole('heading', { name: /Public Resources/i });
  await heading.waitFor({ state: 'visible', timeout: 10_000 });
  await page
    .locator('a')
    .filter({ hasText: 'OpenAPI' })
    .first()
    .waitFor({ state: 'visible', timeout: 5000 });
}

/**
 * Wait for register page to be ready (capabilities loaded).
 * RegistrationRoute shows LoadingSpinner for up to 30s; neither "Create account" nor
 * ".unavailable-page, [data-testid="unavailable-page"] h1" exist during loading. Race: terminal state OR loading hidden.
 */
export async function waitForRegisterPageReady(page: Page, timeoutMs = 35_000): Promise<void> {
  const createHeading = page.getByRole('heading', { name: 'Create account' });
  const unavailableHeading = page.locator('.unavailable-page, [data-testid="unavailable-page"] h1');
  const loadingSpinner = page.locator('.loading-spinner-container');

  // Race: terminal state (register/unavailable) OR loading spinner disappears.
  // When loading never appears (fast path), createHeading/unavailableHeading win.
  // When loading is visible, it hides when capabilities resolve, then terminal state appears.
  await Promise.race([
    createHeading.waitFor({ state: 'visible', timeout: timeoutMs }),
    unavailableHeading.waitFor({ state: 'visible', timeout: timeoutMs }),
    loadingSpinner.waitFor({ state: 'hidden', timeout: timeoutMs }),
  ]);

  // If loading hid first, terminal state appears in same render
  // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
  const hasCreate = await createHeading.isVisible().catch(() => false);
  // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
  const hasUnavailable = await unavailableHeading.isVisible().catch(() => false);
  if (!hasCreate && !hasUnavailable) {
    await Promise.race([
      createHeading.waitFor({ state: 'visible', timeout: 5_000 }),
      unavailableHeading.waitFor({ state: 'visible', timeout: 5_000 }),
    ]);
  }
}

/**
 * Assert that the given user has a personal tenant.
 * Phase 11.1: access_token is no longer in localStorage. Uses loginViaApi from Node.js
 * to get a fresh token, then fetches /auth/me/ to verify tenant_id.
 */
export async function assertUserHasPersonalTenant(_page: Page, user?: TestUser): Promise<void> {
  // Try to get email/password from the user argument; fall back to reading email from localStorage
  let email: string;
  let password: string;
  if (user?.email && user?.password) {
    email = user.email;
    password = user.password;
  } else {
    throw new Error(
      'assertUserHasPersonalTenant: user credentials required (Phase 11.1: access_token no longer in localStorage)'
    );
  }
  const apiAuth = await loginViaApi(email, password);
  const res = await fetch(`${API_BASE_URL}/auth/me/`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${apiAuth.access_token}` },
  });
  if (!res.ok) {
    // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
    const body = await res.text().catch(() => '');
    throw new Error(`assertUserHasPersonalTenant: /auth/me/ failed: ${res.status} ${body}`);
  }
  const me = (await res.json()) as { tenant_id?: string | null; [k: string]: unknown };
  if (!me.tenant_id) {
    throw new Error(
      `assertUserHasPersonalTenant: Expected tenant_id in /auth/me/ (personal tenant). Got: ${JSON.stringify(me)}`
    );
  }
}

/**
 * After clicking the Register form's submit button, wait for ONE of three
 * outcomes: the redirect to /login (success), an error/alert displayed inline
 * (server rejected — 4xx/5xx, validation, rate-limit), or a timeout (neither
 * happened — backend hung).
 *
 * The previous "wait 60 s for /login" pattern in JOURNEY-AUTH-001 Security
 * tests turned a 500 / 503 from /auth/register/ into a meaningless
 * `TimeoutError: page.waitForURL`, masking the real failure mode and
 * burning the full 60 s budget on every flake. This helper:
 *
 *   1. surfaces the inline error text in the thrown message so a single
 *      report line names the cause instead of "test timed out";
 *   2. surfaces *which* outcome was missed when neither path fires (URL
 *      stays where it is — usually /register), so the next reviewer can
 *      tell auth-rate-limit from FE-stuck-spinner from network blip.
 *
 * Pure helper-shaped — exported for reuse across every register-then-wait
 * call-site (JOURNEY-AUTH-001 Security, etc.) so the diagnostic shape
 * doesn't drift between specs.
 */
export async function waitForRegisterRedirectOrError(
  page: Page,
  options: { timeout?: number } = {}
): Promise<void> {
  const timeout = options.timeout ?? 60_000;
  const errorLocator = page
    .locator('.error-message, .error-display, [data-testid="error-display"], [role="alert"]')
    .first();
  const postSubmit = await Promise.race([
    page
      .waitForURL((url) => url.pathname === '/login', { timeout })
      .then(() => 'redirect' as const),
    errorLocator
      .waitFor({ state: 'visible', timeout })
      .then(() => 'error' as const),
    // intentional: race uses .catch on the outer Promise.race to convert any rejection into a 'timeout' literal so the caller sees a single, classified outcome rather than three different rejection shapes.
  ]).catch(() => 'timeout' as const);

  if (postSubmit === 'error') {
    // intentional: textContent on a freshly-resolved locator is best-effort —
    // primary failure assertion is the throw below; missing text just yields ''.
    const errText = await errorLocator.textContent().catch(() => '');
    throw new Error(
      `Registration failed — error shown on page: ${(errText ?? '').slice(0, 300)}`
    );
  }
  if (postSubmit === 'timeout') {
    throw new Error(
      `Registration: neither /login redirect nor error display appeared within ${timeout}ms. ` +
        `Current URL: ${page.url()}. Likely cause: backend register endpoint hung ` +
        `(staging worker rate-limit, DB pool exhausted, or 5xx burst); the FE ` +
        `submit handler awaits authService.register() and never reached the ` +
        `setSuccess+navigate('/login') branch.`
    );
  }
}

/** Run JOURNEY-AUTH-001 success: register via UI then login */
export async function runJOURNEY_AUTH_001_Success(page: Page): Promise<void> {
  const email = uniqueEmail('e2e_register');
  const password = strongPassword();
  const name = 'E2E Visitor Register';
  await clearAuthStorage(page);
  await page.goto('/register', { waitUntil: 'domcontentloaded' });
  if (page.url().includes('/login')) {
    const createLink = page.getByRole('link', { name: /Create an account/i });
    await createLink.waitFor({ state: 'visible', timeout: 35_000 });
    await createLink.click();
    await page.waitForURL((url) => url.pathname.includes('/register'), { timeout: 5000 });
  }
  await waitForRegisterPageReady(page);
  if (page.url().includes('/unavailable')) {
    throw new Error(
      'Registration unavailable (capabilities/schema). JOURNEY-AUTH-001 requires registration to be enabled. ' +
        'Enable registration in deployment capabilities or schema.'
    );
  }
  await page.fill('input#name', name);
  await page.fill('input#email', email);
  await page.fill('input#password', password);
  await page.click('button[type="submit"]');
  // Registration navigates to /login with state on success. If the API fails
  // (500, 503, rate-limit, validation), the page stays on /register with an
  // error display. Race redirect vs error so we don't burn 60 s waiting for
  // a redirect that may never come — see waitForRegisterRedirectOrError.
  await waitForRegisterRedirectOrError(page, { timeout: 60_000 });

  await page.locator('.success-message').waitFor({ state: 'visible', timeout: 15_000 });
  const successText = await page.locator('.success-message').textContent();
  if (!successText?.includes('Account created')) {
    throw new Error('Expected "Account created" success message');
  }
  const user: TestUser = { email, password, name };
  await loginUser(page, user);
  await page.locator('.app-header, [data-testid="app-header"]').waitFor({ state: 'visible', timeout: 10_000 });
  await assertUserHasPersonalTenant(page, user);
}

/** Run JOURNEY-AUTH-003 success: password reset request + confirm via email (requires MailHog) */
export async function runJOURNEY_AUTH_003_Success(page: Page): Promise<void> {
  // Reachability probe must mirror the spec-file probe at JOURNEY-AUTH-003.spec.ts:
  // v1 (NOT v2) so the staging proxy at /api/v1/test/mailhog (which only exposes
  // v1) succeeds; v2 list responses also omit Content.Body which would silently
  // break the actual flow downstream. Auth header is sent only when targeting
  // the staging proxy — local-dev MailHog has no auth.
  const probeHeaders = isMailhogProxyUrl(MAILHOG_BASE_URL)
    ? buildMailhogRequestHeaders(MAILHOG_BASE_URL, process.env.E2E_TEST_SECRET)
    : {};
  let mailhogReachable = false;
  try {
    const probe = await fetch(`${MAILHOG_BASE_URL}/api/v1/messages`, {
      headers: probeHeaders,
    });
    if (probe.ok) mailhogReachable = true;
  } catch {
    // intentional: auth-journey shared step uses best-effort waits on optional UI elements; primary auth-success assertion is in the calling spec.
    // ignore
  }
  if (!mailhogReachable) {
    throw new Error(
      `MailHog not reachable at ${MAILHOG_BASE_URL}. ` +
        `For local: docker compose up -d mailhog (then SMTP_HOST=mailhog SMTP_PORT=1025). ` +
        `For staging: confirm MAILHOG_URL points at the proxy and X-E2E-Token is correct.`
    );
  }
  const email = uniqueEmail('e2e_pwreset');
  const initialPassword = strongPassword();
  const newPassword = strongPassword();
  const name = 'E2E Password Reset User';
  await registerViaApi({ email, password: initialPassword, name });
  await clearAuthStorage(page);
  await page.goto('/password-reset', { waitUntil: 'domcontentloaded' });
  const resetHeading = page.getByRole('heading', { name: /Reset password/i });
  const unavailableHeading = page.locator('.unavailable-page, [data-testid="unavailable-page"] h1');
  // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
  await Promise.race([
    resetHeading.waitFor({ state: 'visible', timeout: 35_000 }),
    unavailableHeading.waitFor({ state: 'visible', timeout: 35_000 }),
  ]).catch(() => null);
  if (page.url().includes('/unavailable')) {
    throw new Error(
      'Password reset unavailable (capabilities/schema). JOURNEY-AUTH-003 requires password reset to be enabled. ' +
        'Enable password reset in deployment capabilities or schema.'
    );
  }
  // Capabilities load can take up to 30s; ensure reset form is visible
  await resetHeading.waitFor({ state: 'visible', timeout: 35_000 });
  await page.fill('input#email', email);
  await page.click('button[type="submit"]');
  // Wait for either success or error (backend may return error if password reset not enabled).
  // Timeout raised from 25s to 45s: the API can take up to ~20s to restart during parallel
  // E2E load, causing the form-submit response to arrive late but still within the window.
  const successOrError = page.locator('.success-message, .error-message').first();
  await successOrError.waitFor({ state: 'visible', timeout: 45_000 });
  if (await page.locator('.error-message').isVisible()) {
    const errText = await page.locator('.error-message').textContent();
    throw new Error(
      `Backend returned error for password reset. ${errText || 'Capability may be disabled.'} ` +
        'JOURNEY-AUTH-003 requires password reset to be enabled. Enable in deployment capabilities or schema.'
    );
  }
  // UI submit already triggered password reset and enqueued send_password_reset_email (job_low)
  const resetLink = await waitForPasswordResetEmail(email, 120_000);
  const url = new URL(resetLink);
  // Token can live in either the query (`?token=`) or the fragment
  // (`#token=`). Production currently uses fragment for security
  // (fragments never reach the server / access logs / Referer headers);
  // both forms are accepted by `PasswordResetConfirmPage.tsx`.
  const fragmentParams = new URLSearchParams(url.hash.replace(/^#/, ''));
  const token = url.searchParams.get('token') ?? fragmentParams.get('token') ?? '';
  if (!token) {
    throw new Error(
      `JOURNEY-AUTH-003: could not extract token from reset link "${resetLink}". ` +
        `Expected the token to live in either the URL query or fragment. ` +
        `Verify hub/apps/notifications/templates.py emits one of those forms.`,
    );
  }
  // Preserve the same separator the email used so we exercise the
  // same client-side code path a real user would. The frontend reads
  // both forms, but mirroring the email keeps coverage honest.
  const separator = url.hash ? '#' : '?';
  const pathAndSearch = `/password-reset/confirm${separator}token=${encodeURIComponent(token)}`;
  await page.goto(pathAndSearch, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('domcontentloaded');
  const setPwHeading = page.getByRole('heading', { name: /Set a new password/i });
  // Wait for form or error (invalid/expired token).
  // Timeout raised from 25s to 45s: CapabilityRoute on /password-reset/confirm fetches
  // capabilities from the backend. Under parallel E2E load, capability fetch can take up
  // to ~20s to restart, pushing total wait beyond 25s. 45s provides safe headroom.
  const formOrError = await Promise.race([
    setPwHeading.waitFor({ state: 'visible', timeout: 45_000 }).then(() => 'form'),
    page.locator('.error-message, .error-display, [data-testid="error-display"]').filter({ hasText: /invalid|expired/i }).first()
      .waitFor({ state: 'visible', timeout: 45_000 }).then(() => 'error'),
  ]).catch(() => 'timeout' as const);
  if (formOrError === 'error') {
    // intentional: auth journey steps wrap optional UI element waits; primary auth-success assertion is in the calling spec.
    const errText = await page.locator('.error-message, .error-display, [data-testid="error-display"]').first().textContent().catch(() => '');
    throw new Error(
      `Token invalid or expired. ${errText}. Ensure MailHog is running and email was captured.`
    );
  }
  if (formOrError === 'timeout') {
    throw new Error(
      'Set new password form not visible within 45s. Token may be invalid or page structure changed.'
    );
  }
  await page.fill('input#new_password', newPassword);
  await page.click('button[type="submit"]');
  // 35s: must exceed apiClient timeout (30s) so we see success/error before test times out
  const confirmResult = page.locator('.success-message, .error-message').first();
  await confirmResult.waitFor({ state: 'visible', timeout: 35_000 });
  if (await page.locator('.error-message').isVisible()) {
    const errText = await page.locator('.error-message').textContent();
    throw new Error(
      `Password reset confirm failed: ${errText || 'Backend returned error (e.g. rate limit or invalid token).'}`
    );
  }
  await page.goto('/login', { waitUntil: 'domcontentloaded' });
  const user: TestUser = { email, password: newPassword, name };
  await loginUser(page, user);
  await page.locator('.app-header, [data-testid="app-header"]').waitFor({ state: 'visible', timeout: 10_000 });
}
