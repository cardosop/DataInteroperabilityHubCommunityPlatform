/**
 * Toast Provider Component
 */

import { useCallback, useRef, useState } from 'react';
import { ToastItem } from './ToastItem';
import { ToastContext } from './toastTypes';
import type { Toast, ToastType } from './toastTypes';

export type { Toast, ToastType } from './toastTypes';
export { ToastContext } from './toastTypes';

const DEFAULT_DURATION = 4000;

const DEDUP_WINDOW_MS = 500;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const recentRef = useRef<Map<string, number>>(new Map());
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const addToast = useCallback((type: ToastType, message: string, duration = DEFAULT_DURATION) => {
    // Deduplication: skip if an identical message was shown within DEDUP_WINDOW_MS
    const now = Date.now();
    const key = `${type}:${message}`;
    const lastShown = recentRef.current.get(key);
    if (lastShown !== undefined && now - lastShown < DEDUP_WINDOW_MS) return;
    recentRef.current.set(key, now);

    const id = `toast-${now}-${Math.random().toString(36).slice(2)}`;
    const toast: Toast = { id, type, message, duration };
    setToasts((prev) => [...prev, toast]);

    if (duration > 0) {
      const timer = setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
        recentRef.current.delete(key);
        timersRef.current.delete(id);
      }, duration);
      timersRef.current.set(id, timer);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timersRef.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timersRef.current.delete(id);
    }
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="toast-container" role="region" aria-label="Notifications" data-testid="toast-container">
        {toasts.map((toast) => (
          <ToastItem
            key={toast.id}
            toast={toast}
            onClose={() => removeToast(toast.id)}
          />
        ))}
      </div>
    </ToastContext.Provider>
  );
}
