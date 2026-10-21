/**
 * Phase 228.F1.10 (REQ-LIN-F1-004) — Cross-tenant marketplace
 * lineage panel.
 *
 * Renders the lineage graph for a listing's backing asset, with
 * automatic detail-tier resolution:
 *
 * - **Pre-purchase** (no ACTIVE entitlement for the asset):
 *   - Requests `?detail=summary`
 *   - Displays a "Buy listing to see full lineage" CTA below the graph
 *
 * - **Post-purchase** (ACTIVE entitlement present):
 *   - Requests `?detail=full`
 *   - Hides the CTA
 *
 * The detail-tier resolution happens on the FRONTEND so the buyer
 * doesn't see a 403-then-200 flicker after purchase.  The backend
 * still enforces the boundary — a buyer who tampers with the
 * request to ask for `full` without the entitlement gets a 403
 * (REQ-LIN-F1-001 scenario "pre-purchase full view forbidden").
 */
import { useEffect, useMemo, useRef } from 'react';

import { useEntitlements } from '../hooks/useEntitlements';
import { useListingLineage } from '../hooks/useListings';
import { LineageGraph } from '../../lineage/components/LineageGraph';
import {
  emitLineageListingEvent,
} from '../lib/listingLineageTelemetry';
import { t } from './listingLineageStrings';
import type { LineageDetailLevel } from '../../../shared/types/lineage';

export interface ListingLineagePanelProps {
  listingId: string;
  /** Asset uuid backing the listing — used to look up entitlement state. */
  assetId: string;
  /**
   * Optional handler for the "Buy listing" CTA.  When omitted the CTA
   * scrolls to the listing's purchase section by anchor.
   */
  onPurchaseClick?: () => void;
}

