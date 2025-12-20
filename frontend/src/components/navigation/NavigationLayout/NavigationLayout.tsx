import React, { useState } from 'react'
import { cn } from '@/components/utils'
import { Header, HeaderProps } from '../Header'
import { Sidebar, SidebarProps } from '../Sidebar'
import { spacing } from '@/styles/tokens'

export interface NavigationLayoutProps {
  /**
   * Header props
   */
  header?: HeaderProps
  /**
   * Sidebar props
   */
  sidebar?: SidebarProps
  /**
   * Main content
   */
  children: React.ReactNode
  /**
   * Whether to show sidebar
   * @default true
   */
  showSidebar?: boolean
  /**
   * Whether sidebar is collapsed (controlled)
   */
  sidebarCollapsed?: boolean
  /**
   * Callback when sidebar collapse state changes
   */
  onSidebarCollapseChange?: (collapsed: boolean) => void
  className?: string
}

/**
 * NavigationLayout component - combines Header + Sidebar for primary navigation pattern
 */
export const NavigationLayout: React.FC<NavigationLayoutProps> = ({
  header,
  sidebar,
  children,
  showSidebar = true,
  sidebarCollapsed: controlledCollapsed,
  onSidebarCollapseChange,
  className,
}) => {
  const [internalCollapsed, setInternalCollapsed] = useState(false)
  const isCollapsed = controlledCollapsed !== undefined
    ? controlledCollapsed
    : internalCollapsed

  const handleSidebarToggle = () => {
    const newCollapsed = !isCollapsed
    if (controlledCollapsed === undefined) {
      setInternalCollapsed(newCollapsed)
    }
    onSidebarCollapseChange?.(newCollapsed)
  }

  return (
    <div
      className={cn('navigation-layout', className)}
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
      }}
    >
      {/* Header */}
      {header && <Header {...header} />}

      {/* Main Content Area */}
      <div
        style={{
          display: 'flex',
          flex: 1,
          overflow: 'hidden',
        }}
      >
        {/* Sidebar */}
        {showSidebar && sidebar && (
          <Sidebar
            {...sidebar}
            collapsed={isCollapsed}
            onToggle={handleSidebarToggle}
          />
        )}

        {/* Page Content */}
        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: spacing[4],
            transition: 'margin-left 0.3s',
          }}
          role="main"
        >
          {children}
        </main>
      </div>
    </div>
  )
}

NavigationLayout.displayName = 'NavigationLayout'

