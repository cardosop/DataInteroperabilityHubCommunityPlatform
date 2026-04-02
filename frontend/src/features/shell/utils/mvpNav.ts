/**
 * MVP navigation: hide non-MVP sidebar entries when VITE_MVP_MODE is true.
 * Backend still gates /api/v1/* via MVP_MODE; OpenAPI omits gated paths so
 * capability-based items also disappear after schema load.
 */

const MVP_EXACT_PATHS = new Set([
  '/mesh',
  '/virtualization',
  '/integrations/connections',
  '/communities',
  '/baas',
  '/ml',
  '/transformation',
  '/scheduled-ingestions',
  '/scheduled-exports',
]);

const MVP_PREFIX_PATHS = ['/ai/'];

export function isPathHiddenInMvpMode(path: string, mvpModeEnabled: boolean): boolean {
  if (!mvpModeEnabled) return false;
  if (MVP_EXACT_PATHS.has(path)) return true;
  return MVP_PREFIX_PATHS.some((prefix) => path.startsWith(prefix));
}

export function isMvpModeEnabledFromEnv(): boolean {
  return import.meta.env.VITE_MVP_MODE === 'true';
}
