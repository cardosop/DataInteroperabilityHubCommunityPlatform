/**
 * DetailPageSkeleton — Phase 40 (38.3)
 *
 * Skeleton placeholder for detail pages: breadcrumb, title, two-column field grid.
 */

import { Skeleton } from '../Skeleton';

const FIELD_COUNT = 6;

export function DetailPageSkeleton() {
  return (
    <div style={{ padding: 'var(--spacing-lg, 24px)', maxWidth: 'var(--layout-content-max-width, 1200px)', margin: '0 auto' }}>
      {/* Breadcrumb skeleton */}
      <div style={{ display: 'flex', gap: 'var(--spacing-sm, 8px)', marginBottom: 'var(--spacing-md, 16px)' }}>
        <Skeleton.Line width="80px" />
        <Skeleton.Line width="80px" />
        <Skeleton.Line width="80px" />
      </div>

      {/* Title */}
      <div style={{ marginBottom: 'var(--spacing-lg, 24px)' }}>
        <Skeleton.Block height="36px" width="300px" />
      </div>

      {/* Two-column field grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 'var(--spacing-md, 16px)',
      }}>
        {Array.from({ length: FIELD_COUNT }, (_, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <Skeleton.Line width="120px" height="var(--font-size-xs, 12px)" />
            <Skeleton.Line />
          </div>
        ))}
      </div>
    </div>
  );
}
