import React from 'react'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface Step {
  id: string
  label: string
  description?: string
  optional?: boolean
}

export interface StepperProps {
  /**
   * Array of steps
   */
  steps: Step[]
  /**
   * Current active step index (0-indexed)
   */
  activeStep: number
  /**
   * Orientation of stepper
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical'
  /**
   * Callback when step is clicked
   */
  onStepClick?: (stepIndex: number) => void
  className?: string
}

/**
 * Stepper component for multi-step progress
 */
export const Stepper: React.FC<StepperProps> = ({
  steps,
  activeStep,
  orientation = 'horizontal',
  onStepClick,
  className,
}) => {
  const getStepStatus = (index: number) => {
    if (index < activeStep) return 'completed'
    if (index === activeStep) return 'active'
    return 'pending'
  }

  return (
    <div
      className={cn('stepper', className)}
      style={{
        display: 'flex',
        flexDirection: orientation === 'vertical' ? 'column' : 'row',
        width: '100%',
      }}
    >
      {steps.map((step, index) => {
        const status = getStepStatus(index)
        const isCompleted = status === 'completed'
        const isActive = status === 'active'
        const isClickable = onStepClick && (isCompleted || index <= activeStep)

        return (
          <div
            key={step.id}
            style={{
              display: 'flex',
              flexDirection: orientation === 'vertical' ? 'row' : 'column',
              flex: orientation === 'horizontal' ? 1 : undefined,
              alignItems: orientation === 'vertical' ? 'flex-start' : 'center',
              position: 'relative',
            }}
          >
            {/* Step circle and connector */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                flexDirection: orientation === 'vertical' ? 'column' : 'row',
              }}
            >
              <button
                onClick={() => isClickable && onStepClick?.(index)}
                disabled={!isClickable}
                aria-label={`Step ${index + 1}: ${step.label}`}
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: '50%',
                  border: `2px solid ${
                    isCompleted || isActive
                      ? colors.primary[500]
                      : colors.semantic.borderDefault
                  }`,
                  background:
                    isCompleted || isActive
                      ? colors.primary[500]
                      : 'transparent',
                  color:
                    isCompleted || isActive
                      ? '#FFFFFF'
                      : colors.semantic.textSecondary,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: isClickable ? 'pointer' : 'default',
                  outline: 'none',
                  transition: 'all 0.2s',
                  zIndex: 1,
                  position: 'relative',
                }}
                onFocus={(e) => {
                  if (isClickable) {
                    e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
                    e.currentTarget.style.outlineOffset = '2px'
                  }
                }}
                onBlur={(e) => {
                  e.currentTarget.style.outline = 'none'
                }}
              >
                {isCompleted ? '✓' : index + 1}
              </button>
              {orientation === 'horizontal' && index < steps.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: '2px',
                    background:
                      index < activeStep
                        ? colors.primary[500]
                        : colors.semantic.borderDivider,
                    margin: `0 ${spacing[2]}px`,
                    minWidth: '40px',
                  }}
                  aria-hidden="true"
                />
              )}
            </div>

            {/* Step label */}
            <div
              style={{
                marginTop: orientation === 'horizontal' ? spacing[2] : 0,
                marginLeft: orientation === 'vertical' ? spacing[3] : 0,
                textAlign: orientation === 'horizontal' ? 'center' : 'left',
              }}
            >
              <div
                style={{
                  fontSize: '14px',
                  fontWeight: isActive ? 500 : 400,
                  color: isActive
                    ? colors.primary[500]
                    : isCompleted
                      ? colors.semantic.textPrimary
                      : colors.semantic.textSecondary,
                }}
              >
                {step.label}
              </div>
              {step.description && (
                <div
                  style={{
                    fontSize: '12px',
                    color: colors.semantic.textSecondary,
                    marginTop: spacing[1],
                  }}
                >
                  {step.description}
                </div>
              )}
              {step.optional && (
                <div
                  style={{
                    fontSize: '12px',
                    color: colors.semantic.textHint,
                    marginTop: spacing[1],
                  }}
                >
                  Optional
                </div>
              )}
            </div>

            {/* Vertical connector */}
            {orientation === 'vertical' && index < steps.length - 1 && (
              <div
                style={{
                  position: 'absolute',
                  left: '19px',
                  top: '40px',
                  width: '2px',
                  height: 'calc(100% - 40px)',
                  background:
                    index < activeStep
                      ? colors.primary[500]
                      : colors.semantic.borderDivider,
                  zIndex: 0,
                }}
                aria-hidden="true"
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

Stepper.displayName = 'Stepper'

