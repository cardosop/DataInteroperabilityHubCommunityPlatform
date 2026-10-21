/**
 * Phase 250.6.B (closes Gap 12) — Asset type-picker step.
 *
 * Rendered as an in-page step BEFORE the existing AssetCreatePage
 * form. Lets the user pre-configure form-field visibility by
 * picking one of FOUR asset shapes:
 *
 *   * ``data``      — A data file (CSV / JSON / Parquet).
 *   * ``contract``  — A contract document (ODCS / DataContract.com).
 *   * ``both``      — File + contract.
 *   * ``metadata``  — Metadata only (no upload, no contract).
 *
 * The picker holds NO URL state (250.6.B.3 — "in-page state, no
 * URL change"). Selection is published via the ``onSelect``
 * callback so the parent (``AssetCreatePage``) can pre-set its
 * ``showDataFile`` / ``showContract`` toggles.
 *
 * The ``shouldSkipTypePicker(search)`` helper lives in
 * ``AssetTypePickerStep.utils.ts`` so the parent can check the URL query string
 * (``?skip=picker``) to decide whether to render the picker at
 * all. Keeping the helper a pure function — free of React /
 * router imports — means it's trivially unit-testable AND can
 * be reused outside React (e.g. SSR pre-render).
 *
 * Accessibility (Phase 250.6.B.4 — WCAG 2.1 AA target)
 * --------------------------------------------------
 * * The four options form a single ``role="radiogroup"`` with
 *   the step's heading bound via ``aria-labelledby``.
 * * Each option is a real ``<button role="radio">`` so it
 *   participates in the document tab order AND
 *   Enter/Space activation works without custom keyboard
 *   handlers.
 * * The currently-selected option carries
 *   ``aria-checked="true"``; others are ``aria-checked="false"``.
 *   The same state is reflected in ``data-selected`` for E2E
 *   selectors and in CSS via the same attribute.
 * * Each option has a verbose ``aria-label`` (separate i18n key)
 *   so a screen reader announces the full intent rather than
 *   just the title.
 */
import type { KeyboardEvent } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import './AssetTypePickerStep.css';

export type AssetTypeKind = 'data' | 'contract' | 'both' | 'metadata';

export interface AssetTypePickerStepProps {
  /** Fires with the selected kind on every option click. The
   *  parent decides whether the click is "advance to next step"
   *  or "preview-on-hover" — the picker itself doesn't navigate. */
  onSelect: (kind: AssetTypeKind) => void;
  /** Optional skip handler. When provided, the picker renders a
   *  Skip CTA so users who landed here without ``?skip=picker``
   *  can still bypass without re-typing the URL. When omitted,
   *  the Skip button is NOT rendered (250.6.B.3 contract). */
  onSkip?: () => void;
  /** The currently-selected kind. Drives ``aria-checked`` /
   *  ``data-selected`` for the matching option. */
  selected?: AssetTypeKind | null;
  /** Phase 250.6.D.3 — when True, the picker renders an
   *  onboarding-incomplete CTA INSTEAD of the four kind cards.
   *  The CTA points at the onboarding flow via ``onCompleteOnboarding``
   *  (a click handler the parent provides — typically a
   *  ``navigate('/onboarding')`` call). The four cards + skip
   *  button are NOT rendered when this flag is set; the role tree
   *  collapses to the heading + body + CTA. */
  onboardingIncomplete?: boolean;
  /** Phase 250.6.D.3 — click handler for the "Complete onboarding"
   *  CTA. Required when ``onboardingIncomplete=true``; ignored
   *  otherwise. Keeping this a parent-provided callback (vs.
   *  hardcoding navigation) preserves the picker's "no business
   *  logic" contract from 250.6.B.1. */
  onCompleteOnboarding?: () => void;
}

interface _OptionDef {
  kind: AssetTypeKind;
  titleKey: string;
  bodyKey: string;
  ariaKey: string;
}

