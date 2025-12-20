import React from 'react'
import { cn } from '@/components/utils'

export interface ListProps extends React.HTMLAttributes<HTMLUListElement> {
  /**
   * Whether to use ordered list
   * @default false
   */
  ordered?: boolean
  children: React.ReactNode
}

/**
 * List component for ordered/unordered lists
 */
export const List: React.FC<ListProps> = ({
  ordered = false,
  children,
  className,
  ...props
}) => {
  const Component = ordered ? 'ol' : 'ul'
  return (
    <Component
      className={cn('list', className)}
      style={{ listStyle: 'none', padding: 0, margin: 0, ...props.style }}
      {...props}
    >
      {children}
    </Component>
  )
}

List.displayName = 'List'

