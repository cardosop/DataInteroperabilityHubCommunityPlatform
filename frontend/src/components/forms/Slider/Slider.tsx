import React from 'react'
import { cn, useId } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface SliderProps {
  /**
   * Current value
   */
  value: number
  /**
   * Callback when value changes
   */
  onChange: (value: number) => void
  /**
   * Minimum value
   * @default 0
   */
  min?: number
  /**
   * Maximum value
   * @default 100
   */
  max?: number
  /**
   * Step size
   * @default 1
   */
  step?: number
  /**
   * Label for the slider
   */
  label?: string
  /**
   * Whether to show value
   * @default false
   */
  showValue?: boolean
  /**
   * Whether the slider is disabled
   */
  disabled?: boolean
  className?: string
}

/**
 * Slider component for numeric range input
 */
export const Slider: React.FC<SliderProps> = ({
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  label,
  showValue = false,
  disabled,
  className,
}) => {
  const sliderId = useId('slider')
  const percentage = ((value - min) / (max - min)) * 100

  return (
    <div className={cn('slider', className)}>
      {label && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: spacing[2],
          }}
        >
          <label
            htmlFor={sliderId}
            style={{
              fontSize: '14px',
              fontWeight: 500,
              color: colors.semantic.textPrimary,
            }}
          >
            {label}
          </label>
          {showValue && (
            <span
              style={{
                fontSize: '14px',
                color: colors.semantic.textSecondary,
              }}
            >
              {value}
            </span>
          )}
        </div>
      )}
      <div style={{ position: 'relative', padding: `${spacing[2]}px 0` }}>
        <input
          id={sliderId}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          style={{
            width: '100%',
            height: '4px',
            borderRadius: '2px',
            background: `linear-gradient(to right, ${colors.primary[500]} 0%, ${colors.primary[500]} ${percentage}%, ${colors.semantic.borderDefault} ${percentage}%, ${colors.semantic.borderDefault} 100%)`,
            outline: 'none',
            cursor: disabled ? 'not-allowed' : 'pointer',
            opacity: disabled ? 0.5 : 1,
            WebkitAppearance: 'none',
            appearance: 'none',
          }}
          onInput={(e) => {
            const target = e.target as HTMLInputElement
            const percentage = ((Number(target.value) - min) / (max - min)) * 100
            target.style.background = `linear-gradient(to right, ${colors.primary[500]} 0%, ${colors.primary[500]} ${percentage}%, ${colors.semantic.borderDefault} ${percentage}%, ${colors.semantic.borderDefault} 100%)`
          }}
        />
        <style>
          {`
            #${sliderId}::-webkit-slider-thumb {
              -webkit-appearance: none;
              appearance: none;
              width: 18px;
              height: 18px;
              border-radius: 50%;
              background: ${colors.primary[500]};
              cursor: ${disabled ? 'not-allowed' : 'pointer'};
              border: 2px solid #FFFFFF;
              box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            #${sliderId}::-moz-range-thumb {
              width: 18px;
              height: 18px;
              border-radius: 50%;
              background: ${colors.primary[500]};
              cursor: ${disabled ? 'not-allowed' : 'pointer'};
              border: 2px solid #FFFFFF;
              box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
          `}
        </style>
      </div>
    </div>
  )
}

Slider.displayName = 'Slider'

