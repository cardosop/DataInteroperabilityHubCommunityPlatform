/**
 * useToastManager Hook
 *
 * Hook for managing toast notifications with stacking support.
 */

import { useState, useCallback, useRef } from 'react'

export interface ToastOptions {
  message: string
  severity?: 'success' | 'warning' | 'error' | 'info'
  duration?: number
  action?: React.ReactNode
  onClose?: () => void
}

export interface Toast extends ToastOptions {
  id: string
}

export interface UseToastManagerOptions {
  /**
   * Maximum number of toasts to show
   * @default 5
   */
  maxToasts?: number
  /**
   * Default duration for toasts
   * @default 5000
   */
  defaultDuration?: number
}

/**
 * Hook for managing toast notifications
 */
export function useToastManager(options: UseToastManagerOptions = {}) {
  const { maxToasts = 5, defaultDuration = 5000 } = options
  const [toasts, setToasts] = useState<Toast[]>([])
  const timeoutRefs = useRef<Map<string, NodeJS.Timeout>>(new Map())

  const addToast = useCallback(
    (options: ToastOptions) => {
      const id = `toast-${Date.now()}-${Math.random()}`
      const toast: Toast = {
        id,
        message: options.message,
        severity: options.severity || 'info',
        duration: options.duration ?? defaultDuration,
        action: options.action,
        onClose: options.onClose,
      }

      setToasts((prev) => {
        const updated = [toast, ...prev]
        return updated.slice(0, maxToasts)
      })

      // Auto-dismiss
      if (toast.duration && toast.duration > 0) {
        const timeout = setTimeout(() => {
          removeToast(id)
        }, toast.duration)
        timeoutRefs.current.set(id, timeout)
      }

      return id
    },
    [maxToasts, defaultDuration]
  )

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
    const timeout = timeoutRefs.current.get(id)
    if (timeout) {
      clearTimeout(timeout)
      timeoutRefs.current.delete(id)
    }
  }, [])

  const clearAll = useCallback(() => {
    timeoutRefs.current.forEach((timeout) => clearTimeout(timeout))
    timeoutRefs.current.clear()
    setToasts([])
  }, [])

  const success = useCallback(
    (message: string, duration?: number) => {
      return addToast({ message, severity: 'success', duration })
    },
    [addToast]
  )

  const error = useCallback(
    (message: string, duration?: number) => {
      return addToast({ message, severity: 'error', duration })
    },
    [addToast]
  )

  const warning = useCallback(
    (message: string, duration?: number) => {
      return addToast({ message, severity: 'warning', duration })
    },
    [addToast]
  )

  const info = useCallback(
    (message: string, duration?: number) => {
      return addToast({ message, severity: 'info', duration })
    },
    [addToast]
  )

  return {
    toasts,
    addToast,
    removeToast,
    clearAll,
    success,
    error,
    warning,
    info,
  }
}

