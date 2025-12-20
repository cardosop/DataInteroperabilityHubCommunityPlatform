import React, { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '@/components/utils'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'

export interface ModalProps {
  /**
   * Whether the modal is open
   */
  open: boolean
  /**
   * Callback when modal closes
   */
  onClose: () => void
  /**
   * Modal title
   */
  title?: string
  /**
   * Modal content
   */
  children: React.ReactNode
  /**
   * Action buttons
   */
  actions?: React.ReactNode
  /**
   * Size of the modal
   * @default 'md'
   */
  size?: 'sm' | 'md' | 'lg' | 'xl'
  className?: string
}

const sizeMap = {
  sm: '400px',
  md: '600px',
  lg: '900px',
  xl: '1200px',
} as const

/**
 * Modal component for modal dialogs
 */
export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  children,
  actions,
  size = 'md',
  className,
}) => {
  const modalRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleEscape)
      document.body.style.overflow = ''
    }
  }, [open, onClose])

  useEffect(() => {
    if (open && modalRef.current) {
      const focusable = modalRef.current.querySelector(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      ) as HTMLElement
      focusable?.focus()
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className={cn('modal-backdrop', className)}
      onClick={onClose}
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: spacing[4],
        animation: 'fadeIn 0.2s ease-out',
      }}
    >
      <div
        ref={modalRef}
        onClick={(e) => e.stopPropagation()}
        style={{
          background: colors.semantic.backgroundDefault,
          borderRadius: borderRadius.lg,
          boxShadow: shadows.elevation16,
          width: '100%',
          maxWidth: sizeMap[size],
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          animation: 'modalSlideIn 0.3s ease-out',
        }}
      >
        {title && (
          <div
            style={{
              padding: spacing[4],
              borderBottom: `1px solid ${colors.semantic.borderDivider}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 500 }}>
              {title}
            </h2>
            <button
              onClick={onClose}
              aria-label="Close modal"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '24px',
                color: colors.semantic.textSecondary,
              }}
            >
              ×
            </button>
          </div>
        )}
        <div
          style={{
            padding: spacing[4],
            overflowY: 'auto',
            flex: 1,
          }}
        >
          {children}
        </div>
        {actions && (
          <div
            style={{
              padding: spacing[4],
              borderTop: `1px solid ${colors.semantic.borderDivider}`,
              display: 'flex',
              justifyContent: 'flex-end',
              gap: spacing[2],
            }}
          >
            {actions}
          </div>
        )}
      </div>
      <style>
        {`
          @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
          @keyframes modalSlideIn {
            from {
              transform: scale(0.9) translateY(-20px);
              opacity: 0;
            }
            to {
              transform: scale(1) translateY(0);
              opacity: 1;
            }
          }
        `}
      </style>
    </div>,
    document.body
  )
}

Modal.displayName = 'Modal'

