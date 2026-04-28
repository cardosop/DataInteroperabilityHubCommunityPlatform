/// <reference types="vite/client" />

/**
 * Extend Vite env types for known variables.
 * VITE_APP_NAME: Brand name (Phase 28.7 Meshant); default 'Meshant'.
 * VITE_FEATURE_BREADCRUMBS_ENABLED: When false, Breadcrumbs hidden. Default: true.
 * VITE_FEATURE_RESOURCE_PICKERS_ENABLED: When false, pickers render text inputs for manual UUID entry. Default: true.
 */
interface ImportMetaEnv {
  readonly VITE_APP_NAME?: string;
  readonly VITE_FEATURE_BREADCRUMBS_ENABLED?: string;
  readonly VITE_FEATURE_RESOURCE_PICKERS_ENABLED?: string;
  /** When "false", hide advanced sidebar items (Mesh, Virtualization, etc.). Default: true */
  readonly VITE_FEATURE_SIDEBAR_ADVANCED?: string;
  /** When "true", hide non-MVP nav and send capability misses to /coming-soon */
  readonly VITE_MVP_MODE?: string;
  /** Stripe.js publishable key (optional; billing UI) */
  readonly VITE_STRIPE_PUBLISHABLE_KEY?: string;
  /**
   * Phase 226.F2 — when "true" or "1", pre-seed the apiClient's
   * `_cookieAuthMode` flag at construction so the cookie-auth
   * Playwright project can force the cookie path before the first
   * login response arrives. Hint only; the runtime detector still
   * overrides this flag based on what login actually returns.
   */
  readonly VITE_COOKIE_AUTH?: string;
}
