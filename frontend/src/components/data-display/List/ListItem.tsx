import React from 'react'
import { cn } from '@/components/utils'
import { spacing } from '@/styles/tokens'

export interface ListItemProps extends React.LiHTMLAttributes<HTMLLIElement> {
  children: React.ReactNode
  /**
   * Action buttons/icons
   */
  actions?: React.ReactNode
  /**
   * Icon element
   */
  icon?: React.ReactNode
}

/**
 * ListItem component for list items
 */
export const ListItem: React.FC<ListItemProps> = ({
  children,
  actions,
  icon,
  className,
  ...props
}) => {
  return (
    <li
      className={cn('list-item', className)}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing[2],
        padding: spacing[2],
        ...props.style,
      }}
      {...props}
    >
      {icon && <span>{icon}</span>}
      <span style={{ flex: 1 }}>{children}</span>
      {actions && <span>{actions}</span>}
    </li>
  )
}

ListItem.displayName = 'ListItem'

