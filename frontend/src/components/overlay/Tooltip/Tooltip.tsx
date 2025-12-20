import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'

export interface TooltipProps {
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
   * Trigger element
   */
  children: React.ReactElement
  /**
   * Delay before showing (ms)
   * @default 200
   */
  delay?: number
}

/**
 * Tooltip component for hover tooltips
 */
export const Tooltip: React.FC<TooltipProps> = ({
  content,
  placement = 'top',
  children,
  delay = 200,
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

    let top = 0
    let left = 0

    switch (placement) {
      case 'top':
        top = triggerRect.top - tooltipRect.height - 8
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'bottom':
        top = triggerRect.bottom + 8
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2
        break
      case 'left':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.left - tooltipRect.width - 8
        break
      case 'right':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2
        left = triggerRect.right + 8
        break
    }

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

  const handleMouseEnter = () => {
    timeoutRef.current = setTimeout(() => {
      setIsVisible(true)
    }, delay)
  }

  const handleMouseLeave = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }
    setIsVisible(false)
  }

  const trigger = React.cloneElement(children, {
    ref: triggerRef,
    onMouseEnter: handleMouseEnter,
    onMouseLeave: handleMouseLeave,
  })

  return (
    <>
      {trigger}
      {isVisible &&
        createPortal(
          <div
            ref={tooltipRef}
            style={{
              position: 'fixed',
              top: `${position.top}px`,
              left: `${position.left}px`,
              background: colors.gray[900],
              color: '#FFFFFF',
              padding: `${spacing[1]}px ${spacing[2]}px`,
              borderRadius: borderRadius.sm,
              fontSize: '12px',
              boxShadow: shadows.elevation8,
              zIndex: 10001,
              pointerEvents: 'none',
              whiteSpace: 'nowrap',
            }}
          >
            {content}
          </div>,
          document.body
        )}
    </>
  )
}

Tooltip.displayName = 'Tooltip'

