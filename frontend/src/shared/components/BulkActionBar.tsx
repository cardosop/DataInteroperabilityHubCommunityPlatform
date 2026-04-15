/**
 * BulkActionBar — 223.3.2.
 *
 * Sticky bottom bar that appears only while rows are selected. Pages
 * pass their own action buttons (approve / reject / delete) plus a
 * deselect-all callback; the bar renders nothing when `selectedCount`
 * is 0 so it never occludes the list otherwise.
 */

import type { ReactNode } from 'react';
import './BulkActionBar.css';

export type BulkActionVariant = 'primary' | 'secondary' | 'danger';

export interface BulkAction {
  label: string;
  onClick: () => void;
  variant?: BulkActionVariant;
  disabled?: boolean;
  /** Optional icon/node rendered before the label. */
  leadingIcon?: ReactNode;
  'data-testid'?: string;
}

export interface BulkActionBarProps {
  selectedCount: number;
  onDeselectAll: () => void;
  actions: BulkAction[];
  /** Optional contextual helper shown on the left of the bar. */
  description?: ReactNode;
}

export function BulkActionBar({
  selectedCount,
  onDeselectAll,
  actions,
  description,
}: BulkActionBarProps) {
  if (selectedCount <= 0) return null;

  return (
    <div
      className="bulk-action-bar"
      role="region"
      aria-label="Bulk actions"
      data-testid="bulk-action-bar"
    >
      <div className="bulk-action-bar__info">
        <span className="bulk-action-bar__count">
          <strong>{selectedCount}</strong> selected
        </span>
        {description && (
          <span className="bulk-action-bar__desc">{description}</span>
        )}
      </div>
      <div className="bulk-action-bar__actions">
        {actions.map((action) => (
          <button
            key={action.label}
            type="button"
            className={`bulk-action-bar__btn bulk-action-bar__btn--${action.variant ?? 'secondary'}`}
            onClick={action.onClick}
            disabled={action.disabled}
            data-testid={action['data-testid']}
          >
            {action.leadingIcon}
            {action.label}
          </button>
        ))}
        <button
          type="button"
          className="bulk-action-bar__btn bulk-action-bar__btn--ghost"
          onClick={onDeselectAll}
          aria-label="Clear selection"
        >
          Clear selection
        </button>
      </div>
    </div>
  );
}
