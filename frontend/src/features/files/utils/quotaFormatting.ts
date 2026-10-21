/**
 * Phase 260.4.G — quota formatting + severity helpers.
 *
 * Extracted from ``FileQuotaMeter.tsx`` so the helpers can be
 * unit-tested without instantiating the component AND so the
 * react-refresh rule (only-export-components from a `.tsx` file)
 * doesn't flag them. Pure functions, no side effects.
 */

/** Severity thresholds (per Phase 260.4.G spec). */
export const QUOTA_WARN_THRESHOLD_PERCENT = 80;
export const QUOTA_DANGER_THRESHOLD_PERCENT = 95;
export const QUOTA_UPGRADE_CTA_THRESHOLD_PERCENT = 90;

export type QuotaSeverity = 'normal' | 'warn' | 'danger';

/**
 * Map a percentage to a severity bucket. Strict-greater-than
 * boundaries — exactly 80% / 95% stay in the lower bucket so a
 * tenant landing on the threshold doesn't flip-flop on a re-fetch
 * that returns the same value.
 */
export function severityForQuota(
  percentage: number | null | undefined,
): QuotaSeverity {
  if (percentage == null) return 'normal';
  if (percentage > QUOTA_DANGER_THRESHOLD_PERCENT) return 'danger';
  if (percentage > QUOTA_WARN_THRESHOLD_PERCENT) return 'warn';
  return 'normal';
}

/**
 * Human-readable bytes formatter — picks the largest scale at which
 * the value is < 1024 of the next scale up. Mirrors the existing
 * ``formatBytes`` in FileListPage but adds a TB tier (file storage
 * easily reaches multi-TB on PRO+ plans).
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  if (gb < 1024) return `${gb.toFixed(1)} GB`;
  const tb = gb / 1024;
  return `${tb.toFixed(2)} TB`;
}
