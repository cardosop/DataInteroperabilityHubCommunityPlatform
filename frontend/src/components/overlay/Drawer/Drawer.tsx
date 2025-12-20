import React, { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/components/utils'
import { colors, spacing, shadows } from '@/styles/tokens'

export interface DrawerProps {
  /**
   * Whether the drawer is open
   */
  open: boolean
  /**
   * Callback when drawer closes
   */
  onClose: () => void
  /**
   * Drawer content
   */
  children: React.ReactNode
  /**
   * Anchor position
   * @default 'right'
   */
  anchor?: 'left' | 'right' | 'bottom'
  /**
   * Width of the drawer (for left/right)
   * @default '400px'
   */
  width?: string
  /**
   * Height of the drawer (for bottom)
   * @default '50vh'
   */
  height?: string
  className?: string
}

/**
 * Drawer component for side panels
 */
export const Drawer: React.FC<DrawerProps> = ({
  open,
  onClose,
  children,
  anchor = 'right',
  width = '400px',
  height = '50vh',
  className,
}) => {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
      return () => {
        document.body.style.overflow = ''
      }
    }
  }, [open])

  if (!open) return null

  const getStyle = (): React.CSSProperties => {
    const base: React.CSSProperties = {
      position: 'fixed',
      background: colors.semantic.backgroundDefault,
      boxShadow: shadows.elevation8,
      zIndex: 10000,
    }

    if (anchor === 'left' || anchor === 'right') {
      return {
        ...base,
        top: 0,
        bottom: 0,
        [anchor]: 0,
        width,
        animation: `drawer-slide-${anchor} 0.3s ease-out`,
      }
    }

    return {
      ...base,
      bottom: 0,
      left: 0,
      right: 0,
      height,
      animation: 'drawer-slide-bottom 0.3s ease-out',
    }
  }

  return createPortal(
    <>
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          zIndex: 9999,
          animation: 'fadeIn 0.2s ease-out',
        }}
      />
      <div className={cn('drawer', className)} style={getStyle()}>
        {children}
      </div>
      <style>
        {`
          @keyframes drawer-slide-left {
            from { transform: translateX(-100%); }
            to { transform: translateX(0); }
          }
          @keyframes drawer-slide-right {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
          }
          @keyframes drawer-slide-bottom {
            from { transform: translateY(100%); }
            to { transform: translateY(0); }
          }
        `}
      </style>
    </>,
    document.body
  )
}

Drawer.displayName = 'Drawer'

