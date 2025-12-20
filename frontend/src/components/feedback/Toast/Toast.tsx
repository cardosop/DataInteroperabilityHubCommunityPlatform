import React, { createContext, useContext, useCallback } from 'react'
import { ToastManager } from './ToastManager'
import { useToastManager } from './useToastManager'

interface ToastContextValue {
  show: (
    message: string,
    severity?: 'success' | 'warning' | 'error' | 'info',
    duration?: number
  ) => string
  success: (message: string, duration?: number) => string
  error: (message: string, duration?: number) => string
  warning: (message: string, duration?: number) => string
  info: (message: string, duration?: number) => string
  remove: (id: string) => void
  clearAll: () => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export const useToast = () => {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

export interface ToastProviderProps {
  children: React.ReactNode
  /**
   * Position of toast notifications
   * @default 'top-right'
   */
  position?:
    | 'top-right'
    | 'top-left'
    | 'top-center'
    | 'bottom-right'
    | 'bottom-left'
    | 'bottom-center'
  /**
   * Maximum number of toasts
   * @default 5
   */
  maxToasts?: number
}

export const ToastProvider: React.FC<ToastProviderProps> = ({
  children,
  position = 'top-right',
  maxToasts = 5,
}) => {
  const { addToast, removeToast, clearAll, success, error, warning, info } =
    useToastManager({ maxToasts })

  const show = useCallback(
    (
      message: string,
      severity: 'success' | 'warning' | 'error' | 'info' = 'info',
      duration = 5000
    ) => {
      return addToast({ message, severity, duration })
    },
    [addToast]
  )

  const successHandler = useCallback(
    (message: string, duration = 5000) => {
      return success(message, duration)
    },
    [success]
  )

  const errorHandler = useCallback(
    (message: string, duration = 5000) => {
      return error(message, duration)
    },
    [error]
  )

  const warningHandler = useCallback(
    (message: string, duration = 5000) => {
      return warning(message, duration)
    },
    [warning]
  )

  const infoHandler = useCallback(
    (message: string, duration = 5000) => {
      return info(message, duration)
    },
    [info]
  )

  return (
    <ToastContext.Provider
      value={{
        show,
        success: successHandler,
        error: errorHandler,
        warning: warningHandler,
        info: infoHandler,
        remove: removeToast,
        clearAll,
      }}
    >
      {children}
      <ToastManager position={position} maxToasts={maxToasts} />
    </ToastContext.Provider>
  )
}

/**
 * Toast component - use via useToast hook
 */
export const Toast: React.FC = () => {
  return null // Toast is rendered via ToastProvider
}

Toast.displayName = 'Toast'

