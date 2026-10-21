/**
 * Phase 250.7.A.3 — semantic graceful-degrade banner.
 *
 * Renders inline on the asset detail page when
 * ``asset.semantic_status === "FAIL"`` to surface "active but not
 * yet discoverable" with a retry CTA. The banner is purely
 * presentational; the retry mutation lives at the call site
 * (``AssetDetailPage``) so the banner can be unit-tested without
 * the React Query provider.
 *
 * Returns ``null`` for any non-FAIL state — UNKNOWN (default for
 * pre-250.7.A assets) and PASS render nothing because the asset
 * is in the expected state and a banner would just add noise. WARN
 * is reserved for future granular failures and currently treated
 * the same as PASS (no banner) until the workflow steps that
 * could emit WARN actually exist.
 *
 * **a11y (WCAG 2.1 AA)** — top-level wrapper is
 * ``<section role="alert" aria-live="polite" aria-label>`` so
 * screen readers announce the degradation on first render. The
 * "Retry mapping" button has an accessible name + a click handler
 * the parent supplies — when the parent omits ``onRetry`` (e.g.
 * the retry mutation isn't wired yet), the button is still
 * rendered but disabled with a ``title="Retry not available"``
 * tooltip so the visual state matches the keyboard / SR state.
 */
import type { SemanticStatus } from '../../../shared/types/assets';

export interface SemanticDegradedBannerProps {
  /** The asset's current ``semantic_status``. The banner short-
   *  circuits to ``null`` for any value other than ``"FAIL"``. */
  semanticStatus: SemanticStatus | null | undefined;
  /** Click handler for the "Retry mapping" CTA. When omitted the
   *  button renders disabled (UX clarity — the operator should
   *  see the action exists even if it's not wired yet). */
  onRetry?: () => void;
  /** Set true while the retry mutation is in flight to disable
   *  the button + show the in-flight state. */
  isRetrying?: boolean;
  /** Optional className escape hatch for layout (margin, max-width). */
  className?: string;
}

export function SemanticDegradedBanner({
  semanticStatus,
  onRetry,
  isRetrying,
  className,
}: SemanticDegradedBannerProps) {
  // Banner only fires for FAIL. UNKNOWN (default for pre-250.7.A
  // assets) + PASS + WARN render nothing.
  if (semanticStatus !== 'FAIL') {
    return null;
  }

  const retryDisabled = !onRetry || !!isRetrying;

  return (
    <section
      role="alert"
      aria-live="polite"
      aria-label="Asset is active but not discoverable in semantic search"
      data-testid="semantic-degraded-banner"
      data-semantic-status="FAIL"
      className={[
        'rounded-md border p-4 my-4 text-sm',
        'border-amber-300 bg-amber-50 text-amber-900',
        className ?? '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <header className="flex items-baseline gap-2 mb-2">
        <span aria-hidden="true" className="text-lg leading-none">
          ⚠
        </span>
        <h3 className="font-semibold text-base">
          Active, but not yet discoverable
        </h3>
      </header>
      <p className="mb-3">
        This asset is active but not yet discoverable in semantic
        search. The semantic mapping or search-indexing step
        couldn&apos;t complete during activation. The asset is
        usable (read / download / contract operations work
        normally); it just won&apos;t show up in semantic search
        results until you retry the mapping.
      </p>
      <button
        type="button"
        onClick={onRetry}
        disabled={retryDisabled}
        title={onRetry ? undefined : 'Retry not available'}
        data-testid="semantic-degraded-banner-retry"
        className="rounded border border-amber-700 bg-amber-100 hover:bg-amber-200 disabled:opacity-50 disabled:cursor-not-allowed px-3 py-1 text-sm font-medium"
      >
        {isRetrying ? 'Retrying…' : 'Retry mapping'}
      </button>
    </section>
  );
}
