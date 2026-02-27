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
}

export function EmptyState({ title, message, action, icon = '📭' }: EmptyStateProps) {
  return (
    <div className="empty-state">
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
