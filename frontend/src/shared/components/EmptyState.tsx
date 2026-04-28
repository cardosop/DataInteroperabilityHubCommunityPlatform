/**
 * Empty State Component
 */

import './EmptyState.css';

interface EmptyStateProps {
  title?: string;
  message: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  icon?: string;
  /** Optional data-testid for E2E stable selectors */
  'data-testid'?: string;
}

export function EmptyState({ title, message, action, icon = '📭', 'data-testid': dataTestId }: EmptyStateProps) {
  // Phase 226.F1.b — fall back to a stable default testid so specs can
  // do `getByTestId('empty-state')` regardless of whether the call site
  // passed a more-specific override (e.g. 'asset-list-empty').
  return (
    <div className="empty-state" data-testid={dataTestId ?? 'empty-state'}>
      <div className="empty-state-icon">{icon}</div>
      <h3 className="empty-state-title" data-testid="empty-state-title">{title ?? message}</h3>
      <p className="empty-state-message" data-testid="empty-state-message">{message}</p>
      {action && (
        <button
          className="empty-state-action"
          onClick={action.onClick}
          type="button"
          data-testid="empty-state-action"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
