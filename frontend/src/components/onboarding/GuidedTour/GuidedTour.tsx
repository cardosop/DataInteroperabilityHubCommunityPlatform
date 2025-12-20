import React, { useState, useEffect, useRef, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@mui/material'
import { Close, ArrowBack, ArrowForward, SkipNext } from '@mui/icons-material'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { cn } from '@/components/utils'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export interface TourStep {
  /**
   * Unique identifier for the step
   */
  id: string
  /**
   * Step title
   */
  title: string
  /**
   * Step description/content
   */
  content: React.ReactNode
  /**
   * CSS selector or ref to the target element
   */
  target: string | React.RefObject<HTMLElement>
  /**
   * Placement of the tooltip relative to target
   * @default 'bottom'
   */
  placement?: 'top' | 'bottom' | 'left' | 'right' | 'center'
  /**
   * Optional action to perform when step is shown
   */
  onShow?: () => void
  /**
   * Optional action to perform when step is completed
   */
  onComplete?: () => void
}

export interface GuidedTourProps {
  /**
   * Tour steps
   */
  steps: TourStep[]
  /**
   * Whether tour is active
   */
  isActive: boolean
  /**
   * Callback when tour starts
   */
  onStart?: () => void
  /**
   * Callback when tour completes
   */
  onComplete?: () => void
  /**
   * Callback when tour is skipped
   */
  onSkip?: () => void
  /**
   * Storage key for remembering completion
   */
  storageKey?: string
  /**
   * Show skip button
   * @default true
   */
  showSkip?: boolean
  /**
   * Show progress indicator
   * @default true
   */
  showProgress?: boolean
  /**
   * Close on backdrop click
   * @default false
   */
  closeOnBackdropClick?: boolean
  /**
   * Highlight target element
   * @default true
   */
  highlightTarget?: boolean
  className?: string
}

/**
 * Calculate position for tooltip based on target and placement
 */
function calculatePosition(
  targetRect: DOMRect,
  tooltipRect: DOMRect,
  placement: TourStep['placement'],
  viewportWidth: number,
  viewportHeight: number
): { top: number; left: number } {
  const gap = 16
  let top = 0
  let left = 0

  switch (placement) {
    case 'top':
      top = targetRect.top - tooltipRect.height - gap
      left = targetRect.left + targetRect.width / 2 - tooltipRect.width / 2
      break
    case 'bottom':
      top = targetRect.bottom + gap
      left = targetRect.left + targetRect.width / 2 - tooltipRect.width / 2
      break
    case 'left':
      top = targetRect.top + targetRect.height / 2 - tooltipRect.height / 2
      left = targetRect.left - tooltipRect.width - gap
      break
    case 'right':
      top = targetRect.top + targetRect.height / 2 - tooltipRect.height / 2
      left = targetRect.right + gap
      break
    case 'center':
      top = viewportHeight / 2 - tooltipRect.height / 2
      left = viewportWidth / 2 - tooltipRect.width / 2
      break
    default:
      // Auto-detect best placement
      const spaceTop = targetRect.top
      const spaceBottom = viewportHeight - targetRect.bottom
      const spaceLeft = targetRect.left
      const spaceRight = viewportWidth - targetRect.right

      if (spaceBottom >= tooltipRect.height + gap) {
        top = targetRect.bottom + gap
        left = targetRect.left + targetRect.width / 2 - tooltipRect.width / 2
      } else if (spaceTop >= tooltipRect.height + gap) {
        top = targetRect.top - tooltipRect.height - gap
        left = targetRect.left + targetRect.width / 2 - tooltipRect.width / 2
      } else if (spaceRight >= tooltipRect.width + gap) {
        top = targetRect.top + targetRect.height / 2 - tooltipRect.height / 2
        left = targetRect.right + gap
      } else {
        top = targetRect.top + targetRect.height / 2 - tooltipRect.height / 2
        left = targetRect.left - tooltipRect.width - gap
      }
  }

  // Keep tooltip within viewport
  top = Math.max(gap, Math.min(top, viewportHeight - tooltipRect.height - gap))
  left = Math.max(gap, Math.min(left, viewportWidth - tooltipRect.width - gap))

  return { top, left }
}

/**
 * GuidedTour component for step-by-step onboarding
 *
 * Features:
 * - Step-by-step tooltips
 * - Highlights target elements
 * - Progress indicator
 * - Skip option
 * - Remembers completion
 * - Smooth transitions
 */
export const GuidedTour: React.FC<GuidedTourProps> = ({
  steps,
  isActive,
  onStart,
  onComplete,
  onSkip,
  storageKey,
  showSkip = true,
  showProgress = true,
  closeOnBackdropClick = false,
  highlightTarget = true,
  className,
}) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [position, setPosition] = useState({ top: 0, left: 0 })
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const [completed, setCompleted] = useLocalStorage(
    storageKey || 'guided-tour-completed',
    false
  )

  const currentStepData = steps[currentStep]
  const isLastStep = currentStep === steps.length - 1
  const isFirstStep = currentStep === 0

  // Update position when step changes or window resizes
  const updatePosition = useCallback(() => {
    if (!currentStepData || !tooltipRef.current) return

    let targetElement: HTMLElement | null = null

    if (typeof currentStepData.target === 'string') {
      targetElement = document.querySelector<HTMLElement>(
        currentStepData.target
      )
    } else if (currentStepData.target?.current) {
      targetElement = currentStepData.target.current
    }

    if (!targetElement) {
      // Center tooltip if target not found
      const viewportWidth = window.innerWidth
      const viewportHeight = window.innerHeight
      const tooltipRect = tooltipRef.current.getBoundingClientRect()
      setPosition({
        top: viewportHeight / 2 - tooltipRect.height / 2,
        left: viewportWidth / 2 - tooltipRect.width / 2,
      })
      setTargetRect(null)
      return
    }

    const rect = targetElement.getBoundingClientRect()
    setTargetRect(rect)

    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    const pos = calculatePosition(
      rect,
      tooltipRect,
      currentStepData.placement || 'bottom',
      viewportWidth,
      viewportHeight
    )

    setPosition(pos)

    // Scroll target into view if needed
    targetElement.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
      inline: 'center',
    })
  }, [currentStepData])

  useEffect(() => {
    if (isActive && currentStepData) {
      updatePosition()
      currentStepData.onShow?.()

      const handleResize = () => updatePosition()
      const handleScroll = () => updatePosition()

      window.addEventListener('resize', handleResize)
      window.addEventListener('scroll', handleScroll, true)

      return () => {
        window.removeEventListener('resize', handleResize)
        window.removeEventListener('scroll', handleScroll, true)
      }
    }
  }, [isActive, currentStep, currentStepData, updatePosition])

  const handleNext = useCallback(() => {
    currentStepData?.onComplete?.()

    if (isLastStep) {
      handleComplete()
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }, [currentStepData, isLastStep])

  const handlePrevious = useCallback(() => {
    if (!isFirstStep) {
      setCurrentStep((prev) => prev - 1)
    }
  }, [isFirstStep])

  const handleSkip = useCallback(() => {
    onSkip?.()
    handleComplete()
  }, [onSkip])

  const handleComplete = useCallback(() => {
    if (storageKey) {
      setCompleted(true)
    }
    onComplete?.()
    setCurrentStep(0)
  }, [storageKey, setCompleted, onComplete])

  // Don't show if already completed and has storage key
  if (!isActive || (storageKey && completed)) {
    return null
  }

  // Call onStart when tour becomes active
  useEffect(() => {
    if (isActive && currentStep === 0) {
      onStart?.()
    }
  }, [isActive, currentStep, onStart])

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (closeOnBackdropClick && e.target === overlayRef.current) {
      handleSkip()
    }
  }

  return createPortal(
    <>
      {/* Overlay */}
      <div
        ref={overlayRef}
        onClick={handleBackdropClick}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          zIndex: 10000,
          pointerEvents: closeOnBackdropClick ? 'auto' : 'none',
        }}
      >
        {/* Highlight target element */}
        {highlightTarget && targetRect && (
          <div
            style={{
              position: 'fixed',
              top: `${targetRect.top - 4}px`,
              left: `${targetRect.left - 4}px`,
              width: `${targetRect.width + 8}px`,
              height: `${targetRect.height + 8}px`,
              border: `2px solid ${colors.primary[500]}`,
              borderRadius: borderRadius.md,
              boxShadow: `0 0 0 9999px rgba(0, 0, 0, 0.5)`,
              pointerEvents: 'none',
              zIndex: 10001,
            }}
          />
        )}
      </div>

      {/* Tooltip */}
      {currentStepData && (
        <div
          ref={tooltipRef}
          className={cn('guided-tour-tooltip', className)}
          style={{
            position: 'fixed',
            top: `${position.top}px`,
            left: `${position.left}px`,
            background: colors.semantic.backgroundDefault,
            borderRadius: borderRadius.lg,
            boxShadow: shadows.elevation24,
            padding: spacing[6],
            maxWidth: '400px',
            zIndex: 10002,
            pointerEvents: 'auto',
          }}
        >
          {/* Header */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              marginBottom: spacing[4],
            }}
          >
            <div style={{ flex: 1 }}>
              {showProgress && (
                <div
                  style={{
                    fontSize: '12px',
                    color: colors.semantic.textSecondary,
                    marginBottom: spacing[2],
                  }}
                >
                  Step {currentStep + 1} of {steps.length}
                </div>
              )}
              <h3
                style={{
                  fontSize: '18px',
                  fontWeight: 600,
                  color: colors.semantic.textPrimary,
                  margin: 0,
                }}
              >
                {currentStepData.title}
              </h3>
            </div>
            {showSkip && (
              <button
                onClick={handleSkip}
                aria-label="Skip tour"
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
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = colors.semantic.textPrimary
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = colors.semantic.textSecondary
                }}
              >
                <Close fontSize="small" />
              </button>
            )}
          </div>

          {/* Content */}
          <div
            style={{
              fontSize: '14px',
              color: colors.semantic.textSecondary,
              lineHeight: 1.6,
              marginBottom: spacing[6],
            }}
          >
            {currentStepData.content}
          </div>

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: spacing[2],
            }}
          >
            <div style={{ display: 'flex', gap: spacing[2] }}>
              {!isFirstStep && (
                <Button
                  variant="outlined"
                  onClick={handlePrevious}
                  startIcon={<ArrowBack />}
                  sx={{
                    textTransform: 'none',
                  }}
                >
                  Previous
                </Button>
              )}
            </div>
            <div style={{ display: 'flex', gap: spacing[2] }}>
              {showSkip && !isLastStep && (
                <Button
                  variant="text"
                  onClick={handleSkip}
                  endIcon={<SkipNext />}
                  sx={{
                    textTransform: 'none',
                    color: colors.semantic.textSecondary,
                  }}
                >
                  Skip Tour
                </Button>
              )}
              <Button
                variant="contained"
                color="primary"
                onClick={handleNext}
                endIcon={isLastStep ? undefined : <ArrowForward />}
                sx={{
                  textTransform: 'none',
                }}
              >
                {isLastStep ? 'Finish' : 'Next'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>,
    document.body
  )
}

GuidedTour.displayName = 'GuidedTour'

