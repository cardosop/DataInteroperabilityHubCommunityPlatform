/**
 * Feature flags for optional UX components.
 * Configure via VITE_FEATURE_* env vars in .env or Docker build.
 * Default: true (enabled).
 */

/**
 * Parse env string to boolean. Exported for testing.
 * - undefined, '' -> true (default enabled)
 * - 'true', '1' (case-insensitive, trimmed) -> true
 * - 'false', '0', other -> false
 */
export function parseBool(value: string | undefined): boolean {
  if (value === undefined || value === '') return true;
  const v = value.trim().toLowerCase();
  return v === 'true' || v === '1';
}

/** When false, Toast notifications are disabled (no-op). Default: true. */
export const FEATURE_TOAST_ENABLED = parseBool(
  import.meta.env.VITE_FEATURE_TOAST_ENABLED as string | undefined
);

/** When false, Breadcrumbs navigation is hidden. Default: true. */
export const FEATURE_BREADCRUMBS_ENABLED = parseBool(
  import.meta.env.VITE_FEATURE_BREADCRUMBS_ENABLED as string | undefined
);

/** When false, resource pickers (AssetPicker, ContractPicker, etc.) render plain text inputs for manual UUID entry. Default: true. */
export const FEATURE_RESOURCE_PICKERS_ENABLED = parseBool(
  import.meta.env.VITE_FEATURE_RESOURCE_PICKERS_ENABLED as string | undefined
);
