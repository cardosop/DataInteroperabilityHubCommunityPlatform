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

test.describe('Auth UI closure — Visitor persona (no mocks) @critical', () => {
  // AUTH-001: clearAuth → register (45s API) → login (60s) → verify shell (45s)
  // AUTH-003: register → password-reset → MailHog poll (120s) → confirm → login
  test.setTimeout(240_000);

  test('JOURNEY-AUTH-004: unauthenticated user can access public resources', async ({ page }) => {
    await runJOURNEY_AUTH_004_Success(page);
  });

  test('JOURNEY-AUTH-001: visitor can register via UI and then login', async ({ page }) => {
    await runJOURNEY_AUTH_001_Success(page);
  });

  test('JOURNEY-AUTH-003: visitor can request password reset and confirm via email link', async ({
    page,
  }) => {
    let mailhogReachable = false;
    // Retry the MailHog probe once — under parallel E2E load the first attempt can fail
    // with a transient connection error even though the service is healthy.
    for (let attempt = 0; attempt < 2 && !mailhogReachable; attempt++) {
      try {
        const probe = await fetch(`${MAILHOG_BASE_URL}/api/v2/messages?limit=1`, {
          signal: AbortSignal.timeout(5000),
        });
        if (probe.ok) mailhogReachable = true;
      } catch {
        if (attempt === 0) await new Promise((r) => setTimeout(r, 2000));
      }
    }
    // Skip at test level when MailHog unavailable (optional service for password reset flow).
    // See E2E_ENVIRONMENT_REQUIREMENTS.md and E2E_TEST_SEMANTICS.md.
    test.skip(
      !mailhogReachable,
      `MailHog not reachable at ${MAILHOG_BASE_URL}. Password reset requires MailHog for email delivery. ` +
        `Start: docker compose up -d mailhog, SMTP_HOST=mailhog SMTP_PORT=1025`
    );
    await runJOURNEY_AUTH_003_Success(page);
  });
});
