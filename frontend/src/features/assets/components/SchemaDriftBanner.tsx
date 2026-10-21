/**
 * Phase 250.2.B.5 — inline schema-drift banner shown on the
 * asset-creation success summary.
 *
 * The component is **purely presentational** — no fetching, no
 * network side-effects. It renders the ``SchemaDriftResult``
 * payload returned by the workflow's
 * ``compare_schema_against_contract`` step (passed in via the
 * `drift` prop) and surfaces:
 *
 * 1. A coloured severity heading (yellow for WARN, red for FAIL).
 * 2. UX-writer copy explaining what the user should do next.
 * 3. Three collapsible sections — `missing_fields`, `extra_fields`,
 *    and `type_mismatches` — each only rendered if non-empty.
 *
 * Accessibility (WCAG 2.1 AA):
 *
 * - Top-level wrapper is `<section role="alert" aria-live="polite">`
 *   so screen readers announce drift on first render.
 * - Severity is conveyed via colour AND text + icon — not colour
 *   alone (per 1.4.1 Use of Color).
 * - Collapsible sections use native `<details>` / `<summary>` so
 *   keyboard navigation, focus management, and screen-reader
 *   announcements are inherited from the browser (no custom JS
 *   accordion to test).
 * - The type-mismatch table has `<th scope="col">` + a `<caption>`
 *   per 1.3.1 Info and Relationships.
 * - Colour contrast for the severity badges meets 4.5:1 against
 *   the banner background (verified in Storybook chromatic).
 *
 * Localisation: every string is keyed via `useTranslation()` —
 * keys are namespaced under `assets.schema_drift.*` so a per-
 * feature locale split doesn't collide with other surfaces.
 */
import type { JSX } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';

export interface TypeMismatch {
  field: string;
  contract_type: string;
  dataset_type: string;
  compatible: boolean;
}

export interface SchemaDriftPayload {
  detected: boolean;
  severity: 'NONE' | 'WARN' | 'FAIL';
  missing_fields: string[];
  extra_fields: string[];
  type_mismatches: TypeMismatch[];
  structural_incompatibility: boolean;
}

export interface SchemaDriftBannerProps {
  /** Server-emitted drift payload (`result_summary.schema_drift`). */
  drift: SchemaDriftPayload | null | undefined;
  /** Optional className escape hatch for layout (margin, max-width). */
  className?: string;
}

/**
 * Renders nothing when there's no drift to report. Specifically:
 * - drift is null/undefined (workflow didn't run the step)
 * - drift.detected === false (clean diff)
 * - drift.severity === 'NONE' (defence in depth)
 *
 * Returning null in the no-drift case keeps the AssetCreatePage
 * summary tidy when the contract and dataset are aligned.
 */
export function SchemaDriftBanner({
  drift,
  className,
}: SchemaDriftBannerProps): JSX.Element | null {
  const { t } = useTranslation();

  if (!drift || !drift.detected || drift.severity === 'NONE') {
    return null;
  }

  const severity = drift.severity;
  const isFail = severity === 'FAIL';

  const headingKey = isFail
    ? 'assets.schema_drift.heading.fail'
    : 'assets.schema_drift.heading.warn';
  const bodyKey = isFail
    ? 'assets.schema_drift.body.fail'
    : 'assets.schema_drift.body.warn';

  // Colour contrast: backgrounds chosen to give ≥4.5:1 against the
  // text colour. WARN uses amber-50 / amber-900; FAIL uses red-50 /
  // red-900. Both scales hit 7.x:1 in Tailwind defaults.
  const severityClass = isFail
    ? 'border-red-300 bg-red-50 text-red-900'
    : 'border-amber-300 bg-amber-50 text-amber-900';

  const iconLabel = isFail ? '⚠' : 'ⓘ';

  return (
    <section
      role="alert"
      aria-live="polite"
      aria-label={t('assets.schema_drift.banner_aria_label')}
      data-testid="schema-drift-banner"
      data-severity={severity}
      className={[
        'rounded-md border p-4 my-4 text-sm',
        severityClass,
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <header className="flex items-baseline gap-2 mb-2">
        <span aria-hidden="true" className="text-lg leading-none">
          {iconLabel}
        </span>
        <h3 className="font-semibold text-base">
          {t(headingKey)}
        </h3>
      </header>

      <p className="mb-3">{t(bodyKey)}</p>

      {drift.missing_fields.length > 0 && (
        <DriftSection
          headingKey="assets.schema_drift.section.missing"
          helpKey="assets.schema_drift.section.missing_help"
          items={drift.missing_fields}
        />
      )}

      {drift.extra_fields.length > 0 && (
        <DriftSection
          headingKey="assets.schema_drift.section.extra"
          helpKey="assets.schema_drift.section.extra_help"
          items={drift.extra_fields}
        />
      )}

      {drift.type_mismatches.length > 0 && (
        <TypeMismatchSection mismatches={drift.type_mismatches} />
      )}
    </section>
  );
}

/**
 * Field-name list section (used for `missing_fields` and
 * `extra_fields`). Wrapped in a native `<details>` so it's
 * collapsible without custom JS.
 */
function DriftSection({
  headingKey,
  helpKey,
  items,
}: {
  headingKey: string;
  helpKey: string;
  items: string[];
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <details className="mb-2" open={items.length <= 5}>
      <summary className="cursor-pointer font-medium">
        {t(headingKey)} ({items.length})
      </summary>
      <p className="mt-1 mb-2 text-xs opacity-90">{t(helpKey)}</p>
      <ul className="list-disc list-inside font-mono text-xs">
        {items.map((field) => (
          <li key={field}>{field}</li>
        ))}
      </ul>
    </details>
  );
}

/**
 * Type-mismatch table — fixed columns, screen-reader-friendly markup
 * with `<th scope="col">` and a hidden `<caption>` so assistive
 * technology can announce table purpose without visual clutter.
 */
function TypeMismatchSection({
  mismatches,
}: {
  mismatches: TypeMismatch[];
}): JSX.Element {
  const { t } = useTranslation();
  return (
    <details className="mb-2" open={mismatches.length <= 5}>
      <summary className="cursor-pointer font-medium">
        {t('assets.schema_drift.section.mismatches')} ({mismatches.length})
      </summary>
      <p className="mt-1 mb-2 text-xs opacity-90">
        {t('assets.schema_drift.section.mismatches_help')}
      </p>
      <table className="min-w-full text-xs">
        <caption className="sr-only">
          {t('assets.schema_drift.section.mismatches')}
        </caption>
        <thead>
          <tr>
            <th scope="col" className="text-left font-semibold pr-4">
              {t('assets.schema_drift.mismatch_col.field')}
            </th>
            <th scope="col" className="text-left font-semibold pr-4">
              {t('assets.schema_drift.mismatch_col.contract_type')}
            </th>
            <th scope="col" className="text-left font-semibold pr-4">
              {t('assets.schema_drift.mismatch_col.dataset_type')}
            </th>
            <th scope="col" className="text-left font-semibold">
              {t('assets.schema_drift.mismatch_col.compatible')}
            </th>
          </tr>
        </thead>
        <tbody>
          {mismatches.map((m) => (
            <tr key={m.field}>
              <td className="font-mono pr-4">{m.field}</td>
              <td className="font-mono pr-4">{m.contract_type}</td>
              <td className="font-mono pr-4">{m.dataset_type}</td>
              <td>
                {m.compatible
                  ? t('assets.schema_drift.mismatch.compatible_yes')
                  : t('assets.schema_drift.mismatch.compatible_no')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
