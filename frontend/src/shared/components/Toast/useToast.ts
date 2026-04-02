/**
 * useToast hook — extracted to satisfy react-refresh/only-export-components.
 */

import { useContext } from 'react';
import { ToastContext } from './toastTypes';

/** No-op fallback when used outside ToastProvider (safe for tests and SSR). */
const NOOP_TOAST: { success: (message: string, duration?: number) => void; error: (message: string, duration?: number) => void; info: (message: string, duration?: number) => void } = {
  success: () => {},
  error: () => {},
  info: () => {},
};

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) return NOOP_TOAST;
  return {
    success: (message: string, duration?: number) => ctx.addToast('success', message, duration),
    error: (message: string, duration?: number) => ctx.addToast('error', message, duration),
    info: (message: string, duration?: number) => ctx.addToast('info', message, duration),
  };
}
