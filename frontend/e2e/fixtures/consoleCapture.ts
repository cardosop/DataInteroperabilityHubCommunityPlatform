/**
 * Phase 276.B.001 — Browser-console capture fixture.
 *
 * Subscribes `page.on('console')` and `page.on('pageerror')` on every
 * Playwright page. Accumulates errors per test and asserts the list is
 * empty in an `afterEach` hook.
 *
 * Configurable allowlist for known noisy third-party scripts, declared
 * explicitly per spec.
 */
import { test as base } from '@playwright/test';

type ConsoleEntry = { type: string; text: string; location: string };

// Allowlist: messages from these sources are NOT treated as test failures.
const ALLOWLIST_PATTERNS: RegExp[] = [
  /Failed to load resource: the server responded with a status of 401/,
  /Download the React DevTools/,
];

export const test = base.extend<{ consoleErrors: ConsoleEntry[] }>({
  consoleErrors: [
    async ({ page }, use) => {
      const errors: ConsoleEntry[] = [];

      page.on('console', (msg) => {
        if (msg.type() === 'error') {
          const entry: ConsoleEntry = {
            type: msg.type(),
            text: msg.text(),
            location: msg.location().url || '',
          };

          const isAllowed = ALLOWLIST_PATTERNS.some((p) => p.test(entry.text));
          if (!isAllowed) {
            errors.push(entry);
          }
        }
      });

      page.on('pageerror', (err) => {
        errors.push({ type: 'pageerror', text: err.message, location: '' });
      });

      await use(errors);

      if (errors.length > 0) {
        const details = errors
          .map((e) => `  [${e.type}] ${e.text}`)
          .join('\n');
        throw new Error(
          `Browser console errors detected (${errors.length}):\n${details}`,
        );
      }
    },
    { auto: true },
  ],
});
