/**
 * ListPageSkeleton — Phase 40 (38.2)
 *
 * Skeleton placeholder for list pages: title bar, action row, 8 list-item rows.
 */

import { Skeleton } from '../Skeleton';

const ROW_COUNT = 8;

export function ListPageSkeleton() {
  return (
    <div style={{ padding: 'var(--spacing-lg, 24px)', maxWidth: 'var(--layout-content-max-width, 1200px)', margin: '0 auto' }}>
      {/* Page title placeholder */}
      <Skeleton.Block height="32px" width="200px" />

      {/* Action button row placeholder */}
      <div style={{ marginTop: 'var(--spacing-md, 16px)', marginBottom: 'var(--spacing-lg, 24px)' }}>
        <Skeleton.Block height="40px" />
      </div>

      {/* List item rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md, 16px)' }}>
        {Array.from({ length: ROW_COUNT }, (_, i) => (
          <div
            key={i}
            data-testid="skeleton-row"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 'var(--spacing-md, 16px)',
            }}
          >
            <Skeleton.Circle size="36px" />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <Skeleton.Line width="60%" />
              <Skeleton.Line width="40%" height="var(--font-size-xs, 12px)" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
