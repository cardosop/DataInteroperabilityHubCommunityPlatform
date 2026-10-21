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

/** When false, Breadcrumbs navigation is hidden. Default: true. */
export const FEATURE_BREADCRUMBS_ENABLED = parseBool(
  import.meta.env.VITE_FEATURE_BREADCRUMBS_ENABLED as string | undefined
);

/** When false, resource pickers (AssetPicker, ContractPicker, etc.) render plain text inputs for manual UUID entry. Default: true. */
export const FEATURE_RESOURCE_PICKERS_ENABLED = parseBool(
  import.meta.env.VITE_FEATURE_RESOURCE_PICKERS_ENABLED as string | undefined
);

/** When false, advanced/non-core sidebar items (Mesh, Virtualization, Semantic,
 *  AI, Communities, Developer, BaaS, ML, Observability, Transformation) are
 *  hidden from the sidebar navigation. Default: true (all visible). */
export const FEATURE_SIDEBAR_ADVANCED = parseBool(
  import.meta.env.VITE_FEATURE_SIDEBAR_ADVANCED as string | undefined
);
