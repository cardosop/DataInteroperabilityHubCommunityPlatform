import React from 'react'
import { cn } from '@/components/utils'

export interface CardContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

/**
 * CardContent component for card body content
 */
export const CardContent: React.FC<CardContentProps> = ({
  children,
  className,
  ...props
}) => {
  return (
    <div className={cn('card-content', className)} {...props}>
      {children}
    </div>
  )
}

CardContent.displayName = 'CardContent'

