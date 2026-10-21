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
  // W5.4 (R2-F5) — assertive error toasts: a failed save must interrupt the
  // screen reader immediately, not queue behind polite chatter. Success and
  // info stay polite (role=status) — they are ambient confirmation, not an
  // interruption.
  const assertive = toast.type === 'error';
  return (
    <div
      className={`toast toast-${toast.type}`}
      role={assertive ? 'alert' : 'status'}
      aria-live={assertive ? 'assertive' : 'polite'}
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
