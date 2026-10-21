/**
 * Stripe test-mode publishable key for local E2E runs.
 *
 * Mirrors the `STRIPE_PUBLISHABLE_KEY` default in docker-compose.test.yml
 * (single source of truth: the test stack). A publishable key is safe to
 * embed in a frontend bundle by design — it can only tokenize cards.
 *
 * Consumers:
 *  - vite.config.ts: defaults `VITE_STRIPE_PUBLISHABLE_KEY` when
 *    `VITE_E2E_TEST=true` so ANY E2E dev server (Playwright-managed OR the
 *    supervised 5184 server started by scripts/e2e-detect-api.sh) embeds
 *    the key. Before this default existed, only the Playwright webServer
 *    injected the key — batch runs that reused the supervised server
 *    rendered "Stripe is not configured" and the Stripe checkout E2E
 *    runtime-skipped (batch 2, 2026-10-02).
 *  - playwright.config.ts: webServer env fallback (kept so an explicitly
 *    exported key still wins in both start paths).
 */
export const E2E_STRIPE_PUBLISHABLE_KEY =
  'pk_test_51T412N79Dw5TG33rxbm9F3zSZ1rPxI5En7Tb2n8OL65Cd9wwCdpuiPsIcmi5qQATGzx7pMrGNKKj1pQiwB7w45Hw004ICHrRJe';
