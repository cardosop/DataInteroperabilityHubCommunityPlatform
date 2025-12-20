import React, { useRef, useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/components/utils'
import { colors, spacing, shadows, breakpoints } from '@/styles/tokens'
import { useKeyboardNavigation } from '../hooks'
import { Drawer } from '@/components/overlay/Drawer'

export interface SidebarItem {
  id: string
  label: string
  href?: string
  path?: string // React Router path
  onClick?: () => void
  icon?: React.ReactNode
  exact?: boolean // For exact route matching
  badge?: number | string
  children?: SidebarItem[]
}

export interface SidebarProps {
  /**
   * Sidebar items
   */
  items: SidebarItem[]
  /**
   * Whether sidebar is collapsed
   * @default false
   */
  collapsed?: boolean
  /**
   * Callback when toggle is clicked
   */
  onToggle?: () => void
  /**
   * Whether sidebar should be sticky
   * @default true
   */
  sticky?: boolean
  /**
   * Whether to use mobile drawer on small screens
   * @default true
   */
  mobileDrawer?: boolean
  className?: string
}

/**
 * Enhanced Sidebar component with React Router integration, mobile drawer, and keyboard navigation
 */
export const Sidebar: React.FC<SidebarProps> = ({
  items,
  collapsed = false,
  onToggle,
  sticky = true,
  mobileDrawer = true,
  className,
}) => {
  const [expandedItems, setExpandedItems] = React.useState<Set<string>>(
    new Set()
  )
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const [isMobile, setIsMobile] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const sidebarRef = useRef<HTMLElement>(null)
  const navRef = useRef<HTMLElement>(null)

  // Check if we're on mobile
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < breakpoints.md)
    }
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  // Determine active state based on current route
  const isItemActive = (item: SidebarItem): boolean => {
    if (item.path) {
      if (item.exact) {
        return location.pathname === item.path
      }
      return location.pathname.startsWith(item.path)
    }
    if (item.href) {
      return location.pathname === item.href
    }
    return false
  }

  // Keyboard navigation
  useKeyboardNavigation({
    containerRef: navRef,
    enabled: !collapsed && !isMobile,
    orientation: 'vertical',
    onActivate: (element) => {
      const link = element.closest('a, button')
      if (link) {
        link.click()
      }
    },
  })

  // Close mobile drawer on route change
  useEffect(() => {
    if (isMobile) {
      setIsMobileOpen(false)
    }
  }, [location.pathname, isMobile])

  const toggleExpand = (itemId: string) => {
    setExpandedItems((prev) => {
      const next = new Set(prev)
      if (next.has(itemId)) {
        next.delete(itemId)
      } else {
        next.add(itemId)
      }
      return next
    })
  }

  const handleItemClick = (item: SidebarItem) => {
    if (item.onClick) {
      item.onClick()
    } else if (item.path) {
      navigate(item.path)
    } else if (item.href) {
      navigate(item.href)
    }
    if (isMobile) {
      setIsMobileOpen(false)
    }
  }

  const renderItem = (item: SidebarItem, level: number = 0) => {
    const isExpanded = expandedItems.has(item.id)
    const hasChildren = item.children && item.children.length > 0
    const isActive = isItemActive(item)

    const ItemComponent = item.path || item.href ? Link : 'div'

    const itemProps = item.path || item.href
      ? {
          to: item.path || item.href || '#',
          onClick: (e: React.MouseEvent) => {
            e.preventDefault()
            if (hasChildren) {
              toggleExpand(item.id)
            } else {
              handleItemClick(item)
            }
          },
        }
      : {
          onClick: () => {
            if (hasChildren) {
              toggleExpand(item.id)
            } else {
              handleItemClick(item)
            }
          },
        }

    return (
      <div key={item.id}>
        <ItemComponent
          {...itemProps}
          style={{
            display: 'flex',
            alignItems: 'center',
            padding: `${spacing[2]}px ${spacing[3]}px`,
            marginLeft: level * spacing[4],
            color: isActive
              ? colors.primary[500]
              : colors.semantic.textPrimary,
            background: isActive ? colors.primary[50] : 'transparent',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: isActive ? 500 : 400,
            transition: 'all 0.2s',
            position: 'relative',
            textDecoration: 'none',
            border: 'none',
            outline: 'none',
            width: '100%',
          }}
          onMouseEnter={(e: React.MouseEvent<HTMLElement>) => {
            if (!isActive) {
              e.currentTarget.style.background = colors.semantic.actionHover
            }
          }}
          onMouseLeave={(e: React.MouseEvent<HTMLElement>) => {
            if (!isActive) {
              e.currentTarget.style.background = 'transparent'
            }
          }}
          onFocus={(e: React.FocusEvent<HTMLElement>) => {
            e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e: React.FocusEvent<HTMLElement>) => {
            e.currentTarget.style.outline = 'none'
          }}
          aria-current={isActive ? 'page' : undefined}
        >
          {item.icon && (
            <span
              style={{
                display: 'flex',
                alignItems: 'center',
                marginRight: collapsed ? 0 : spacing[2],
                minWidth: '20px',
              }}
            >
              {item.icon}
            </span>
          )}
          {!collapsed && (
            <>
              <span style={{ flex: 1 }}>{item.label}</span>
              {item.badge && (
                <span
                  style={{
                    background: colors.primary[500],
                    color: '#FFFFFF',
                    fontSize: '11px',
                    fontWeight: 500,
                    padding: `2px ${spacing[1]}px`,
                    borderRadius: '10px',
                    minWidth: '18px',
                    textAlign: 'center',
                  }}
                >
                  {item.badge}
                </span>
              )}
              {hasChildren && (
                <span
                  style={{
                    transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s',
                  }}
                >
                  ›
                </span>
              )}
            </>
          )}
        </ItemComponent>
        {hasChildren && !collapsed && isExpanded && (
          <div style={{ marginTop: spacing[1] }}>
            {item.children!.map((child) => renderItem(child, level + 1))}
          </div>
        )}
      </div>
    )
  }

  const sidebarContent = (
    <nav
      ref={navRef}
      style={{
        padding: spacing[4],
        paddingTop: onToggle ? spacing[10] : spacing[4],
      }}
      aria-label="Sidebar navigation"
      role="navigation"
    >
      {items.map((item) => renderItem(item))}
    </nav>
  )

  // Mobile drawer mode
  if (isMobile && mobileDrawer) {
    return (
      <>
        <button
          onClick={() => setIsMobileOpen(true)}
          aria-label="Open sidebar"
          style={{
            position: 'fixed',
            top: spacing[2],
            left: spacing[2],
            zIndex: 999,
            width: '40px',
            height: '40px',
            background: colors.semantic.backgroundDefault,
            border: `1px solid ${colors.semantic.borderDefault}`,
            borderRadius: '4px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: shadows.elevation2,
          }}
        >
          ☰
        </button>
        <Drawer
          open={isMobileOpen}
          onClose={() => setIsMobileOpen(false)}
          anchor="left"
          width="280px"
        >
          <div
            style={{
              padding: spacing[4],
              borderBottom: `1px solid ${colors.semantic.borderDivider}`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 500 }}>
              Navigation
            </h2>
            <button
              onClick={() => setIsMobileOpen(false)}
              aria-label="Close sidebar"
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '24px',
                color: colors.semantic.textSecondary,
              }}
            >
              ×
            </button>
          </div>
          {sidebarContent}
        </Drawer>
      </>
    )
  }

  // Desktop sidebar
  return (
    <aside
      ref={sidebarRef}
      className={cn('sidebar', className)}
      style={{
        width: collapsed ? '64px' : '240px',
        height: '100vh',
        position: sticky ? 'sticky' : 'relative',
        top: 0,
        left: 0,
        background: colors.semantic.backgroundPaper,
        borderRight: `1px solid ${colors.semantic.borderDivider}`,
        boxShadow: shadows.elevation1,
        transition: 'width 0.3s',
        overflowY: 'auto',
        overflowX: 'hidden',
        zIndex: 100,
      }}
    >
      {onToggle && (
        <button
          onClick={onToggle}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          style={{
            position: 'absolute',
            top: spacing[2],
            right: spacing[2],
            width: '32px',
            height: '32px',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '4px',
            color: colors.semantic.textSecondary,
            transition: 'all 0.2s',
            zIndex: 1,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = colors.semantic.actionHover
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'transparent'
          }}
          onFocus={(e) => {
            e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
            e.currentTarget.style.outlineOffset = '2px'
          }}
          onBlur={(e) => {
            e.currentTarget.style.outline = 'none'
          }}
        >
          {collapsed ? '›' : '‹'}
        </button>
      )}
      {sidebarContent}
    </aside>
  )
}

Sidebar.displayName = 'Sidebar'
