import React from 'react'
import { cn } from '@/components/utils'
import { typography, colors } from '@/styles/tokens'

export interface TypographyProps extends React.HTMLAttributes<HTMLElement> {
  /**
   * Typography variant
   * @default 'body1'
   */
  variant?:
    | 'h1'
    | 'h2'
    | 'h3'
    | 'h4'
    | 'h5'
    | 'h6'
    | 'body1'
    | 'body2'
    | 'caption'
    | 'overline'
    | 'code'
  /**
   * Component to render as
   */
  component?: React.ElementType
  children: React.ReactNode
}

const variantToComponent = {
  h1: 'h1',
  h2: 'h2',
  h3: 'h3',
  h4: 'h4',
  h5: 'h5',
  h6: 'h6',
  body1: 'p',
  body2: 'p',
  caption: 'span',
  overline: 'span',
  code: 'code',
} as const

/**
 * Typography component for text styling
 */
export const Typography: React.FC<TypographyProps> = ({
  variant = 'body1',
  component,
  children,
  className,
  ...props
}) => {
  const Component = component || variantToComponent[variant]
  const style = typography.fontSize[variant]

  return (
    <Component
      className={cn('typography', `typography-${variant}`, className)}
      style={{
        fontSize: style.rem,
        lineHeight: style.lineHeight,
        fontFamily:
          variant === 'code'
            ? typography.fontFamily.monospace
            : typography.fontFamily.primary,
        color: colors.semantic.textPrimary,
        margin: 0,
        ...props.style,
      }}
      {...props}
    >
      {children}
    </Component>
  )
}

Typography.displayName = 'Typography'

