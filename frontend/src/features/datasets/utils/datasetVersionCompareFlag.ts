/**
 * Phase 260.3.A — dataset version compare UI is opt-in via Vite env so soak/staging
 * can ship with the button hidden (`VITE_DATASET_VERSION_COMPARE_ENABLED` unset).
 *
 * Docker/backend `DATASET_VERSION_COMPARE_ENABLED` does not reach the browser;
 * use `VITE_DATASET_VERSION_COMPARE_ENABLED=true` in the frontend image / compose.
 */
export function isDatasetVersionCompareEnabled(): boolean {
  return import.meta.env.VITE_DATASET_VERSION_COMPARE_ENABLED === 'true';
}