// Pinned in this exact order so the data-kind regression test
// (in the test file) catches a future re-order.
const _OPTIONS: ReadonlyArray<_OptionDef> = [
  {
    kind: 'data',
    titleKey: 'assets.type_picker.option.data.title',
    bodyKey: 'assets.type_picker.option.data.body',
    ariaKey: 'assets.type_picker.option.data.aria_label',
  },
  {
    kind: 'contract',
    titleKey: 'assets.type_picker.option.contract.title',
    bodyKey: 'assets.type_picker.option.contract.body',
    ariaKey: 'assets.type_picker.option.contract.aria_label',
  },
  {
    kind: 'both',
    titleKey: 'assets.type_picker.option.both.title',
    bodyKey: 'assets.type_picker.option.both.body',
    ariaKey: 'assets.type_picker.option.both.aria_label',
  },
  {
    kind: 'metadata',
    titleKey: 'assets.type_picker.option.metadata.title',
    bodyKey: 'assets.type_picker.option.metadata.body',
    ariaKey: 'assets.type_picker.option.metadata.aria_label',
  },
];

export function AssetTypePickerStep({
  onSelect,
  onSkip,
  selected = null,
  onboardingIncomplete = false,
  onCompleteOnboarding,
}: AssetTypePickerStepProps) {
  const { t } = useTranslation();

  const handleKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    kind: AssetTypeKind,
  ) => {
    // Native ``<button>`` already triggers click on Enter+Space,
    // so this handler is a defence-in-depth pin for the keyboard
    // contract — useful if someone later switches to a
    // ``<div role="radio">`` shape.
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      onSelect(kind);
    }
  };

  // Phase 250.6.D.3 — onboarding-incomplete variant. When the parent
  // signals the tenant hasn't finished onboarding, render an
  // alternative first-step UI: heading + a CTA that points at the
  // onboarding flow. The four kind cards + skip CTA are NOT
  // rendered in this branch — letting the user pick a kind would
  // produce a form whose POST will 403 at the kill-switch gate.
  if (onboardingIncomplete) {
    return (
      <div
        data-testid="asset-type-picker-step"
        data-variant="onboarding-incomplete"
        className="asset-type-picker-step asset-type-picker-step--blocked"
      >
        <h2 id="asset-type-picker-heading">
          {t('assets.type_picker.onboarding_incomplete.heading')}
        </h2>
        <p>{t('assets.type_picker.onboarding_incomplete.body')}</p>
        {onCompleteOnboarding && (
          <button
            type="button"
            data-testid="asset-type-picker-complete-onboarding"
            className="asset-type-picker-complete-onboarding"
            onClick={onCompleteOnboarding}
          >
            {t('assets.type_picker.onboarding_incomplete.cta')}
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      data-testid="asset-type-picker-step"
      className="asset-type-picker-step"
    >
      <h2 id="asset-type-picker-heading">
        {t('assets.type_picker.heading')}
      </h2>
      <p>{t('assets.type_picker.body')}</p>

      <div
        role="radiogroup"
        aria-labelledby="asset-type-picker-heading"
        aria-label={t('assets.type_picker.aria_label')}
        className="asset-type-picker-options"
      >
        {_OPTIONS.map((option) => {
          const isSelected = selected === option.kind;
          return (
            <button
              key={option.kind}
              type="button"
              role="radio"
              aria-checked={isSelected ? 'true' : 'false'}
              aria-label={t(option.ariaKey)}
              data-kind={option.kind}
              data-selected={isSelected ? 'true' : 'false'}
              data-testid={`asset-type-picker-option-${option.kind}`}
              className="asset-type-picker-option"
              onClick={() => onSelect(option.kind)}
              onKeyDown={(e) => handleKeyDown(e, option.kind)}
            >
              <span className="asset-type-picker-option-title">
                {t(option.titleKey)}
              </span>
              <span className="asset-type-picker-option-body">
                {t(option.bodyKey)}
              </span>
            </button>
          );
        })}
      </div>

      {onSkip && (
        <button
          type="button"
          data-testid="asset-type-picker-skip"
          className="asset-type-picker-skip"
          onClick={onSkip}
        >
          {t('assets.type_picker.skip_label')}
        </button>
      )}
    </div>
  );
}
