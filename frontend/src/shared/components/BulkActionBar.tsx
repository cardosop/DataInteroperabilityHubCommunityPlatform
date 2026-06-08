/**
 * Phase 278.E.2 — sticky bulk-action bar for multi-select list pages.
 */
import type { FC } from 'react';

export interface BulkAction {
  label: string;
  onClick: () => void;
  variant?: 'default' | 'danger';
  disabled?: boolean;
  'data-testid'?: string;
}

export interface BulkActionBarProps {
  selectedCount: number;
  totalCount?: number;
  actions: BulkAction[];
  onClear: () => void;
  resourceLabel?: string;
  'data-testid'?: string;
}

export const BulkActionBar: FC<BulkActionBarProps> = ({
  selectedCount,
  totalCount,
  actions,
  onClear,
  resourceLabel = 'items',
  'data-testid': testId = 'bulk-action-bar',
}) => {
  if (selectedCount === 0) return null;

  return (
    <div className="bulk-action-bar" role="toolbar" data-testid={testId}>
      <span className="bulk-action-bar__count">
        {selectedCount} {resourceLabel} selected
        {totalCount != null && ` of ${totalCount}`}
      </span>
      <div className="bulk-action-bar__actions">
        {actions.map((action) => (
          <button
            key={action.label}
            type="button"
            className={`bulk-action-bar__btn bulk-action-bar__btn--${action.variant || 'default'}`}
            disabled={action.disabled}
            onClick={action.onClick}
            data-testid={action['data-testid']}
          >
            {action.label}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="bulk-action-bar__clear"
        onClick={onClear}
        aria-label="Clear selection"
      >
        Clear
      </button>
    </div>
  );
};
