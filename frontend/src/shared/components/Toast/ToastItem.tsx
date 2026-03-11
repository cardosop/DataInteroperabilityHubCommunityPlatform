/**
 * Toast Item Component
 */

import type { Toast } from './ToastContext';
import './Toast.css';

interface ToastItemProps {
  toast: Toast;
  onClose: () => void;
}

export function ToastItem({ toast, onClose }: ToastItemProps) {
  return (
    <div
      className={`toast toast-${toast.type}`}
      role="status"
      aria-live="polite"
      data-testid="toast"
    >
      <span className="toast-message">{toast.message}</span>
      <button
        type="button"
        className="toast-close"
        onClick={onClose}
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}
