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
  return (
    <div className="empty-state" data-testid={dataTestId}>
      <div className="empty-state-icon">{icon}</div>
      <h3 className="empty-state-title">{title ?? message}</h3>
      <p className="empty-state-message">{message}</p>
      {action && (
        <button className="empty-state-action" onClick={action.onClick} type="button">
          {action.label}
        </button>
      )}
    </div>
  );
}
