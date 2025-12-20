import React from 'react'
import { cn } from '@/components/utils'

export interface TabPanelProps {
  /**
   * Tab ID this panel belongs to
   */
  tabId: string
  /**
   * Currently active tab ID
   */
  activeTab: string
  /**
   * Panel content
   */
  children: React.ReactNode
  className?: string
}

/**
 * TabPanel component for tab content
 */
export const TabPanel: React.FC<TabPanelProps> = ({
  tabId,
  activeTab,
  children,
  className,
}) => {
  const isActive = tabId === activeTab

  return (
    <div
      role="tabpanel"
      id={`tabpanel-${tabId}`}
      aria-labelledby={`tab-${tabId}`}
      hidden={!isActive}
      className={cn('tab-panel', className)}
      style={{
        display: isActive ? 'block' : 'none',
      }}
    >
      {children}
    </div>
  )
}

TabPanel.displayName = 'TabPanel'

