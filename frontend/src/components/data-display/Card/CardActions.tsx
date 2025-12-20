import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface CardActionsProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

/**
 * CardActions component for card action buttons
 */
export const CardActions: React.FC<CardActionsProps> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div
      className={cn('card-actions', className)}
      style={{
        display: 'flex',
        gap: spacing[2],
        marginTop: spacing[4],
        ...props.style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}

CardActions.displayName = 'CardActions'

