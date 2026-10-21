/** Phase 38 — Domain health score thresholds (replaces magic numbers) */
export const DOMAIN_HEALTH_THRESHOLDS = {
  healthy: 80,
  warning: 60,
} as const;

export function healthColor(score?: number): string {
  if (score == null) return 'var(--color-neutral-500, #9E9E9E)';
  if (score >= DOMAIN_HEALTH_THRESHOLDS.healthy) return 'var(--color-success-500, #4CAF50)';
  if (score >= DOMAIN_HEALTH_THRESHOLDS.warning) return 'var(--color-warning-500, #FFC107)';
  return 'var(--color-error-500, #F44336)';
}
