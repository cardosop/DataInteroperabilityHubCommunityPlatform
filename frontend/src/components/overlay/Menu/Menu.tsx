import React from 'react'
import { Popover, PopoverProps } from '../Popover'
import { colors, spacing } from '@/styles/tokens'

export interface MenuItem {
  label: string
  onClick: () => void
  disabled?: boolean
  icon?: React.ReactNode
  divider?: boolean
}

export interface MenuProps extends Omit<PopoverProps, 'content'> {
  /**
   * Menu items
   */
  items: MenuItem[]
  /**
   * Trigger element
   */
  trigger: React.ReactElement
}

/**
 * Menu component for dropdown menus
 */
export const Menu: React.FC<MenuProps> = ({ items, trigger, ...props }) => {
  return (
    <Popover
      {...props}
      trigger={trigger}
      content={
        <div style={{ display: 'flex', flexDirection: 'column', minWidth: '200px' }}>
          {items.map((item, index) => {
            if (item.divider) {
              return (
                <div
                  key={index}
                  style={{
                    height: '1px',
                    background: colors.semantic.borderDivider,
                    margin: `${spacing[1]}px 0`,
                  }}
                />
              )
            }

            return (
              <button
                key={index}
                onClick={() => {
                  if (!item.disabled) {
                    item.onClick()
                    props.onOpenChange?.(false)
                  }
                }}
                disabled={item.disabled}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: spacing[2],
                  padding: spacing[2],
                  background: 'none',
                  border: 'none',
                  textAlign: 'left',
                  cursor: item.disabled ? 'not-allowed' : 'pointer',
                  color: item.disabled
                    ? colors.semantic.textDisabled
                    : colors.semantic.textPrimary,
                  fontSize: '14px',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => {
                  if (!item.disabled) {
                    e.currentTarget.style.background = colors.semantic.actionHover
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent'
                }}
              >
                {item.icon && <span>{item.icon}</span>}
                {item.label}
              </button>
            )
          })}
        </div>
      }
    />
  )
}

Menu.displayName = 'Menu'