export function ListingLineagePanel({
  listingId,
  assetId,
  onPurchaseClick,
}: ListingLineagePanelProps) {
  // Resolve entitlement state for the backing asset.  An ACTIVE row
  // for the (consumer_tenant, asset) pair → caller can request `full`.
  const {
    data: entitlements,
    isLoading: isEntitlementLoading,
  } = useEntitlements({ asset_id: assetId, status: 'ACTIVE' });

  const hasActiveEntitlement = useMemo(
    () => (entitlements?.results?.length ?? 0) > 0,
    [entitlements],
  );

  // Detail tier — resolved client-side so the request matches what
  // the user is entitled to see, avoiding a useless 403 round-trip.
  const detail: LineageDetailLevel = hasActiveEntitlement ? 'full' : 'summary';

  // Defer the lineage fetch until the entitlement check resolves so
  // we don't race-condition between summary→full when the consumer
  // just purchased.
  const lineageQuery = useListingLineage(
    isEntitlementLoading ? null : listingId,
    detail,
  );
  const { data: graph, isLoading, error, refetch } = lineageQuery;

  // ----- Telemetry (F1.29) -----
  const mountedAtRef = useRef<number | null>(null);
  const fullLoadedFiredRef = useRef(false);
  const errorFiredRef = useRef(false);

  useEffect(() => {
    mountedAtRef.current = Date.now();
    emitLineageListingEvent('lineage.listing.opened', {
      listing_id: listingId,
      detail,
    });
  }, [listingId, detail]);

  useEffect(() => {
    if (graph && detail === 'full' && !fullLoadedFiredRef.current) {
      fullLoadedFiredRef.current = true;
      emitLineageListingEvent('lineage.listing.full_loaded', {
        listing_id: listingId,
        detail: 'full',
        elapsed_ms: mountedAtRef.current
          ? Date.now() - mountedAtRef.current
          : undefined,
      });
    }
  }, [graph, detail, listingId]);

  useEffect(() => {
    if (error && !errorFiredRef.current) {
      errorFiredRef.current = true;
      emitLineageListingEvent('lineage.listing.error', {
        listing_id: listingId,
        detail,
        error_code: getErrorCode(error),
      });
      if (getErrorCode(error) === 'ENTITLEMENT_REQUIRED') {
        emitLineageListingEvent('lineage.listing.forbidden', {
          listing_id: listingId,
          detail,
        });
      }
    }
  }, [error, listingId, detail]);

  const handleCtaClick = () => {
    emitLineageListingEvent('lineage.listing.cta_clicked', {
      listing_id: listingId,
      detail: 'summary',
    });
    onPurchaseClick?.();
  };

  // ----- Render states -----

  // Loading — including the entitlement check (avoids the
  // summary→full flicker after a purchase completes).
  if (isLoading || isEntitlementLoading) {
    return (
      <section
        aria-label={t('lineage.listing.heading')}
        aria-busy="true"
        data-testid="listing-lineage-panel-loading"
      >
        <h2>{t('lineage.listing.heading')}</h2>
        <SkeletonGraph />
      </section>
    );
  }

  // Error
  if (error) {
    const code = getErrorCode(error);
    const isForbidden = code === 'ENTITLEMENT_REQUIRED';
    return (
      <section
        aria-label={t('lineage.listing.heading')}
        role="alert"
        data-testid="listing-lineage-panel-error"
      >
        <h2>{t('lineage.listing.heading')}</h2>
        {isForbidden ? (
          <ContentRichForbidden />
        ) : (
          <ContentRichError onRetry={() => refetch()} />
        )}
      </section>
    );
  }

  // Empty
  if (!graph || (graph.nodes.length <= 1 && graph.links.length === 0)) {
    return (
      <section
        aria-label={t('lineage.listing.heading')}
        data-testid="listing-lineage-panel-empty"
      >
        <h2>{t('lineage.listing.heading')}</h2>
        <ContentRichEmpty />
      </section>
    );
  }

  // Successful render
  return (
    <section
      aria-label={t('lineage.listing.heading')}
      data-testid="listing-lineage-panel"
      data-detail={detail}
    >
      <h2>{t('lineage.listing.heading')}</h2>
      <p>
        {detail === 'full'
          ? t('lineage.listing.full.description')
          : t('lineage.listing.summary.description')}
      </p>
      {graph.truncated && (
        <div role="status" data-testid="listing-lineage-truncated">
          {t('lineage.listing.truncated.banner')}
        </div>
      )}
      <div style={{ height: 480 }}>
        <LineageGraph
          nodes={graph.nodes}
          links={graph.links}
          loading={false}
          error={null}
          onRetry={() => refetch()}
        />
      </div>
      {detail === 'summary' && (
        <PurchaseCTA onClick={handleCtaClick} />
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SkeletonGraph() {
  // Minimal CSS-grid skeleton — three placeholder boxes that suggest
  // the graph shape without depending on a third-party skeleton lib.
  return (
    <div
      role="status"
      aria-label={t('lineage.listing.loading')}
      data-testid="listing-lineage-skeleton"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: '1rem',
        padding: '1rem',
        background: '#f6f8fa',
        borderRadius: '8px',
        height: 240,
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          aria-hidden="true"
          style={{
            background: '#e5eaf0',
            borderRadius: '4px',
            animation: 'lineage-pulse 1.5s ease-in-out infinite',
          }}
        />
      ))}
    </div>
  );
}

function ContentRichError({ onRetry }: { onRetry: () => void }) {
  return (
    <div data-testid="listing-lineage-error">
      <h3>{t('lineage.listing.error.title')}</h3>
      <p>{t('lineage.listing.error.body')}</p>
      <button type="button" onClick={onRetry}>
        {t('lineage.listing.error.retry')}
      </button>
    </div>
  );
}

function ContentRichForbidden() {
  return (
    <div data-testid="listing-lineage-forbidden">
      <h3>{t('lineage.listing.forbidden.title')}</h3>
      <p>{t('lineage.listing.forbidden.body')}</p>
    </div>
  );
}

function ContentRichEmpty() {
  return (
    <div data-testid="listing-lineage-empty">
      <h3>{t('lineage.listing.empty.title')}</h3>
      <p>{t('lineage.listing.empty.body')}</p>
    </div>
  );
}

function PurchaseCTA({ onClick }: { onClick: () => void }) {
  return (
    <div
      data-testid="listing-lineage-purchase-cta"
      style={{
        marginTop: '1.5rem',
        padding: '1rem',
        background: '#fff7ed',
        border: '1px solid #fed7aa',
        borderRadius: '8px',
      }}
    >
      <h3>{t('lineage.listing.cta.heading')}</h3>
      <p>{t('lineage.listing.cta.body')}</p>
      <button type="button" onClick={onClick}>
        {t('lineage.listing.cta.button')}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getErrorCode(err: unknown): string | undefined {
  if (!err || typeof err !== 'object') return undefined;
  // Axios / apiClient error shape: { response: { data: { code: ... } } }
  const e = err as Record<string, unknown>;
  const response = (e.response as Record<string, unknown> | undefined);
  const data = response?.data as Record<string, unknown> | undefined;
  return typeof data?.code === 'string' ? data.code : undefined;
}
