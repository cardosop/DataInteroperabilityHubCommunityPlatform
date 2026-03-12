/**
 * Shared step logic for auth journey E2E tests (JOURNEY-AUTH-001, 003, 004).
 * Used by journeys/auth/JOURNEY-AUTH-*.spec.ts and auth-visitor-journeys.spec.ts (thin wrapper).
 * No mocks/stubs; real backend only.
 */

import { Page } from '@playwright/test';
import type { TestUser } from '../setup/create-test-user';
import { clearAuthStorage, loginUser } from './auth';

// Node fetch needs absolute URL; align with auth.ts (VITE_API_BASE_URL can be relative)
const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${String(process.env.VITE_PROXY_TARGET).replace(/\/$/, '')}/api/v1`
    : null) ||
  (process.env.VITE_API_BASE_URL?.startsWith?.('http') ? process.env.VITE_API_BASE_URL : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;
const MAILHOG_BASE_URL = process.env.MAILHOG_URL || 'http://localhost:8025';

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
  return /ECONNRESET|ECONNREFUSED|fetch failed|socket hang up|network/i.test(msg);
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

/** URL may be line-wrapped in email body (e.g. password-\\nreset). */
const RESET_LINK_REGEX =
  /https?:\/\/[^\s"']*auth\/password[\s\r\n-]*reset\/confirm\?token=[0-9a-fA-F-]{36}/;

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
  return match[0].replace(/[\s\r\n-]*(?=reset\/confirm)/g, '-');
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

/** Prefer v1 (full content); fallback to v2 list then fetch by id if needed. */
export async function waitForPasswordResetEmail(
  toEmail: string,
  timeoutMs = 60_000
): Promise<string> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      const v1Resp = await fetch(`${MAILHOG_BASE_URL}/api/v1/messages`);
      if (v1Resp.ok) {
        const v1Data = (await v1Resp.json()) as MailHogMessage[] | { items?: MailHogMessage[] };
        const list: MailHogMessage[] = Array.isArray(v1Data)
          ? v1Data
          : ((v1Data as { items?: MailHogMessage[] })?.items ?? []);
        for (const item of list) {
          if (!messageToMatches(item, toEmail)) continue;
          const link = extractResetLinkFromMessage(item);
          if (link) return link;
          if (item.ID) {
            const detailResp = await fetch(`${MAILHOG_BASE_URL}/api/v1/messages/${item.ID}`);
            if (detailResp.ok) {
              const full = (await detailResp.json()) as MailHogMessage;
              const fullLink = extractResetLinkFromMessage(full);
              if (fullLink) return fullLink;
            }
          }
        }
      } else {
        const v2Resp = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=50`);
        if (!v2Resp.ok) throw new Error(`MailHog API HTTP ${v2Resp.status}`);
        const v2Data = (await v2Resp.json()) as {
          items?: MailHogMessage[];
          messages?: MailHogMessage[];
        };
        const list = v2Data?.items ?? v2Data?.messages ?? [];
        for (const item of list) {
          if (!messageToMatches(item, toEmail)) continue;
          const link = extractResetLinkFromMessage(item);
          if (link) return link;
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
 * ".unavailable-page h1" exist during loading. Race: terminal state OR loading hidden.
 */
export async function waitForRegisterPageReady(page: Page, timeoutMs = 35_000): Promise<void> {
  const createHeading = page.getByRole('heading', { name: 'Create account' });
  const unavailableHeading = page.locator('.unavailable-page h1');
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
  const hasCreate = await createHeading.isVisible().catch(() => false);
  const hasUnavailable = await unavailableHeading.isVisible().catch(() => false);
  if (!hasCreate && !hasUnavailable) {
    await Promise.race([
      createHeading.waitFor({ state: 'visible', timeout: 5_000 }),
      unavailableHeading.waitFor({ state: 'visible', timeout: 5_000 }),
    ]);
  }
}

/**
 * Assert that the currently logged-in user (from page localStorage) has a personal tenant.
 * Fetches /auth/me/ with Bearer token and asserts tenant_id is present (useronboardfix 4.1.1).
 */
export async function assertUserHasPersonalTenant(page: Page): Promise<void> {
  const token = await page.evaluate(() => localStorage.getItem('access_token'));
  if (!token) {
    throw new Error('assertUserHasPersonalTenant: No access_token in localStorage');
  }
  const res = await fetch(`${API_BASE_URL}/auth/me/`, {
    method: 'GET',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
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
  // Registration navigates to /login with state; allow up to 60s for slow API under E2E load
  await page.waitForURL((url) => url.pathname === '/login', { timeout: 60_000 });
  await page.locator('.success-message').waitFor({ state: 'visible', timeout: 15_000 });
  const successText = await page.locator('.success-message').textContent();
  if (!successText?.includes('Account created')) {
    throw new Error('Expected "Account created" success message');
  }
  const user: TestUser = { email, password, name };
  await loginUser(page, user);
  await page.locator('.app-header').waitFor({ state: 'visible', timeout: 10_000 });
  await assertUserHasPersonalTenant(page);
}

/** Run JOURNEY-AUTH-003 success: password reset request + confirm via email (requires MailHog) */
export async function runJOURNEY_AUTH_003_Success(page: Page): Promise<void> {
  let mailhogReachable = false;
  try {
    const probe = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=1`);
    if (probe.ok) mailhogReachable = true;
  } catch {
    // ignore
  }
  if (!mailhogReachable) {
    throw new Error(
      `MailHog not reachable at ${MAILHOG_BASE_URL}. For full E2E: docker compose up -d mailhog, SMTP_HOST=mailhog SMTP_PORT=1025`
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
  const unavailableHeading = page.locator('.unavailable-page h1');
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
  const token = url.searchParams.get('token') ?? '';
  const pathAndSearch = `/password-reset/confirm?token=${encodeURIComponent(token)}`;
  await page.goto(pathAndSearch, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('domcontentloaded');
  const setPwHeading = page.getByRole('heading', { name: /Set a new password/i });
  // Wait for form or error (invalid/expired token); increase timeout for slow MailHog/backend
  const formOrError = await Promise.race([
    setPwHeading.waitFor({ state: 'visible', timeout: 25_000 }).then(() => 'form'),
    page.locator('.error-message, .error-display').filter({ hasText: /invalid|expired/i }).first()
      .waitFor({ state: 'visible', timeout: 25_000 }).then(() => 'error'),
  ]).catch(() => 'timeout' as const);
  if (formOrError === 'error') {
    const errText = await page.locator('.error-message, .error-display').first().textContent().catch(() => '');
    throw new Error(
      `Token invalid or expired. ${errText}. Ensure MailHog is running and email was captured.`
    );
  }
  if (formOrError === 'timeout') {
    throw new Error(
      'Set new password form not visible within 25s. Token may be invalid or page structure changed.'
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
  await page.locator('.app-header').waitFor({ state: 'visible', timeout: 10_000 });
}
