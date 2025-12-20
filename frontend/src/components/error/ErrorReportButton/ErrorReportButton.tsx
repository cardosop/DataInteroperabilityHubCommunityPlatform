/**
 * Error Report Button Component
 *
 * Component for reporting errors to support/Sentry.
 * Provides a user-friendly way to report issues with error context.
 */

import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { logError } from '@/services/errorLogging'
import { captureErrorContext } from '@/utils/errorContextCapture'
import type { Location } from 'react-router-dom'

export interface ErrorReportButtonProps {
  /**
   * Error to report
   */
  error: unknown
  /**
   * Button label
   * @default "Report Issue"
   */
  label?: string
  /**
   * React Router location (for context)
   */
  location?: Location
  /**
   * Additional context
   */
  context?: Record<string, any>
  /**
   * Callback when error is reported
   */
  onReported?: (eventId?: string) => void
  /**
   * Custom className
   */
  className?: string
  /**
   * Button variant
   * @default "outline"
   */
  variant?: 'primary' | 'outline' | 'text'
  /**
   * Button size
   * @default "md"
   */
  size?: 'sm' | 'md' | 'lg'
}

/**
 * ErrorReportButton component for reporting errors
 */
export const ErrorReportButton: React.FC<ErrorReportButtonProps> = ({
  error,
  label = 'Report Issue',
  location,
  context,
  onReported,
  className,
  variant = 'outline',
  size = 'md',
}) => {
  const [isReporting, setIsReporting] = useState(false)
  const [reported, setReported] = useState(false)

  const handleReport = async () => {
    if (isReporting || reported) return

    setIsReporting(true)

    try {
      // Capture error context
      const errorContext = captureErrorContext(error, {
        location,
        custom: {
          ...context,
          userReported: true,
          reportedAt: new Date().toISOString(),
        },
      })

      // Log error with full context
      const eventId = logError(error, {
        location,
        context: {
          ...context,
          ...errorContext,
          userReported: true,
        },
        tags: {
          user_reported: 'true',
        },
      })

      setReported(true)
      onReported?.(eventId)

      // Show success message briefly
      setTimeout(() => {
        setReported(false)
      }, 3000)
    } catch (reportError) {
      console.error('[ErrorReportButton] Failed to report error:', reportError)
    } finally {
      setIsReporting(false)
    }
  }

  const sizeStyles = {
    sm: {
      padding: `${spacing[1]}px ${spacing[2]}px`,
      fontSize: '12px',
      height: '28px',
    },
    md: {
      padding: `${spacing[2]}px ${spacing[3]}px`,
      fontSize: '14px',
      height: '36px',
    },
    lg: {
      padding: `${spacing[3]}px ${spacing[4]}px`,
      fontSize: '16px',
      height: '44px',
    },
  }

  const variantStyles = {
    primary: {
      background: colors.primary[500],
      color: '#FFFFFF',
      border: 'none',
      hoverBackground: colors.primary[600],
    },
    outline: {
      background: 'transparent',
      color: colors.primary[500],
      border: `1px solid ${colors.primary[500]}`,
      hoverBackground: colors.primary[50],
    },
    text: {
      background: 'transparent',
      color: colors.primary[500],
      border: 'none',
      hoverBackground: colors.primary[50],
    },
  }

  const style = variantStyles[variant]
  const sizeStyle = sizeStyles[size]

  return (
    <button
      type="button"
      onClick={handleReport}
      disabled={isReporting || reported}
      className={cn('error-report-button', className)}
      style={{
        ...sizeStyle,
        ...style,
        borderRadius: borderRadius.md,
        fontWeight: 500,
        cursor: isReporting || reported ? 'not-allowed' : 'pointer',
        opacity: isReporting || reported ? 0.6 : 1,
        transition: 'all 0.2s',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[1],
        outline: 'none',
      }}
      onMouseEnter={(e) => {
        if (!isReporting && !reported) {
          e.currentTarget.style.background = style.hoverBackground
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = style.background
      }}
      onFocus={(e) => {
        e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
        e.currentTarget.style.outlineOffset = '2px'
      }}
      onBlur={(e) => {
        e.currentTarget.style.outline = 'none'
      }}
      aria-label={reported ? 'Issue reported' : label}
    >
      {isReporting ? (
        <>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            style={{
              animation: 'spin 1s linear infinite',
            }}
          >
            <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
          </svg>
          Reporting...
        </>
      ) : reported ? (
        <>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M20 6L9 17l-5-5" />
          </svg>
          Reported
        </>
      ) : (
        <>
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            <line x1="9" y1="10" x2="15" y2="10" />
            <line x1="9" y1="14" x2="15" y2="14" />
          </svg>
          {label}
        </>
      )}
      <style>
        {`
          @keyframes spin {
            from {
              transform: rotate(0deg);
            }
            to {
              transform: rotate(360deg);
            }
          }
        `}
      </style>
    </button>
  )
}

ErrorReportButton.displayName = 'ErrorReportButton'

