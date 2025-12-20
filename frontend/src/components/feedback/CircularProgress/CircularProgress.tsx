import React from 'react'
import { cn } from '@/components/utils'
import { colors } from '@/styles/tokens'

export interface CircularProgressProps {
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
   * Progress value (0-100) for determinate variant
   */
  value?: number
  /**
   * Variant
   * @default 'indeterminate'
   */
  variant?: 'indeterminate' | 'determinate'
  className?: string
}

const sizeMap = {
  sm: 20,
  md: 32,
  lg: 48,
} as const

/**
 * CircularProgress component for loading spinner
 */
export const CircularProgress: React.FC<CircularProgressProps> = ({
  size = 'md',
  color = 'primary',
  value,
  variant = value !== undefined ? 'determinate' : 'indeterminate',
  className,
}) => {
  const diameter = sizeMap[size]
  const strokeWidth = diameter / 8
  const radius = (diameter - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  const progressColor = color === 'primary' ? colors.primary[500] : '#FFFFFF'

  if (variant === 'determinate' && value !== undefined) {
    const clampedValue = Math.min(Math.max(value, 0), 100)
    const offset = circumference - (clampedValue / 100) * circumference

    return (
      <div className={cn('circular-progress', className)}>
        <svg
          width={diameter}
          height={diameter}
          style={{ transform: 'rotate(-90deg)' }}
        >
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            fill="none"
            stroke={colors.semantic.borderDivider}
            strokeWidth={strokeWidth}
          />
          <circle
            cx={diameter / 2}
            cy={diameter / 2}
            r={radius}
            fill="none"
            stroke={progressColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{
              transition: 'stroke-dashoffset 0.3s ease',
            }}
          />
        </svg>
      </div>
    )
  }

  return (
    <div className={cn('circular-progress', className)}>
      <svg
        width={diameter}
        height={diameter}
        style={{
          animation: 'circular-progress-rotate 1.4s linear infinite',
        }}
      >
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          stroke={progressColor}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference * 0.75}
          strokeLinecap="round"
          style={{
            animation: 'circular-progress-dash 1.4s ease-in-out infinite',
            transformOrigin: 'center',
          }}
        />
      </svg>
      <style>
        {`
          @keyframes circular-progress-rotate {
            0% {
              transform: rotate(0deg);
            }
            100% {
              transform: rotate(360deg);
            }
          }
          @keyframes circular-progress-dash {
            0% {
              stroke-dashoffset: ${circumference * 0.75};
            }
            50% {
              stroke-dashoffset: ${circumference * 0.25};
            }
            100% {
              stroke-dashoffset: ${circumference * 0.75};
            }
          }
        `}
      </style>
    </div>
  )
}

CircularProgress.displayName = 'CircularProgress'

