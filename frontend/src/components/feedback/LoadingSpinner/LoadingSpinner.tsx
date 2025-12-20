import React from 'react'
import { cn } from '@/components/utils'
import { CircularProgress } from '../CircularProgress'

export interface LoadingSpinnerProps {
  /**
   * Size of the spinner
   * @default 'md'
   */
  size?: 'sm' | 'md' | 'lg'
  /**
   * Color variant
   * @default 'primary'
   */
  color?: 'primary' | 'white'
  /**
   * Whether to show as full-page overlay
   * @default false
   */
  fullPage?: boolean
  /**
   * Whether to show as inline spinner
   * @default true
   */
  inline?: boolean
  /**
   * Loading message
   */
  message?: string
  className?: string
}

/**
 * LoadingSpinner component for loading states
 */
export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'primary',
  fullPage = false,
  inline = true,
  message,
  className,
}) => {
  if (fullPage) {
    return (
      <div
        className={cn('loading-spinner', 'loading-spinner-fullpage', className)}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(255, 255, 255, 0.8)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '16px',
          zIndex: 9999,
        }}
      >
        <CircularProgress size={size} color={color} />
        {message && (
          <div style={{ fontSize: '14px', color: '#666' }}>{message}</div>
        )}
      </div>
    )
  }

  return (
    <div
      className={cn('loading-spinner', 'loading-spinner-inline', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        padding: inline ? '16px' : 0,
      }}
    >
      <CircularProgress size={size} color={color} />
      {message && (
        <div style={{ fontSize: '14px', color: '#666' }}>{message}</div>
      )}
    </div>
  )
}

LoadingSpinner.displayName = 'LoadingSpinner'

