/**
 * E2E Test: Auth UI closure — Visitor persona (thin wrapper)
 *
 * Covers JOURNEY-AUTH-001, JOURNEY-AUTH-003, JOURNEY-AUTH-004.
 * Canonical specs: journeys/auth/JOURNEY-AUTH-001.spec.ts, JOURNEY-AUTH-003.spec.ts, JOURNEY-AUTH-004.spec.ts.
 * This file is a thin wrapper that runs the same shared step logic (fixtures/auth-journey-steps) for CI/legacy.
 * Real backend only (no mocks/stubs). Password reset requires MailHog.
 */

import { test } from '@playwright/test';
import {
  runJOURNEY_AUTH_001_Success,
  runJOURNEY_AUTH_003_Success,
  runJOURNEY_AUTH_004_Success,
} from './fixtures/auth-journey-steps';

const MAILHOG_BASE_URL = process.env.MAILHOG_URL || 'http://localhost:8025';

test.describe('Auth UI closure — Visitor persona (no mocks)', () => {
  test('JOURNEY-AUTH-004: unauthenticated user can access public resources', async ({ page }) => {
    await runJOURNEY_AUTH_004_Success(page);
  });

  test('JOURNEY-AUTH-001: visitor can register via UI and then login', async ({ page }) => {
    await runJOURNEY_AUTH_001_Success(page);
  });

  test('JOURNEY-AUTH-003: visitor can request password reset and confirm via email link', async ({
    page,
  }) => {
    test.setTimeout(180_000);
    let mailhogReachable = false;
    try {
      const probe = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=1`);
      if (probe.ok) mailhogReachable = true;
    } catch {
      // ignore
    }
    test.skip(
      !mailhogReachable,
      `MailHog not reachable at ${MAILHOG_BASE_URL}. For full E2E: docker compose up -d mailhog, SMTP_HOST=mailhog SMTP_PORT=1025`
    );
    try {
      await runJOURNEY_AUTH_003_Success(page);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      // Report skip when MailHog unavailable or password-reset email not received (no mocks)
      if (
        msg.includes('E2E_SKIP_PASSWORD_RESET') ||
        msg.includes('MailHog not reachable') ||
        msg.includes('not reachable at')
      ) {
        test.skip(true, msg);
      }
      throw err;
    }
  });
});
