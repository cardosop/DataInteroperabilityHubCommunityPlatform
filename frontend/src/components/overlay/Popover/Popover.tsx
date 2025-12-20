import React, { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'

export interface PopoverProps {
  /**
   * Trigger element
   */
  trigger: React.ReactElement
  /**
   * Popover content
   */
  content: React.ReactNode
  /**
   * Placement of the popover
   * @default 'bottom-start'
   */
  placement?:
    | 'bottom-start'
    | 'bottom-end'
    | 'top-start'
    | 'top-end'
    | 'left-start'
    | 'left-end'
    | 'right-start'
    | 'right-end'
  /**
   * Whether the popover is open (controlled)
   */
  open?: boolean
  /**
   * Callback when open state changes
   */
  onOpenChange?: (open: boolean) => void
}

/**
 * Popover component for click-triggered popovers
 */
export const Popover: React.FC<PopoverProps> = ({
  trigger,
  content,
  placement = 'bottom-start',
  open: controlledOpen,
  onOpenChange,
}) => {
  const [internalOpen, setInternalOpen] = useState(false)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const triggerRef = useRef<HTMLElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)

  const isOpen = controlledOpen !== undefined ? controlledOpen : internalOpen

  const updatePosition = () => {
    if (!triggerRef.current || !popoverRef.current) return

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const popoverRect = popoverRef.current.getBoundingClientRect()

    let top = 0
    let left = 0

    const [vertical, horizontal] = placement.split('-')

    if (vertical === 'bottom') {
      top = triggerRect.bottom + 8
      left =
        horizontal === 'start'
          ? triggerRect.left
          : triggerRect.right - popoverRect.width
    } else if (vertical === 'top') {
      top = triggerRect.top - popoverRect.height - 8
      left =
        horizontal === 'start'
          ? triggerRect.left
          : triggerRect.right - popoverRect.width
    } else if (vertical === 'left') {
      top =
        horizontal === 'start'
          ? triggerRect.top
          : triggerRect.bottom - popoverRect.height
      left = triggerRect.left - popoverRect.width - 8
    } else if (vertical === 'right') {
      top =
        horizontal === 'start'
          ? triggerRect.top
          : triggerRect.bottom - popoverRect.height
      left = triggerRect.right + 8
    }

    setPosition({ top, left })
  }

  useEffect(() => {
    if (isOpen) {
      updatePosition()
      window.addEventListener('scroll', updatePosition, true)
      window.addEventListener('resize', updatePosition)
      return () => {
        window.removeEventListener('scroll', updatePosition, true)
        window.removeEventListener('resize', updatePosition)
      }
    }
  }, [isOpen, placement])

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node) &&
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node)
      ) {
        if (controlledOpen === undefined) {
          setInternalOpen(false)
        }
        onOpenChange?.(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, controlledOpen, onOpenChange])

  const handleToggle = () => {
    const newOpen = !isOpen
    if (controlledOpen === undefined) {
      setInternalOpen(newOpen)
    }
    onOpenChange?.(newOpen)
  }

  const triggerElement = React.cloneElement(trigger, {
    ref: triggerRef,
    onClick: handleToggle,
  })

  return (
    <>
      {triggerElement}
      {isOpen &&
        createPortal(
          <div
            ref={popoverRef}
            style={{
              position: 'fixed',
              top: `${position.top}px`,
              left: `${position.left}px`,
              background: colors.semantic.backgroundDefault,
              border: `1px solid ${colors.semantic.borderDefault}`,
              borderRadius: borderRadius.md,
              boxShadow: shadows.elevation8,
              padding: spacing[2],
              zIndex: 10001,
              minWidth: '200px',
              maxHeight: '300px',
              overflowY: 'auto',
            }}
          >
            {content}
          </div>,
          document.body
        )}
    </>
  )
}

Popover.displayName = 'Popover'

