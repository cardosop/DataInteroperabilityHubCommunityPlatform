import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { HelpOutline, Close } from '@mui/icons-material'
import { Button } from '@mui/material'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { cn } from '@/components/utils'

export interface EnhancedTooltipProps {
  /**
   * Tooltip content
   */
  content: string | React.ReactNode
  /**
   * Placement of the tooltip
   * @default 'top'
   */
  placement?: 'top' | 'bottom' | 'left' | 'right'
  /**
   * Trigger element (if not provided, shows help icon)
   */
  children?: React.ReactElement
  /**
   * Show help icon trigger
   * @default true
   */
  showHelpIcon?: boolean
  /**
   * Title for the tooltip
   */
  title?: string
  /**
   * Feature highlight mode (larger, more prominent)
   * @default false
   */
  highlight?: boolean
  /**
   * Show close button
   * @default false
   */
  showClose?: boolean
  /**
   * Link to documentation
   */
  learnMoreLink?: {
    text: string
    href: string
    external?: boolean
  }
  /**
   * Trigger mode
   * @default 'hover'
   */
  trigger?: 'hover' | 'click' | 'focus'
  /**
   * Delay before showing (ms) - only for hover
   * @default 200
   */
  delay?: number
  /**
   * Max width of tooltip
   * @default '300px'
   */
  maxWidth?: string
  className?: string
}

/**
 * Enhanced Tooltip component with advanced features
 *
 * Features:
 * - Help text and feature highlights
 * - Title and content sections
 * - Learn more links
 * - Multiple trigger modes (hover, click, focus)
 * - Customizable styling
 */
export const EnhancedTooltip: React.FC<EnhancedTooltipProps> = ({
  content,
  placement = 'top',
  children,
  showHelpIcon = true,
  title,
  highlight = false,
  showClose = false,
  learnMoreLink,
  trigger = 'hover',
  delay = 200,
  maxWidth = '300px',
  className,
}) => {
  const [isVisible, setIsVisible] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef<HTMLElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const timeoutRef = useRef<NodeJS.Timeout>()

  const updatePosition = () => {
    if (!triggerRef.current || !tooltipRef.current) return

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    const gap = 8

    let top = 0
    let left = 0

    switch (placement) {
      case 'top':
        top = triggerRect.top - tooltipRect.height - gap
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'bottom':
        top = triggerRect.bottom + gap
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'left':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.left - tooltipRect.width - gap
        break
      case 'right':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.right + gap
        break
    }

    // Keep within viewport
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    top = Math.max(8, Math.min(top, viewportHeight - tooltipRect.height - 8))
    left = Math.max(8, Math.min(left, viewportWidth - tooltipRect.width - 8))

    setPosition({ top, left })
  }

  useEffect(() => {
    if (isVisible) {
      updatePosition()
      window.addEventListener('scroll', updatePosition, true)
      window.addEventListener('resize', updatePosition)
      return () => {
        window.removeEventListener('scroll', updatePosition, true)
        window.removeEventListener('resize', updatePosition)
      }
    }
  }, [isVisible, placement])

  const showTooltip = () => {
    if (trigger === 'hover') {
      timeoutRef.current = setTimeout(() => {
        setIsVisible(true)
      }, delay)
    } else {
      setIsVisible(true)
    }
  }

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setIsVisible(false)
  }

  const handleClick = (e: React.MouseEvent) => {
    if (trigger === 'click') {
      e.stopPropagation()
      if (isVisible) {
        hideTooltip()
      } else {
        showTooltip()
      }
    }
  }

  // Close on outside click for click mode
  useEffect(() => {
    if (trigger === 'click' && isVisible) {
      const handleClickOutside = (e: MouseEvent) => {
        if (
          tooltipRef.current &&
          !tooltipRef.current.contains(e.target as Node) &&
          triggerRef.current &&
          !triggerRef.current.contains(e.target as Node)
        ) {
          hideTooltip()
        }
      }
      document.addEventListener('mousedown', handleClickOutside)
      return () => {
        document.removeEventListener('mousedown', handleClickOutside)
      }
    }
  }, [trigger, isVisible])

  const triggerElement = children || (
    <button
      type="button"
      aria-label="Help"
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: spacing[1],
        color: highlight ? colors.primary[500] : colors.semantic.textSecondary,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <HelpOutline fontSize="small" />
    </button>
  )

  const trigger = React.cloneElement(triggerElement, {
    ref: triggerRef,
    onMouseEnter: trigger === 'hover' ? showTooltip : undefined,
    onMouseLeave: trigger === 'hover' ? hideTooltip : undefined,
    onClick: handleClick,
    onFocus: trigger === 'focus' ? showTooltip : undefined,
    onBlur: trigger === 'focus' ? hideTooltip : undefined,
  })

  return (
    <>
      {trigger}
      {isVisible &&
        createPortal(
          <div
            ref={tooltipRef}
            className={cn('enhanced-tooltip', className)}
            style={{
              position: 'fixed',
              top: `${position.top}px`,
              left: `${position.left}px`,
              background: highlight
                ? colors.semantic.backgroundDefault
                : colors.gray[900],
              color: highlight ? colors.semantic.textPrimary : '#FFFFFF',
              padding: highlight ? spacing[4] : `${spacing[2]}px ${spacing[3]}px`,
              borderRadius: borderRadius.md,
              fontSize: highlight ? '14px' : '12px',
              boxShadow: shadows.elevation16,
              zIndex: 10001,
              pointerEvents: 'auto',
              maxWidth,
              lineHeight: 1.5,
            }}
          >
            {highlight && (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: title ? spacing[2] : 0,
                }}
              >
                {title && (
                  <h4
                    style={{
                      fontSize: '16px',
                      fontWeight: 600,
                      margin: 0,
                      marginBottom: spacing[2],
                    }}
                  >
                    {title}
                  </h4>
                )}
                {showClose && (
                  <button
                    onClick={hideTooltip}
                    aria-label="Close"
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: spacing[1],
                      color: colors.semantic.textSecondary,
                      display: 'flex',
                      alignItems: 'center',
                      marginLeft: spacing[2],
                    }}
                  >
                    <Close fontSize="small" />
                  </button>
                )}
              </div>
            )}
            <div>{content}</div>
            {learnMoreLink && (
              <div
                style={{
                  marginTop: spacing[2],
                  paddingTop: spacing[2],
                  borderTop: `1px solid ${
                    highlight
                      ? colors.semantic.borderDivider
                      : 'rgba(255, 255, 255, 0.2)'
                  }`,
                }}
              >
                <a
                  href={learnMoreLink.href}
                  target={learnMoreLink.external ? '_blank' : undefined}
                  rel={learnMoreLink.external ? 'noopener noreferrer' : undefined}
                  style={{
                    fontSize: '12px',
                    color: highlight
                      ? colors.primary[600]
                      : 'rgba(255, 255, 255, 0.9)',
                    textDecoration: 'none',
                    fontWeight: 500,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.textDecoration = 'underline'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.textDecoration = 'none'
                  }}
                >
                  {learnMoreLink.text} {learnMoreLink.external && '↗'}
                </a>
              </div>
            )}
          </div>,
          document.body
        )}
    </>
  )
}

EnhancedTooltip.displayName = 'EnhancedTooltip'

