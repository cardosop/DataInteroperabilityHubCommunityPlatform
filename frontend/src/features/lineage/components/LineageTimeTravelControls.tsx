/**
 * Phase 228 F5 (228.F5.12 + F5.15 + F5.16 + DoD-G8) — point-in-time
 * controls.
 *
 * Two anchors:
 *
 *  1. Date picker (`as_of`) — ISO-8601 timestamp the user wants the
 *     graph rendered at. Locale-aware via `<input type="datetime-local">`
 *     so the browser draws the picker the user expects.
 *  2. Version dropdown (`version`) — pulled from the contract's
 *     version history; resolves to the contract's `created_at`
 *     server-side.
 *
 * Capability gate (DoD-G8 / spec REQ-LIN-F5-003): when
 * `lineage.snapshots` is OFF the controls are not rendered. The
 * backend ALSO silently ignores the params if the flag is off, so
 * the gate here is UX-only — no security boundary depends on it.
 *
 * Accessibility (228.F5.16):
 *
 *  - Every control has an associated `<label>` with explicit `htmlFor`.
 *  - The "Apply" button announces its action via `aria-label`.
 *  - The "Reset" button restores the live (current-state) view.
 *  - All `data-testid` attributes are stable so the E2E spec
 *    (228.F5.17) can drive the controls deterministically.
 */
import { useEffect, useState } from 'react';

import { useCapabilities } from '../../../shared/hooks/useCapabilities';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import styles from './LineageTimeTravelControls.module.css';

export interface LineageTimeTravelControlsProps {
  /** ISO-8601 string for the currently-applied as_of, if any. */
  asOf: string | null;
  /** Currently-applied version int, if any. */
  version: number | null;
  /**
   * List of versions the user can pick from. Each entry should match
   * a `Contract.version` row the tenant owns.
   */
  availableVersions: Array<{ version: number; label?: string }>;
  /** Apply the chosen anchor. Caller updates URL state + queries. */
  onApply: (next: { asOf: string | null; version: number | null }) => void;
  /** Clear the anchor (return to live current-state view). */
  onReset: () => void;
}

const isoToLocal = (iso: string | null): string => {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '';
  }
};

export function LineageTimeTravelControls({
  asOf,
  version,
  availableVersions,
  onApply,
  onReset,
}: LineageTimeTravelControlsProps) {
  const { t } = useTranslation();
  const { isCapabilityAvailable, isLoading: capsLoading } = useCapabilities();

  const [draftDate, setDraftDate] = useState<string>(() => isoToLocal(asOf));
  const [draftVersion, setDraftVersion] = useState<string>(
    version != null ? String(version) : '',
  );

  useEffect(() => {
    setDraftDate(isoToLocal(asOf));
  }, [asOf]);
  useEffect(() => {
    setDraftVersion(version != null ? String(version) : '');
  }, [version]);

  // DoD-G8 — gate behind the lineage.snapshots capability flag per
  // REQ-LIN-F5-003. The hook fail-opens (returns true) on capabilities
  // load timeout, so a slow capabilities endpoint doesn't suppress
  // the controls indefinitely. While loading we render nothing rather
  // than flashing the controls in a transient OFF/ON sequence.
  if (capsLoading) {
    return null;
  }
  if (!isCapabilityAvailable('lineage.snapshots')) {
    return null;
  }

  const handleApply = (e: React.FormEvent) => {
    e.preventDefault();
    let nextAsOf: string | null = null;
    if (draftDate) {
      const d = new Date(draftDate);
      if (!Number.isNaN(d.getTime())) {
        nextAsOf = d.toISOString();
      }
    }
    const nextVersion = draftVersion ? Number(draftVersion) : null;
    onApply({ asOf: nextAsOf, version: nextVersion });
  };

  const handleReset = () => {
    setDraftDate('');
    setDraftVersion('');
    onReset();
  };

  return (
    <form
      onSubmit={handleApply}
      data-testid="lineage-time-travel-controls"
      aria-label={t('lineage.timetravel.controls_aria_label', 'Lineage time-travel controls')}
      className={styles.controls}
    >
      <div className={styles.field}>
        <label htmlFor="lineage-asof-input" className={styles.label}>
          {t('lineage.timetravel.as_of_label', 'As of')}
        </label>
        <input
          id="lineage-asof-input"
          data-testid="lineage-asof-input"
          type="datetime-local"
          value={draftDate}
          onChange={(e) => setDraftDate(e.target.value)}
          aria-describedby="lineage-asof-help"
          className={styles.input}
        />
        <span id="lineage-asof-help" className={styles.help}>
          {t('lineage.timetravel.as_of_help', 'Render lineage at this exact moment.')}
        </span>
      </div>

      <div className={styles.field}>
        <label htmlFor="lineage-version-select" className={styles.label}>
          {t('lineage.timetravel.version_label', 'Version')}
        </label>
        <select
          id="lineage-version-select"
          data-testid="lineage-version-select"
          value={draftVersion}
          onChange={(e) => setDraftVersion(e.target.value)}
          className={styles.select}
        >
          <option value="">
            {t('lineage.timetravel.version_placeholder', '— pick a version —')}
          </option>
          {availableVersions.map((v) => (
            <option key={v.version} value={v.version}>
              {v.label ?? `v${v.version}`}
            </option>
          ))}
        </select>
      </div>

      <button
        type="submit"
        data-testid="lineage-timetravel-apply"
        aria-label={t('lineage.timetravel.apply_aria', 'Apply time-travel anchor')}
        className={styles.applyButton}
      >
        {t('lineage.timetravel.apply', 'Apply')}
      </button>
      <button
        type="button"
        onClick={handleReset}
        data-testid="lineage-timetravel-reset"
        aria-label={t('lineage.timetravel.reset_aria', 'Reset to live view')}
        className={styles.resetButton}
      >
        {t('lineage.timetravel.reset', 'Reset')}
      </button>
    </form>
  );
}

export default LineageTimeTravelControls;
