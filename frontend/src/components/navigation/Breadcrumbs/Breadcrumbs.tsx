import React from 'react'
import { Link } from 'react-router-dom'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface BreadcrumbItem {
  label: string
  href?: string
  onClick?: () => void
}

export interface BreadcrumbsProps {
  /**
   * Array of breadcrumb items
   */
  items: BreadcrumbItem[]
  /**
   * Separator between items
   * @default '/'
   */
  separator?: string | React.ReactNode
  /**
   * Maximum number of items to show before truncation
   */
  maxItems?: number
  className?: string
}

/**
 * Breadcrumbs component for navigation trail
 */
export const Breadcrumbs: React.FC<BreadcrumbsProps> = ({
  items,
  separator = '/',
  maxItems,
  className,
}) => {
  // Enhanced truncation logic: always show first item, last item, and ellipsis
  const displayItems = React.useMemo(() => {
    if (!maxItems || items.length <= maxItems) {
      return items
    }

    // Always show first item
    const firstItem = items[0]

    // Show last (maxItems - 1) items (excluding first)
    const lastItems = items.slice(-(maxItems - 1))

    // If we have more items than can fit, add ellipsis
    if (items.length > maxItems) {
      return [
        firstItem,
        { label: '...', href: undefined, onClick: undefined },
        ...lastItems,
      ]
    }

    return items
  }, [items, maxItems])

  return (
    <nav
      className={cn('breadcrumbs', className)}
      aria-label="Breadcrumb navigation"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing[2],
        fontSize: '14px',
        color: colors.semantic.textSecondary,
      }}
    >
      <ol
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing[2],
          listStyle: 'none',
          margin: 0,
          padding: 0,
        }}
      >
        {displayItems.map((item, index) => {
          const isLast = index === displayItems.length - 1
          const isActive = isLast

          return (
            <li
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: spacing[2],
              }}
            >
              {index > 0 && (
                <span
                  style={{
                    color: colors.semantic.textSecondary,
                    userSelect: 'none',
                  }}
                  aria-hidden="true"
                >
                  {separator}
                </span>
              )}
              {item.href && !isActive ? (
                <Link
                  to={item.href}
                  onClick={item.onClick}
                  style={{
                    color: colors.semantic.textSecondary,
                    textDecoration: 'none',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = colors.semantic.textPrimary
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = colors.semantic.textSecondary
                  }}
                >
                  {item.label}
                </Link>
              ) : item.onClick && !isActive ? (
                <button
                  onClick={item.onClick}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: colors.semantic.textSecondary,
                    cursor: 'pointer',
                    padding: 0,
                    fontSize: 'inherit',
                    transition: 'color 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.color = colors.semantic.textPrimary
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.color = colors.semantic.textSecondary
                  }}
                >
                  {item.label}
                </button>
              ) : (
                <span
                  style={{
                    color: isActive
                      ? colors.semantic.textPrimary
                      : colors.semantic.textSecondary,
                    fontWeight: isActive ? 500 : 400,
                  }}
                  aria-current={isActive ? 'page' : undefined}
                >
                  {item.label}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

Breadcrumbs.displayName = 'Breadcrumbs'

