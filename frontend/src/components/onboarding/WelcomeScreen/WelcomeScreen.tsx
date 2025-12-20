import React, { useState } from 'react'
import { Button } from '@mui/material'
import { CheckCircle, ArrowForward, Close } from '@mui/icons-material'
import { colors, spacing, borderRadius, shadows } from '@/styles/tokens'
import { cn } from '@/components/utils'
import { useLocalStorage } from '@/hooks/useLocalStorage'

export interface WelcomeStep {
  /**
   * Step title
   */
  title: string
  /**
   * Step description
   */
  description: string
  /**
   * Step illustration or icon
   */
  illustration?: React.ReactNode
  /**
   * Step features list
   */
  features?: string[]
}

export interface WelcomeScreenProps {
  /**
   * Welcome screen title
   */
  title: string
  /**
   * Welcome screen subtitle/description
   */
  subtitle?: string
  /**
   * Welcome steps
   */
  steps?: WelcomeStep[]
  /**
   * Primary action button
   */
  primaryAction?: {
    label: string
    onClick: () => void
  }
  /**
   * Secondary action button
   */
  secondaryAction?: {
    label: string
    onClick: () => void
  }
  /**
   * Storage key for remembering dismissal
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
   * Custom content
   */
  children?: React.ReactNode
  /**
   * Callback when welcome screen is dismissed
   */
  onDismiss?: () => void
  className?: string
}

/**
 * WelcomeScreen component for first-time user experience
 *
 * Features:
 * - Multi-step welcome flow
 * - Progress indicator
 * - Skip option
 * - Remembers dismissal
 * - Customizable content
 */
export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
  title,
  subtitle,
  steps = [],
  primaryAction,
  secondaryAction,
  storageKey,
  showSkip = true,
  showProgress = true,
  children,
  onDismiss,
  className,
}) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [dismissed, setDismissed] = useLocalStorage(
    storageKey || 'welcome-screen-dismissed',
    false
  )

  const isLastStep = currentStep === steps.length - 1
  const hasSteps = steps.length > 0

  const handleNext = () => {
    if (isLastStep) {
      handleDismiss()
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1)
    }
  }

  const handleSkip = () => {
    handleDismiss()
  }

  const handleDismiss = () => {
    if (storageKey) {
      setDismissed(true)
    }
    onDismiss?.()
  }

  // Don't show if dismissed
  if (dismissed) {
    return null
  }

  const currentStepData = steps[currentStep]

  return (
    <div
      className={cn('welcome-screen-overlay', className)}
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
      }}
    >
      <div
        style={{
          background: colors.semantic.backgroundDefault,
          borderRadius: borderRadius.xl,
          boxShadow: shadows.elevation24,
          maxWidth: '600px',
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          position: 'relative',
        }}
      >
        {/* Close button */}
        {showSkip && (
          <button
            onClick={handleSkip}
            aria-label="Close welcome screen"
            style={{
              position: 'absolute',
              top: spacing[4],
              right: spacing[4],
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: spacing[1],
              color: colors.semantic.textSecondary,
              display: 'flex',
              alignItems: 'center',
              zIndex: 1,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = colors.semantic.textPrimary
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = colors.semantic.textSecondary
            }}
          >
            <Close />
          </button>
        )}

        <div style={{ padding: spacing[8] }}>
          {/* Progress indicator */}
          {showProgress && hasSteps && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                marginBottom: spacing[6],
                gap: spacing[1],
              }}
            >
              {steps.map((_, index) => (
                <div
                  key={index}
                  style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    background:
                      index === currentStep
                        ? colors.primary[500]
                        : index < currentStep
                          ? colors.primary[300]
                          : colors.semantic.borderDefault,
                    transition: 'background 0.2s',
                  }}
                />
              ))}
            </div>
          )}

          {/* Title */}
          <h1
            style={{
              fontSize: '32px',
              fontWeight: 700,
              color: colors.semantic.textPrimary,
              margin: 0,
              marginBottom: spacing[2],
              textAlign: 'center',
            }}
          >
            {hasSteps ? currentStepData?.title || title : title}
          </h1>

          {/* Subtitle */}
          {(subtitle || (hasSteps && currentStepData?.description)) && (
            <p
              style={{
                fontSize: '16px',
                color: colors.semantic.textSecondary,
                margin: 0,
                marginBottom: spacing[6],
                textAlign: 'center',
                lineHeight: 1.6,
              }}
            >
              {hasSteps
                ? currentStepData?.description || subtitle
                : subtitle}
            </p>
          )}

          {/* Illustration */}
          {hasSteps && currentStepData?.illustration && (
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                marginBottom: spacing[6],
              }}
            >
              {currentStepData.illustration}
            </div>
          )}

          {/* Features list */}
          {hasSteps && currentStepData?.features && (
            <ul
              style={{
                listStyle: 'none',
                padding: 0,
                margin: 0,
                marginBottom: spacing[6],
              }}
            >
              {currentStepData.features.map((feature, index) => (
                <li
                  key={index}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: spacing[2],
                    marginBottom: spacing[3],
                    fontSize: '14px',
                    color: colors.semantic.textPrimary,
                  }}
                >
                  <CheckCircle
                    sx={{
                      color: colors.success[500],
                      fontSize: '20px',
                    }}
                  />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          )}

          {/* Custom content */}
          {children}

          {/* Actions */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: spacing[3],
              marginTop: spacing[8],
            }}
          >
            <div>
              {hasSteps && currentStep > 0 && (
                <Button
                  variant="outlined"
                  onClick={handlePrevious}
                  sx={{
                    textTransform: 'none',
                  }}
                >
                  Previous
                </Button>
              )}
            </div>
            <div style={{ display: 'flex', gap: spacing[2] }}>
              {secondaryAction && (
                <Button
                  variant="outlined"
                  onClick={secondaryAction.onClick}
                  sx={{
                    textTransform: 'none',
                  }}
                >
                  {secondaryAction.label}
                </Button>
              )}
              {primaryAction ? (
                <Button
                  variant="contained"
                  color="primary"
                  onClick={
                    hasSteps && !isLastStep
                      ? handleNext
                      : primaryAction.onClick
                  }
                  endIcon={
                    hasSteps && !isLastStep ? (
                      <ArrowForward />
                    ) : undefined
                  }
                  sx={{
                    textTransform: 'none',
                  }}
                >
                  {hasSteps && !isLastStep
                    ? 'Next'
                    : primaryAction.label}
                </Button>
              ) : (
                hasSteps && (
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={handleNext}
                    endIcon={isLastStep ? undefined : <ArrowForward />}
                    sx={{
                      textTransform: 'none',
                    }}
                  >
                    {isLastStep ? 'Get Started' : 'Next'}
                  </Button>
                )
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

WelcomeScreen.displayName = 'WelcomeScreen'

