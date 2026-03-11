/// <reference types="vite/client" />

/**
 * Extend Vite env types for known variables.
 * VITE_APP_NAME: Brand name (Phase 28.7 Meshant); default 'Meshant'.
 * VITE_FEATURE_TOAST_ENABLED: When false, Toast notifications disabled. Default: true.
 * VITE_FEATURE_BREADCRUMBS_ENABLED: When false, Breadcrumbs hidden. Default: true.
 * VITE_FEATURE_RESOURCE_PICKERS_ENABLED: When false, pickers render text inputs for manual UUID entry. Default: true.
 */
interface ImportMetaEnv {
  readonly VITE_APP_NAME?: string;
  readonly VITE_FEATURE_TOAST_ENABLED?: string;
  readonly VITE_FEATURE_BREADCRUMBS_ENABLED?: string;
  readonly VITE_FEATURE_RESOURCE_PICKERS_ENABLED?: string;
}
