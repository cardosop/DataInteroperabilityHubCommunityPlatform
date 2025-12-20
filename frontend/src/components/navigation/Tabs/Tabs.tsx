import React, { useCallback, useEffect } from 'react'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { cn } from '@/components/utils'
import { colors, spacing } from '@/styles/tokens'

export interface TabItem {
  id: string
  label: string
  disabled?: boolean
  icon?: React.ReactNode
  path?: string // React Router path (for URL updates)
  searchParam?: string // Query parameter name for tab state
}

export interface TabsProps {
  /**
   * Array of tab items
   */
  tabs: TabItem[]
  /**
   * Currently active tab ID
   */
  activeTab: string
  /**
   * Callback when tab changes
   */
  onChange: (tabId: string) => void
  /**
   * Orientation of tabs
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical'
  /**
   * Whether to update URL on tab change
   * @default false
   */
  updateUrl?: boolean
  /**
   * Query parameter name for URL updates (if updateUrl is true)
   * @default 'tab'
   */
  urlParam?: string
  className?: string
}

/**
 * Enhanced Tabs component with URL updates and keyboard navigation
 */
export const Tabs: React.FC<TabsProps> = ({
  tabs,
  activeTab,
  onChange,
  orientation = 'horizontal',
  updateUrl = false,
  urlParam = 'tab',
  className,
}) => {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()

  // Sync URL with active tab if updateUrl is enabled
  useEffect(() => {
    if (updateUrl) {
      const tab = tabs.find((t) => t.id === activeTab)
      if (tab?.path) {
        // Update path if tab has a path
        navigate(tab.path, { replace: true })
      } else if (tab?.searchParam || urlParam) {
        // Update query parameter
        const paramName = tab?.searchParam || urlParam
        const newParams = new URLSearchParams(searchParams)
        newParams.set(paramName, activeTab)
        setSearchParams(newParams, { replace: true })
      }
    }
  }, [activeTab, updateUrl, tabs, navigate, searchParams, setSearchParams, urlParam])

  // Initialize active tab from URL on mount
  useEffect(() => {
    if (updateUrl) {
      // Check if URL has a tab path
      const tabFromPath = tabs.find((tab) => tab.path === location.pathname)
      if (tabFromPath && tabFromPath.id !== activeTab) {
        onChange(tabFromPath.id)
        return
      }

      // Check query parameters
      const paramName = urlParam
      const tabFromParam = searchParams.get(paramName)
      if (tabFromParam) {
        const tab = tabs.find((t) => t.id === tabFromParam)
        if (tab && tab.id !== activeTab) {
          onChange(tab.id)
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // Only run on mount

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, tabId: string) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault()
        onChange(tabId)
      } else if (e.key === 'ArrowRight' && orientation === 'horizontal') {
        e.preventDefault()
        const currentIndex = tabs.findIndex((t) => t.id === tabId)
        const nextIndex = (currentIndex + 1) % tabs.length
        const nextTab = tabs[nextIndex]
        if (!nextTab.disabled) {
          onChange(nextTab.id)
        }
      } else if (e.key === 'ArrowLeft' && orientation === 'horizontal') {
        e.preventDefault()
        const currentIndex = tabs.findIndex((t) => t.id === tabId)
        const prevIndex = currentIndex === 0 ? tabs.length - 1 : currentIndex - 1
        const prevTab = tabs[prevIndex]
        if (!prevTab.disabled) {
          onChange(prevTab.id)
        }
      }
    },
    [tabs, onChange, orientation, updateUrl, navigate]
  )

  const handleTabChange = (tabId: string) => {
    onChange(tabId)

    if (updateUrl) {
      const tab = tabs.find((t) => t.id === tabId)
      if (tab?.path) {
        navigate(tab.path, { replace: true })
      } else if (tab?.searchParam || urlParam) {
        const paramName = tab?.searchParam || urlParam
        const newParams = new URLSearchParams(searchParams)
        newParams.set(paramName, tabId)
        setSearchParams(newParams, { replace: true })
      }
    }
  }

  return (
    <div
      className={cn('tabs', className)}
      role="tablist"
      aria-orientation={orientation}
      style={{
        display: 'flex',
        flexDirection: orientation === 'vertical' ? 'column' : 'row',
        borderBottom:
          orientation === 'horizontal'
            ? `1px solid ${colors.semantic.borderDivider}`
            : 'none',
        borderRight:
          orientation === 'vertical'
            ? `1px solid ${colors.semantic.borderDivider}`
            : 'none',
      }}
    >
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tabpanel-${tab.id}`}
            id={`tab-${tab.id}`}
            disabled={tab.disabled}
            onClick={() => !tab.disabled && handleTabChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, tab.id)}
            className={cn('tab', isActive && 'tab-active')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: spacing[2],
              padding: `${spacing[3]}px ${spacing[4]}px`,
              background: 'none',
              border: 'none',
              borderBottom:
                orientation === 'horizontal' && isActive
                  ? `2px solid ${colors.primary[500]}`
                  : '2px solid transparent',
              borderRight:
                orientation === 'vertical' && isActive
                  ? `2px solid ${colors.primary[500]}`
                  : '2px solid transparent',
              color: tab.disabled
                ? colors.semantic.textDisabled
                : isActive
                  ? colors.primary[500]
                  : colors.semantic.textSecondary,
              fontSize: '14px',
              fontWeight: isActive ? 500 : 400,
              cursor: tab.disabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              outline: 'none',
            }}
            onFocus={(e) => {
              if (!tab.disabled) {
                e.currentTarget.style.outline = `2px solid ${colors.primary[500]}`
                e.currentTarget.style.outlineOffset = '2px'
              }
            }}
            onBlur={(e) => {
              e.currentTarget.style.outline = 'none'
            }}
          >
            {tab.icon && <span>{tab.icon}</span>}
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

Tabs.displayName = 'Tabs'

