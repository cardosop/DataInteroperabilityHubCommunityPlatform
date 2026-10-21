/**
 * Phase 231.3 helpers used by ComplianceBadge — kept in their own
 * module so ``react-refresh/only-export-components`` keeps the
 * ``ComplianceBadge`` file component-only and Fast Refresh boundaries
 * stay clean.
 */
import styles from './ComplianceBadge.module.css';

export const RISK_PILL_CLASS: Record<string, string> = {
  NONE: styles.pillNone,
  LOW: styles.pillLow,
  MEDIUM: styles.pillMedium,
  HIGH: styles.pillHigh,
  CRITICAL: styles.pillCritical,
  UNKNOWN: styles.pillUnknown,
};

/** Exported for tests and non-secure contexts (execCommand fallback). */
export async function copyTextToClipboard(text: string): Promise<boolean> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* fall through to execCommand */
  }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function riskDisplayLabel(level: string | null | undefined): string {
  const u = (level ?? 'UNKNOWN').toString().trim().toUpperCase();
  const map: Record<string, string> = {
    NONE: 'None',
    LOW: 'Low',
    MEDIUM: 'Medium',
    HIGH: 'High',
    CRITICAL: 'Critical',
    UNKNOWN: 'Unknown',
  };
  return map[u] ?? 'Unknown';
}
